import unittest
import psycopg2
import psycopg2.errors

PG_CONFIG = {
    "dbname": "gov_intel_test",
    "user": "postgres",
    "host": "127.0.0.1",
    "port": 54339
}

class PostgreSQLGeographicVerificationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.conn = psycopg2.connect(**PG_CONFIG)
        cls.conn.set_client_encoding('UTF8')
        cls.conn.autocommit = False

    @classmethod
    def tearDownClass(cls):
        cls.conn.close()

    def setUp(self):
        self.cur = self.conn.cursor()
        # Clean geographic tables before each test
        self.cur.execute("TRUNCATE TABLE sub_places, main_places CASCADE;")
        self.conn.commit()

    def tearDown(self):
        self.conn.rollback()
        self.cur.close()

    def test_a_main_place_uniqueness(self):
        """Test A: Duplicate main_places.mp_code must fail."""
        self.cur.execute("""
            INSERT INTO main_places (mp_code, mp_name, municipality_code, municipality_name, district_code, district_name, province_code, province_name)
            VALUES (81501, 'Broedershoek', 815, 'Mbombela', 32, 'Ehlanzeni', 8, 'MPUMALANGA');
        """)
        with self.assertRaises(psycopg2.errors.UniqueViolation):
            self.cur.execute("""
                INSERT INTO main_places (mp_code, mp_name, municipality_code, municipality_name, district_code, district_name, province_code, province_name)
                VALUES (81501, 'Broedershoek Duplicate', 815, 'Mbombela', 32, 'Ehlanzeni', 8, 'MPUMALANGA');
            """)

    def test_b_sub_place_uniqueness(self):
        """Test B: Duplicate sub_places.sp_code must fail."""
        self.cur.execute("""
            INSERT INTO main_places (mp_code, mp_name, municipality_code, municipality_name, district_code, district_name, province_code, province_name)
            VALUES (81505, 'Kanyamazane', 815, 'Mbombela', 32, 'Ehlanzeni', 8, 'MPUMALANGA');
        """)
        self.cur.execute("""
            INSERT INTO sub_places (sp_code, sp_name, main_place_code, municipality_code, municipality_name, district_code, district_name, province_code, province_name)
            VALUES (81505001, 'Kanyamazane SP', 81505, 815, 'Mbombela', 32, 'Ehlanzeni', 8, 'MPUMALANGA');
        """)
        with self.assertRaises(psycopg2.errors.UniqueViolation):
            self.cur.execute("""
                INSERT INTO sub_places (sp_code, sp_name, main_place_code, municipality_code, municipality_name, district_code, district_name, province_code, province_name)
                VALUES (81505001, 'Kanyamazane SP Duplicate', 81505, 815, 'Mbombela', 32, 'Ehlanzeni', 8, 'MPUMALANGA');
            """)

    def test_c_nonexistent_main_place_code(self):
        """Test C: Nonexistent main_place_code in sub_places must fail FK constraint."""
        with self.assertRaises(psycopg2.errors.ForeignKeyViolation):
            self.cur.execute("""
                INSERT INTO sub_places (sp_code, sp_name, main_place_code, municipality_code, municipality_name, district_code, district_name, province_code, province_name)
                VALUES (99999001, 'Nonexistent Parent SP', 99999, 815, 'Mbombela', 32, 'Ehlanzeni', 8, 'MPUMALANGA');
            """)

    def test_d_zero_governance_foreign_keys(self):
        """Test D: Geographic tables have exactly zero foreign keys to governance entities."""
        self.cur.execute("""
            SELECT ccu.table_name
            FROM information_schema.table_constraints tc
            JOIN information_schema.constraint_column_usage ccu ON ccu.constraint_name = tc.constraint_name
            WHERE tc.constraint_type = 'FOREIGN KEY'
              AND tc.table_name IN ('main_places', 'sub_places')
              AND ccu.table_name NOT IN ('main_places', 'sub_places');
        """)
        foreign_refs = self.cur.fetchall()
        self.assertEqual(len(foreign_refs), 0, f"Found unexpected governance FK references: {foreign_refs}")

    def test_e_invalid_province_codes(self):
        """Test E: province_code outside 1-9 must fail check constraint."""
        with self.assertRaises(psycopg2.errors.CheckViolation):
            self.cur.execute("""
                INSERT INTO main_places (mp_code, mp_name, municipality_code, municipality_name, district_code, district_name, province_code, province_name)
                VALUES (81501, 'Invalid Place 10', 815, 'Mbombela', 32, 'Ehlanzeni', 10, 'UNKNOWN');
            """)
        self.conn.rollback()
        with self.assertRaises(psycopg2.errors.CheckViolation):
            self.cur.execute("""
                INSERT INTO main_places (mp_code, mp_name, municipality_code, municipality_name, district_code, district_name, province_code, province_name)
                VALUES (81502, 'Invalid Place 0', 815, 'Mbombela', 32, 'Ehlanzeni', 0, 'UNKNOWN');
            """)

    def test_f_invalid_identifiers_and_empty_names(self):
        """Test F: Zero/negative codes and blank names must fail check constraints."""
        with self.assertRaises(psycopg2.errors.CheckViolation):
            self.cur.execute("""
                INSERT INTO main_places (mp_code, mp_name, municipality_code, municipality_name, district_code, district_name, province_code, province_name)
                VALUES (-5, 'Negative Code', 815, 'Mbombela', 32, 'Ehlanzeni', 8, 'MPUMALANGA');
            """)
        self.conn.rollback()
        with self.assertRaises(psycopg2.errors.CheckViolation):
            self.cur.execute("""
                INSERT INTO main_places (mp_code, mp_name, municipality_code, municipality_name, district_code, district_name, province_code, province_name)
                VALUES (81501, '   ', 815, 'Mbombela', 32, 'Ehlanzeni', 8, 'MPUMALANGA');
            """)

    def test_g_sp_code_parent_arithmetic_constraint(self):
        """Test G: sp_code / 1000 must strictly agree with main_place_code."""
        self.cur.execute("""
            INSERT INTO main_places (mp_code, mp_name, municipality_code, municipality_name, district_code, district_name, province_code, province_name)
            VALUES (81505, 'Kanyamazane', 815, 'Mbombela', 32, 'Ehlanzeni', 8, 'MPUMALANGA');
        """)
        # sp_code 81501001 / 1000 = 81501, but main_place_code is set to 81505 -> must fail CHECK
        with self.assertRaises(psycopg2.errors.CheckViolation):
            self.cur.execute("""
                INSERT INTO sub_places (sp_code, sp_name, main_place_code, municipality_code, municipality_name, district_code, district_name, province_code, province_name)
                VALUES (81501001, 'Mismatch SP', 81505, 815, 'Mbombela', 32, 'Ehlanzeni', 8, 'MPUMALANGA');
            """)

    def test_h_dataset_provenance_preservation(self):
        """Test H: Dataset provenance fields preserve distinct dataset/version values."""
        self.cur.execute("""
            INSERT INTO main_places (mp_code, mp_name, municipality_code, municipality_name, district_code, district_name, province_code, province_name, dataset_name, dataset_version)
            VALUES (81501, 'Broedershoek', 815, 'Mbombela', 32, 'Ehlanzeni', 8, 'MPUMALANGA', 'Stats SA 2011 Census', 'v2011.1');
        """)
        self.cur.execute("SELECT dataset_name, dataset_version FROM main_places WHERE mp_code = 81501;")
        row = self.cur.fetchone()
        self.assertEqual(row, ('Stats SA 2011 Census', 'v2011.1'))

    def test_i_source_anomalies_cannot_satisfy_fk(self):
        """Test Step 4: Demonstrate that the two Stats SA orphaned Sub Places fail the FK."""
        # 1. Swellendam NU: SP 11497004 -> derived MP 11497 (missing from MP dataset)
        with self.assertRaises(psycopg2.errors.ForeignKeyViolation):
            self.cur.execute("""
                INSERT INTO sub_places (sp_code, sp_name, main_place_code, municipality_code, municipality_name, district_code, district_name, province_code, province_name)
                VALUES (11497004, 'Swellendam NU', 11497, 114, 'Swellendam', 3, 'Overberg', 1, 'WESTERN CAPE');
            """)
        self.conn.rollback()
        # 2. Prince Albert NU: SP 12332002 -> derived MP 12332 (missing from MP dataset)
        with self.assertRaises(psycopg2.errors.ForeignKeyViolation):
            self.cur.execute("""
                INSERT INTO sub_places (sp_code, sp_name, main_place_code, municipality_code, municipality_name, district_code, district_name, province_code, province_name)
                VALUES (12332002, 'Prince Albert NU', 12332, 123, 'Prince Albert', 5, 'Central Karoo', 1, 'WESTERN CAPE');
            """)

    def test_j_postgresql_bigint_division(self):
        """Test Step 5: Verify PostgreSQL BIGINT division behavior."""
        self.cur.execute("SELECT (81505001::BIGINT / 1000)::INTEGER;")
        val = self.cur.fetchone()[0]
        self.assertEqual(val, 81505)

if __name__ == '__main__':
    unittest.main()
