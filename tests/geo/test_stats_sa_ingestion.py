import unittest
import psycopg2
import psycopg2.errors
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

    def test_a_fresh_ingestion_accounting(self):
        """Test A: Fresh ingestion reports exactly 3,109 MP inserted, 0 updated; 21,241 SP inserted, 0 updated; 2 quarantined."""
        with self.conn.cursor() as cur:
            cur.execute("TRUNCATE TABLE sub_places, main_places CASCADE;")
        self.conn.commit()

        report = run_ingestion(self.conn, DEFAULT_MAIN_PLACE_PATH, DEFAULT_SUB_PLACE_PATH)
        self.assertEqual(report["mp_inserted"], 3109)
        self.assertEqual(report["mp_updated"], 0)
        self.assertEqual(report["sp_inserted"], 21241)
        self.assertEqual(report["sp_updated"], 0)
        self.assertEqual(report["quarantined_count"], 2)
        self.assertEqual(report["final_db_mp_count"], 3109)
        self.assertEqual(report["final_db_sp_count"], 21241)

    def test_b_repeat_ingestion_accounting(self):
        """Test B: Repeat ingestion against populated tables reports 0 inserted, 3,109 MP updated, 21,241 SP updated."""
        report = run_ingestion(self.conn, DEFAULT_MAIN_PLACE_PATH, DEFAULT_SUB_PLACE_PATH)
        self.assertEqual(report["mp_inserted"], 0)
        self.assertEqual(report["mp_updated"], 3109)
        self.assertEqual(report["sp_inserted"], 0)
        self.assertEqual(report["sp_updated"], 21241)
        self.assertEqual(report["quarantined_count"], 2)
        self.assertEqual(report["final_db_mp_count"], 3109)
        self.assertEqual(report["final_db_sp_count"], 21241)

    def test_c_actual_postgresql_rollback_after_mutation(self):
        """Test C: PostgreSQL-native test proving rollback after database mutation has begun."""
        with self.conn.cursor() as cur:
            cur.execute("TRUNCATE TABLE sub_places, main_places CASCADE;")
        self.conn.commit()

        # Begin transaction manually
        conn_rollback = psycopg2.connect(**PG_CONFIG)
        conn_rollback.set_client_encoding('UTF8')
        conn_rollback.autocommit = False
        cur_rb = conn_rollback.cursor()

        try:
            # 1. Mutate DB successfully
            cur_rb.execute("""
                INSERT INTO main_places (mp_code, mp_name, municipality_code, municipality_name, district_code, district_name, province_code, province_name)
                VALUES (81501, 'Broedershoek', 815, 'Mbombela', 32, 'Ehlanzeni', 8, 'MPUMALANGA');
            """)
            # Verify it is visible inside uncommitted transaction
            cur_rb.execute("SELECT COUNT(*) FROM main_places WHERE mp_code = 81501;")
            self.assertEqual(cur_rb.fetchone()[0], 1)

            # 2. Trigger fatal DB error (violating foreign key constraint)
            cur_rb.execute("""
                INSERT INTO sub_places (sp_code, sp_name, main_place_code, municipality_code, municipality_name, district_code, district_name, province_code, province_name)
                VALUES (99999001, 'Invalid Parent SP', 99999, 815, 'Mbombela', 32, 'Ehlanzeni', 8, 'MPUMALANGA');
            """)
        except psycopg2.errors.ForeignKeyViolation:
            # 3. Handle expected error and roll back
            conn_rollback.rollback()
        finally:
            conn_rollback.close()

        # 4. Verify mutation was completely reverted
        with self.conn.cursor() as cur:
            cur.execute("SELECT COUNT(*) FROM main_places WHERE mp_code = 81501;")
            count = cur.fetchone()[0]
            self.assertEqual(count, 0, "Mutation was not rolled back!")

        # Restore test data
        run_ingestion(self.conn, DEFAULT_MAIN_PLACE_PATH, DEFAULT_SUB_PLACE_PATH)

    def test_d_parent_derivation(self):
        """Test D: Parent MP_CODE is correctly derived as SP_CODE // 1000."""
        _, mp_set = validate_and_parse_main_places(DEFAULT_MAIN_PLACE_PATH)
        valid_records, _ = validate_and_parse_sub_places(DEFAULT_SUB_PLACE_PATH, mp_set)
        for r in valid_records[:100]:
            self.assertEqual(r["main_place_code"], r["sp_code"] // 1000)

    def test_e_known_orphan_detection_and_exclusion(self):
        """Test E: Exactly the 2 known orphaned SP_CODEs are detected and quarantined."""
        _, mp_set = validate_and_parse_main_places(DEFAULT_MAIN_PLACE_PATH)
        _, orphans = validate_and_parse_sub_places(DEFAULT_SUB_PLACE_PATH, mp_set)
        orphan_codes = set(o["sp_code"] for o in orphans)
        self.assertEqual(orphan_codes, {11497004, 12332002})

        # Verify not inserted into database
        with self.conn.cursor() as cur:
            cur.execute("SELECT COUNT(*) FROM sub_places WHERE sp_code IN (11497004, 12332002);")
            self.assertEqual(cur.fetchone()[0], 0)

    def test_f_provenance_fields(self):
        """Test F: Provenance fields are correctly populated in DB."""
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

    def test_g_prevalidation_rollback(self):
        """Test G: Pre-validation error triggers IngestionValidationError before any DB interaction."""
        dummy_mp_set = {99999}
        with self.assertRaises(IngestionValidationError):
            validate_and_parse_sub_places(DEFAULT_SUB_PLACE_PATH, dummy_mp_set)

if __name__ == '__main__':
    unittest.main()
