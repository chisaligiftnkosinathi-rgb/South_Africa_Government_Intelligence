import unittest
import sqlite3
import re

MIGRATION_PATH = "supabase/migrations/20260909000002_geographic_reference_layer.sql"
CORE_MIGRATION_PATH = "supabase/migrations/20260909000001_initial_core_schema.sql"

def adapt_pg_to_sqlite(sql: str) -> str:
    lines = []
    for line in sql.splitlines():
        trimmed = line.strip()
        if trimmed.startswith("CREATE EXTENSION"):
            continue
        lines.append(line)
    
    cleaned = "\n".join(lines)
    cleaned = re.sub(r'\bUUID\b', 'TEXT', cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r'\bTIMESTAMPTZ\b', 'TEXT', cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r'\bDEFAULT gen_random_uuid\(\)', '', cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r'\bDEFAULT CURRENT_TIMESTAMP\b', "DEFAULT (datetime('now'))", cleaned, flags=re.IGNORECASE)
    return cleaned

class GeographicSchemaVerificationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        with open(MIGRATION_PATH, "r", encoding="utf-8") as f:
            raw_sql = f.read()
        cls.sqlite_sql = adapt_pg_to_sqlite(raw_sql)
        
    def setUp(self):
        self.conn = sqlite3.connect(":memory:")
        self.conn.execute("PRAGMA foreign_keys = ON;")
        self.conn.executescript(self.sqlite_sql)
        self.cur = self.conn.cursor()

    def tearDown(self):
        self.conn.close()

    def test_a_main_place_uniqueness(self):
        """Test A: Duplicate mp_code must fail."""
        self.cur.execute("""
            INSERT INTO main_places (id, mp_code, mp_name, municipality_code, municipality_name, district_code, district_name, province_code, province_name)
            VALUES ('mp-1', 81501, 'Broedershoek', 815, 'Mbombela', 32, 'Ehlanzeni', 8, 'MPUMALANGA')
        """)
        with self.assertRaises(sqlite3.IntegrityError):
            self.cur.execute("""
                INSERT INTO main_places (id, mp_code, mp_name, municipality_code, municipality_name, district_code, district_name, province_code, province_name)
                VALUES ('mp-2', 81501, 'Broedershoek Duplicate', 815, 'Mbombela', 32, 'Ehlanzeni', 8, 'MPUMALANGA')
            """)

    def test_b_sub_place_uniqueness(self):
        """Test B: Duplicate sp_code must fail."""
        # Insert parent Main Place
        self.cur.execute("""
            INSERT INTO main_places (id, mp_code, mp_name, municipality_code, municipality_name, district_code, district_name, province_code, province_name)
            VALUES ('mp-1', 81505, 'Kanyamazane', 815, 'Mbombela', 32, 'Ehlanzeni', 8, 'MPUMALANGA')
        """)
        # Insert first Sub Place
        self.cur.execute("""
            INSERT INTO sub_places (id, sp_code, sp_name, main_place_code, municipality_code, municipality_name, district_code, district_name, province_code, province_name)
            VALUES ('sp-1', 81505001, 'Kanyamazane SP', 81505, 815, 'Mbombela', 32, 'Ehlanzeni', 8, 'MPUMALANGA')
        """)
        # Duplicate sp_code must raise IntegrityError
        with self.assertRaises(sqlite3.IntegrityError):
            self.cur.execute("""
                INSERT INTO sub_places (id, sp_code, sp_name, main_place_code, municipality_code, municipality_name, district_code, district_name, province_code, province_name)
                VALUES ('sp-2', 81505001, 'Kanyamazane SP Duplicate', 81505, 815, 'Mbombela', 32, 'Ehlanzeni', 8, 'MPUMALANGA')
            """)

    def test_c_main_place_inheritance(self):
        """Test C: A sub_places.main_place_code referencing a nonexistent main_places.mp_code must fail."""
        with self.assertRaises(sqlite3.IntegrityError):
            self.cur.execute("""
                INSERT INTO sub_places (id, sp_code, sp_name, main_place_code, municipality_code, municipality_name, district_code, district_name, province_code, province_name)
                VALUES ('sp-1', 99999001, 'Nonexistent Parent SP', 99999, 815, 'Mbombela', 32, 'Ehlanzeni', 8, 'MPUMALANGA')
            """)

    def test_d_geographic_governance_separation(self):
        """Test D: The geographic tables have no foreign keys to entities or institutions."""
        self.cur.execute("PRAGMA foreign_key_list(main_places)")
        mp_fks = self.cur.fetchall()
        self.assertEqual(len(mp_fks), 0, "main_places must have 0 foreign keys")

        self.cur.execute("PRAGMA foreign_key_list(sub_places)")
        sp_fks = self.cur.fetchall()
        # sub_places must only have 1 FK, pointing to main_places(mp_code)
        self.assertEqual(len(sp_fks), 1, "sub_places must have exactly 1 FK (to main_places)")
        target_table = sp_fks[0][2]
        self.assertEqual(target_table, "main_places")

    def test_e_province_code_validity(self):
        """Test E: province_code outside 1-9 must fail."""
        with self.assertRaises(sqlite3.IntegrityError):
            self.cur.execute("""
                INSERT INTO main_places (id, mp_code, mp_name, municipality_code, municipality_name, district_code, district_name, province_code, province_name)
                VALUES ('mp-1', 81501, 'Invalid Province Place', 815, 'Mbombela', 32, 'Ehlanzeni', 10, 'UNKNOWN')
            """)
        with self.assertRaises(sqlite3.IntegrityError):
            self.cur.execute("""
                INSERT INTO main_places (id, mp_code, mp_name, municipality_code, municipality_name, district_code, district_name, province_code, province_name)
                VALUES ('mp-2', 81502, 'Invalid Province Place 0', 815, 'Mbombela', 32, 'Ehlanzeni', 0, 'UNKNOWN')
            """)

    def test_f_invalid_geographic_identifiers(self):
        """Test F: Zero/negative codes and empty names must fail."""
        with self.assertRaises(sqlite3.IntegrityError):
            self.cur.execute("""
                INSERT INTO main_places (id, mp_code, mp_name, municipality_code, municipality_name, district_code, district_name, province_code, province_name)
                VALUES ('mp-1', -1, 'Negative Code', 815, 'Mbombela', 32, 'Ehlanzeni', 8, 'MPUMALANGA')
            """)
        with self.assertRaises(sqlite3.IntegrityError):
            self.cur.execute("""
                INSERT INTO main_places (id, mp_code, mp_name, municipality_code, municipality_name, district_code, district_name, province_code, province_name)
                VALUES ('mp-2', 81501, '   ', 815, 'Mbombela', 32, 'Ehlanzeni', 8, 'MPUMALANGA')
            """)

    def test_g_sub_place_parent_code_integrity(self):
        """Test G: Sub Place encoded parent (sp_code / 1000) must match main_place_code."""
        self.cur.execute("""
            INSERT INTO main_places (id, mp_code, mp_name, municipality_code, municipality_name, district_code, district_name, province_code, province_name)
            VALUES ('mp-1', 81505, 'Kanyamazane', 815, 'Mbombela', 32, 'Ehlanzeni', 8, 'MPUMALANGA')
        """)
        # sp_code = 81501001 implies parent 81501, but main_place_code given as 81505 -> must fail CHECK
        with self.assertRaises(sqlite3.IntegrityError):
            self.cur.execute("""
                INSERT INTO sub_places (id, sp_code, sp_name, main_place_code, municipality_code, municipality_name, district_code, district_name, province_code, province_name)
                VALUES ('sp-mismatch', 81501001, 'Mismatch SP', 81505, 815, 'Mbombela', 32, 'Ehlanzeni', 8, 'MPUMALANGA')
            """)

    def test_h_historical_dataset_retention(self):
        """Test H: Dataset provenance fields are present and preserve lineage."""
        self.cur.execute("""
            INSERT INTO main_places (id, mp_code, mp_name, municipality_code, municipality_name, district_code, district_name, province_code, province_name, dataset_name, dataset_version)
            VALUES ('mp-1', 81501, 'Broedershoek', 815, 'Mbombela', 32, 'Ehlanzeni', 8, 'MPUMALANGA', 'Stats SA 2011 Census', 'v2011.1')
        """)
        self.cur.execute("SELECT dataset_name, dataset_version FROM main_places WHERE mp_code = 81501")
        row = self.cur.fetchone()
        self.assertEqual(row, ('Stats SA 2011 Census', 'v2011.1'))

if __name__ == '__main__':
    unittest.main()
