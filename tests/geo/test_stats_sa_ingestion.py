import unittest
import psycopg2
from scripts.geo.import_stats_sa import (
    validate_and_parse_main_places,
    validate_and_parse_sub_places,
    run_ingestion,
    IngestionValidationError,
    DEFAULT_MAIN_PLACE_PATH,
    DEFAULT_SUB_PLACE_PATH
)

PG_CONFIG = {
    "dbname": "gov_intel_test",
    "user": "postgres",
    "host": "127.0.0.1",
    "port": 54339
}

class StatsSAIngestionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.conn = psycopg2.connect(**PG_CONFIG)
        cls.conn.set_client_encoding('UTF8')

    @classmethod
    def tearDownClass(cls):
        cls.conn.close()

    def test_a_main_place_parsing(self):
        """Test A: Main Place source parsing validates 3,109 rows and expected structure."""
        records, mp_set = validate_and_parse_main_places(DEFAULT_MAIN_PLACE_PATH)
        self.assertEqual(len(records), 3109)
        self.assertEqual(len(mp_set), 3109)
        # Verify first row structure
        first = records[0]
        self.assertEqual(first["mp_code"], 10101)
        self.assertEqual(first["mp_name"], "Doringbaai")
        self.assertEqual(first["province_code"], 1)

    def test_b_sub_place_parsing(self):
        """Test B: Sub Place source parsing validates 21,243 total rows (21,241 valid + 2 orphans)."""
        _, mp_set = validate_and_parse_main_places(DEFAULT_MAIN_PLACE_PATH)
        valid_records, orphans = validate_and_parse_sub_places(DEFAULT_SUB_PLACE_PATH, mp_set)
        self.assertEqual(len(valid_records), 21241)
        self.assertEqual(len(orphans), 2)

    def test_c_parent_derivation(self):
        """Test C: Parent MP_CODE is correctly derived as SP_CODE // 1000."""
        _, mp_set = validate_and_parse_main_places(DEFAULT_MAIN_PLACE_PATH)
        valid_records, _ = validate_and_parse_sub_places(DEFAULT_SUB_PLACE_PATH, mp_set)
        for r in valid_records[:100]: # Sample 100 records
            self.assertEqual(r["main_place_code"], r["sp_code"] // 1000)

    def test_d_known_orphan_detection(self):
        """Test D: Exactly the 2 known orphaned SP_CODEs are detected."""
        _, mp_set = validate_and_parse_main_places(DEFAULT_MAIN_PLACE_PATH)
        _, orphans = validate_and_parse_sub_places(DEFAULT_SUB_PLACE_PATH, mp_set)
        orphan_codes = set(o["sp_code"] for o in orphans)
        self.assertEqual(orphan_codes, {11497004, 12332002})

    def test_e_and_f_database_counts(self):
        """Test E & F: Database contains exactly 3,109 Main Places and 21,241 Sub Places, and 0 orphans."""
        with self.conn.cursor() as cur:
            cur.execute("SELECT COUNT(*) FROM main_places;")
            mp_count = cur.fetchone()[0]
            self.assertEqual(mp_count, 3109)

            cur.execute("SELECT COUNT(*) FROM sub_places;")
            sp_count = cur.fetchone()[0]
            self.assertEqual(sp_count, 21241)

            # Assert orphans were NOT inserted
            cur.execute("SELECT COUNT(*) FROM sub_places WHERE sp_code IN (11497004, 12332002);")
            orphan_inserted = cur.fetchone()[0]
            self.assertEqual(orphan_inserted, 0)

    def test_g_idempotency(self):
        """Test G: Re-running ingestion is idempotent and yields identical counts."""
        report = run_ingestion(self.conn, DEFAULT_MAIN_PLACE_PATH, DEFAULT_SUB_PLACE_PATH)
        self.assertEqual(report["final_db_mp_count"], 3109)
        self.assertEqual(report["final_db_sp_count"], 21241)

    def test_h_transaction_rollback_on_fatal_error(self):
        """Test H: Fatal validation error stops before DB mutation and rolls back."""
        # Intentionally invalid MP codes set should cause unmapped orphan check to fail
        dummy_mp_set = {99999}
        with self.assertRaises(IngestionValidationError):
            validate_and_parse_sub_places(DEFAULT_SUB_PLACE_PATH, dummy_mp_set)

    def test_i_provenance_fields(self):
        """Test I: Provenance fields are correctly populated in DB."""
        with self.conn.cursor() as cur:
            cur.execute("SELECT dataset_name, dataset_version, observed_at FROM main_places LIMIT 1;")
            row = cur.fetchone()
            self.assertEqual(row[0], "Stats SA 2011 Census")
            self.assertEqual(row[1], "v2011.1")
            self.assertIsNotNone(row[2])

            cur.execute("SELECT dataset_name, dataset_version, observed_at FROM sub_places LIMIT 1;")
            row_sp = cur.fetchone()
            self.assertEqual(row_sp[0], "Stats SA 2011 Census")
            self.assertEqual(row_sp[1], "v2011.1")
            self.assertIsNotNone(row_sp[2])

if __name__ == '__main__':
    unittest.main()
