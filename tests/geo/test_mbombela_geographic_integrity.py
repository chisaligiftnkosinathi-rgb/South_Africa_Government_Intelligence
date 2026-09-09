import unittest
import psycopg2
from scripts.geo.verify_mbombela_pilot import (
    verify_global_integrity,
    get_municipal_summary,
    find_municipality_code_by_name
)

PG_CONFIG = {
    "dbname": "gov_intel_test",
    "user": "postgres",
    "host": "127.0.0.1",
    "port": 54339
}

class MbombelaGeographicIntegrityTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.conn = psycopg2.connect(**PG_CONFIG)
        cls.conn.set_client_encoding('UTF8')

    @classmethod
    def tearDownClass(cls):
        cls.conn.close()

    def test_a_municipality_identity_resolution(self):
        """Test A: Municipality identity resolves deterministically from source data."""
        matches = find_municipality_code_by_name(self.conn, "mbombela")
        self.assertEqual(len(matches), 1)
        code, name = matches[0]
        self.assertEqual(code, 815)
        self.assertEqual(name, "Mbombela")

    def test_b_municipality_summary(self):
        """Test B: Summary returns exact administrative hierarchy for Mbombela."""
        summary = get_municipal_summary(self.conn, 815)
        self.assertIsNotNone(summary)
        self.assertEqual(summary["municipality_code"], 815)
        self.assertEqual(summary["municipality_name"], "Mbombela")
        self.assertEqual(summary["district_code"], 32)
        self.assertEqual(summary["district_name"], "Ehlanzeni")
        self.assertEqual(summary["province_code"], 8)
        self.assertEqual(summary["province_name"], "MPUMALANGA")

    def test_c_main_place_count_for_mbombela(self):
        """Test C: Mbombela contains exactly 25 Main Places and 108 Sub Places."""
        summary = get_municipal_summary(self.conn, 815)
        self.assertEqual(summary["main_place_count"], 25)
        self.assertEqual(summary["sub_place_count"], 108)

    def test_d_deterministic_ordering(self):
        """Test D: Main Places and Sub Places are ordered deterministically by code."""
        summary = get_municipal_summary(self.conn, 815)
        mp_codes = [mp["mp_code"] for mp in summary["main_places"]]
        self.assertEqual(mp_codes, sorted(mp_codes))
        self.assertEqual(mp_codes[0], 81501)
        self.assertEqual(mp_codes[-1], 81525)

        sp_codes = [sp["sp_code"] for sp in summary["sub_places"]]
        self.assertEqual(sp_codes, sorted(sp_codes))
        self.assertEqual(sp_codes[0], 81501000)

    def test_e_sub_place_fk_integrity(self):
        """Test E: All 21,241 Sub Places reference valid Main Place codes."""
        integrity = verify_global_integrity(self.conn)
        self.assertTrue(integrity["checks"]["sub_place_fk_integrity"]["passed"])
        self.assertEqual(integrity["checks"]["sub_place_fk_integrity"]["unmatched_count"], 0)

    def test_f_sp_code_parent_arithmetic_consistency(self):
        """Test F: SP_CODE // 1000 == main_place_code for all loaded Sub Places."""
        integrity = verify_global_integrity(self.conn)
        self.assertTrue(integrity["checks"]["parent_arithmetic_match"]["passed"])
        self.assertEqual(integrity["checks"]["parent_arithmetic_match"]["mismatch_count"], 0)

    def test_g_no_duplicate_geographic_codes(self):
        """Test G: No duplicate MP_CODE or SP_CODE exists in loaded tables."""
        integrity = verify_global_integrity(self.conn)
        self.assertTrue(integrity["checks"]["main_place_uniqueness"]["passed"])
        self.assertTrue(integrity["checks"]["sub_place_uniqueness"]["passed"])

    def test_h_no_blank_names_and_clean_administrative_consistency(self):
        """Test H: No blank names and Main Places/Sub Places have uniform admin hierarchy."""
        integrity = verify_global_integrity(self.conn)
        self.assertTrue(integrity["checks"]["non_blank_names"]["passed"])
        self.assertTrue(integrity["checks"]["main_place_admin_consistency"]["passed"])
        self.assertTrue(integrity["checks"]["sub_place_parent_admin_agreement"]["passed"])

    def test_i_province_code_validity(self):
        """Test I: All province codes are between 1 and 9."""
        integrity = verify_global_integrity(self.conn)
        self.assertTrue(integrity["checks"]["province_code_range"]["passed"])

    def test_j_global_row_counts(self):
        """Test J: Global counts strictly match 3,109 Main Places and 21,241 Sub Places."""
        integrity = verify_global_integrity(self.conn)
        self.assertTrue(integrity["checks"]["global_counts"]["passed"])
        self.assertEqual(integrity["checks"]["global_counts"]["main_places_count"], 3109)
        self.assertEqual(integrity["checks"]["global_counts"]["sub_places_count"], 21241)

    def test_k_source_anomalies_remain_excluded(self):
        """Test K: Quarantined anomalies (11497004, 12332002) remain strictly excluded from DB."""
        integrity = verify_global_integrity(self.conn)
        self.assertTrue(integrity["checks"]["quarantine_status"]["passed"])
        self.assertEqual(integrity["checks"]["quarantine_status"]["leaked_count"], 0)

if __name__ == '__main__':
    unittest.main()
