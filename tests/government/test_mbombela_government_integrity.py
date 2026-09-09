import unittest
import psycopg2
from scripts.government.ingest_mbombela_government import (
    ingest_mbombela_governance,
    MBOMBELA_INSTITUTION_URN
)

PG_CONFIG = {
    "dbname": "gov_intel_test",
    "user": "postgres",
    "host": "127.0.0.1",
    "port": 54339
}

class MbombelaGovernanceIntegrityTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.conn = psycopg2.connect(**PG_CONFIG)
        cls.conn.set_client_encoding('UTF8')
        # Ensure data is ingested
        ingest_mbombela_governance(cls.conn)

    @classmethod
    def tearDownClass(cls):
        cls.conn.close()

    def test_a_institution_existence_and_canonical_entity(self):
        """Test A: Mbombela institution exists exactly once and references its canonical entity."""
        with self.conn.cursor() as cur:
            cur.execute("SELECT id, entity_type, canonical_identifier FROM entities WHERE canonical_identifier = %s;", (MBOMBELA_INSTITUTION_URN,))
            ent = cur.fetchone()
            self.assertIsNotNone(ent)
            ent_id = ent[0]
            self.assertEqual(ent[1], 'institution')

            cur.execute("SELECT id, slug, name, demarcation_code, province, sphere FROM institutions WHERE id = %s;", (ent_id,))
            inst = cur.fetchone()
            self.assertIsNotNone(inst)
            self.assertEqual(inst[1], 'mp-mbombela-lm')
            self.assertEqual(inst[2], 'City of Mbombela Local Municipality')
            self.assertEqual(inst[3], 'MP322')
            self.assertEqual(inst[4], 'MP')
            self.assertEqual(inst[5], 'local_local')

            # Ensure exactly 1 Mbombela institution
            cur.execute("SELECT COUNT(*) FROM institutions WHERE slug = 'mp-mbombela-lm';")
            self.assertEqual(cur.fetchone()[0], 1)

    def test_b_complete_evidence_chain_and_provenance(self):
        """Test B: Every canonical governance claim and relationship has an unbroken evidence chain."""
        with self.conn.cursor() as cur:
            # Check claims have valid evidence
            cur.execute("""
                SELECT c.id, c.predicate, c.processing_stage, c.assertion_status,
                       e.sha256_payload_hash, s.name
                FROM claims c
                JOIN relationship_evidence re ON re.claim_id = c.id
                JOIN evidence_records e ON e.id = re.evidence_record_id
                JOIN sources s ON s.id = e.source_id
                WHERE c.subject_raw_text = 'City of Mbombela Local Municipality';
            """)
            ev_chains = cur.fetchall()
            self.assertEqual(len(ev_chains), 7, "All 7 claims must have complete evidence chain")
            for row in ev_chains:
                self.assertEqual(row[2], 'canonicalized')
                self.assertEqual(row[3], 'substantiated')
                self.assertEqual(len(row[4]), 64, "SHA-256 hash must be 64 characters")
                self.assertTrue(len(row[5]) > 0, "Source name must be populated")

    def test_c_first_class_functions_relationships(self):
        """Test C: Functions are linked via first-class responsible_for_function relationships."""
        with self.conn.cursor() as cur:
            cur.execute("""
                SELECT f.category, f.constitutional_schedule, r.relationship_predicate, re.provenance_role
                FROM institutions i
                JOIN relationships r ON r.source_entity_id = i.id
                JOIN institution_functions f ON f.id = r.target_entity_id
                JOIN relationship_evidence re ON re.relationship_id = r.id
                WHERE i.slug = 'mp-mbombela-lm'
                ORDER BY f.category ASC;
            """)
            funcs = cur.fetchall()
            self.assertEqual(len(funcs), 4, "Expected exactly 4 statutory functions")
            categories = [f[0] for f in funcs]
            self.assertIn("Potable Water Supply & Sanitation", categories)
            self.assertIn("Electricity Reticulation", categories)
            self.assertIn("Municipal Roads & Pothole Maintenance", categories)
            self.assertIn("Refuse Removal & Solid Waste Disposal", categories)

            for f in funcs:
                self.assertEqual(f[2], 'responsible_for_function')
                self.assertEqual(f[3], 'primary_authorizing')

    def test_d_first_class_offices_and_no_direct_person_on_institution(self):
        """Test D: Offices belong to institution via houses_office; zero people directly on institution."""
        with self.conn.cursor() as cur:
            cur.execute("""
                SELECT o.title, o.branch, r.relationship_predicate
                FROM institutions i
                JOIN relationships r ON r.source_entity_id = i.id
                JOIN offices o ON o.id = r.target_entity_id
                WHERE i.slug = 'mp-mbombela-lm'
                ORDER BY o.title ASC;
            """)
            offices = cur.fetchall()
            self.assertEqual(len(offices), 3, "Expected 3 statutory offices")
            titles = [o[0] for o in offices]
            self.assertIn("Municipal Manager", titles)
            self.assertIn("Executive Mayor", titles)
            self.assertIn("Speaker of Council", titles)

            # Invariant: No person directly attached to institution
            cur.execute("""
                SELECT COUNT(*)
                FROM relationships r
                JOIN entities e ON e.id = r.target_entity_id OR e.id = r.source_entity_id
                WHERE e.entity_type = 'person';
            """)
            self.assertEqual(cur.fetchone()[0], 0, "No person entity should be attached without appointment evidence")

    def test_e_authority_rules_exercised(self):
        """Test E: All relationship evidence records link to valid authority rules."""
        with self.conn.cursor() as cur:
            cur.execute("""
                SELECT re.id, ar.claim_predicate, ar.authority_rank, ar.statutory_instrument
                FROM relationship_evidence re
                JOIN authority_rules ar ON ar.id = re.adjudication_rule_id;
            """)
            rules_used = cur.fetchall()
            self.assertEqual(len(rules_used), 7)
            for r in rules_used:
                self.assertEqual(r[2], 1, "Statutory instruments must have rank 1")
                self.assertTrue(len(r[3]) > 0)

    def test_f_geographic_layer_remains_independent_and_unmutated(self):
        """Test F: Geographic reference layer remains completely untouched and isolated."""
        with self.conn.cursor() as cur:
            cur.execute("SELECT COUNT(*) FROM main_places;")
            self.assertEqual(cur.fetchone()[0], 3109)

            cur.execute("SELECT COUNT(*) FROM sub_places;")
            self.assertEqual(cur.fetchone()[0], 21241)

            # Check Mbombela geographic places still resolve exactly to 25 / 108
            cur.execute("SELECT COUNT(*) FROM main_places WHERE municipality_code = 815;")
            self.assertEqual(cur.fetchone()[0], 25)

            cur.execute("SELECT COUNT(*) FROM sub_places WHERE municipality_code = 815;")
            self.assertEqual(cur.fetchone()[0], 108)

            # Ensure zero FKs from main_places or sub_places to entities or institutions
            cur.execute("""
                SELECT ccu.table_name
                FROM information_schema.table_constraints tc
                JOIN information_schema.constraint_column_usage ccu ON ccu.constraint_name = tc.constraint_name
                WHERE tc.constraint_type = 'FOREIGN KEY'
                  AND tc.table_name IN ('main_places', 'sub_places')
                  AND ccu.table_name NOT IN ('main_places', 'sub_places');
            """)
            self.assertEqual(len(cur.fetchall()), 0)

    def test_g_idempotent_ingestion(self):
        """Test G: Re-running governance ingestion produces no duplicate entities or relationships."""
        report = ingest_mbombela_governance(self.conn)
        self.assertEqual(report["institutions_count"], 1)
        self.assertEqual(report["offices_count"], 3)
        self.assertEqual(report["functions_count"], 4)
        self.assertEqual(report["relationships_count"], 7)

        with self.conn.cursor() as cur:
            cur.execute("SELECT COUNT(*) FROM institutions WHERE slug = 'mp-mbombela-lm';")
            self.assertEqual(cur.fetchone()[0], 1)
            cur.execute("SELECT COUNT(*) FROM relationships;")
            self.assertEqual(cur.fetchone()[0], 7)

if __name__ == '__main__':
    unittest.main()
