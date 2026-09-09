import unittest
import sqlite3
import re

SQL_PATH = "supabase/migrations/20260909000001_initial_core_schema.sql"

def adapt_pg_to_sqlite(sql: str) -> str:
    lines = []
    skip = False
    for line in sql.splitlines():
        trimmed = line.strip()
        if trimmed.startswith("CREATE EXTENSION"):
            continue
        if trimmed.startswith("CREATE TYPE"):
            skip = True
            continue
        if trimmed.startswith("CREATE OR REPLACE FUNCTION") or trimmed.startswith("CREATE TRIGGER"):
            skip = True
            continue
        if skip:
            if trimmed.endswith(");") or trimmed.endswith("$$ LANGUAGE plpgsql;") or trimmed.endswith("FUNCTION trg_evidence_records_immutable();"):
                skip = False
            continue
        lines.append(line)
    
    cleaned = "\n".join(lines)
    # Remove Postgres cast syntax first
    cleaned = re.sub(r"'\{\}'::jsonb", "'{}'", cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r'::[a-zA-Z0-9_]+', '', cleaned)
    
    # Convert PostgreSQL types to SQLite equivalents
    cleaned = re.sub(r'\bUUID\b', 'TEXT', cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r'\bTIMESTAMPTZ\b', 'TEXT', cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r'\bJSONB\b', 'TEXT', cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r'\bCHAR\(64\)\b', 'TEXT', cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r'\bNUMERIC\([^)]+\)', 'REAL', cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r'\bDEFAULT gen_random_uuid\(\)', '', cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r'\bDEFAULT CURRENT_TIMESTAMP\b', "DEFAULT (datetime('now'))", cleaned, flags=re.IGNORECASE)
    
    # Replace custom Postgres enums with TEXT
    enum_types = [
        'source_type_enum', 'processing_stage_enum', 'assertion_status_enum',
        'claim_type_enum', 'provenance_role_enum', 'entity_type_enum',
        'relationship_predicate_enum', 'government_sphere_enum', 'sa_province_enum',
        'office_branch_enum', 'constitutional_schedule_enum', 'tender_type_enum',
        'tender_status_enum'
    ]
    for et in enum_types:
        cleaned = re.sub(rf'\b{et}\b', 'TEXT', cleaned)
        
    return cleaned

class SchemaVerificationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        with open(SQL_PATH, "r", encoding="utf-8") as f:
            raw_sql = f.read()
        cls.sqlite_sql = adapt_pg_to_sqlite(raw_sql)
        
    def setUp(self):
        self.conn = sqlite3.connect(":memory:")
        self.conn.execute("PRAGMA foreign_keys = ON;")
        self.conn.executescript(self.sqlite_sql)
        self.cur = self.conn.cursor()

    def tearDown(self):
        self.conn.close()

    def test_a_fk_integrity(self):
        """Test A: An invalid relationship.source_entity_id must fail foreign key check."""
        self.cur.execute("INSERT INTO entities (id, entity_type, canonical_identifier) VALUES ('ent-2', 'office', 'za:office:cfo')")
        with self.assertRaises(sqlite3.IntegrityError):
            self.cur.execute("""
                INSERT INTO relationships (id, source_entity_id, relationship_predicate, target_entity_id, effective_from)
                VALUES ('rel-1', 'ent-nonexistent', 'occupies_office', 'ent-2', '2026-01-01')
            """)

    def test_b_entity_inheritance(self):
        """Test B: An institutions.id referencing a nonexistent entities.id must fail."""
        with self.assertRaises(sqlite3.IntegrityError):
            self.cur.execute("""
                INSERT INTO institutions (id, slug, name, short_name, sphere)
                VALUES ('nonexistent-uuid', 'mp-mbombela', 'City of Mbombela', 'Mbombela', 'local_local')
            """)

    def test_c_relationship_deduplication(self):
        """Test C: Two relationships with identical (source, predicate, target, effective_from) must fail."""
        self.cur.execute("INSERT INTO entities (id, entity_type, canonical_identifier) VALUES ('ent-p1', 'person', 'za:person:p1')")
        self.cur.execute("INSERT INTO entities (id, entity_type, canonical_identifier) VALUES ('ent-o1', 'office', 'za:office:o1')")
        
        self.cur.execute("""
            INSERT INTO relationships (id, source_entity_id, relationship_predicate, target_entity_id, effective_from)
            VALUES ('rel-1', 'ent-p1', 'occupies_office', 'ent-o1', '2026-01-01')
        """)
        
        with self.assertRaises(sqlite3.IntegrityError):
            self.cur.execute("""
                INSERT INTO relationships (id, source_entity_id, relationship_predicate, target_entity_id, effective_from)
                VALUES ('rel-2', 'ent-p1', 'occupies_office', 'ent-o1', '2026-01-01')
            """)

    def test_d_claim_states_and_temporal_constraints(self):
        """Test D: Claim confidence and temporal check constraints must be enforced."""
        with self.assertRaises(sqlite3.IntegrityError):
            self.cur.execute("""
                INSERT INTO claims (id, claim_type, subject_raw_text, predicate, object_raw_text, extraction_confidence)
                VALUES ('c-1', 'relationship_assertion', 'Person A', 'occupies_office', 'CFO', 1.25)
            """)
        with self.assertRaises(sqlite3.IntegrityError):
            self.cur.execute("""
                INSERT INTO claims (id, claim_type, subject_raw_text, predicate, object_raw_text, effective_from, effective_to)
                VALUES ('c-2', 'relationship_assertion', 'Person A', 'occupies_office', 'CFO', '2026-05-01', '2026-04-01')
            """)

    def test_e_evidence_provenance_integrity(self):
        """Test E: relationship_evidence must reject nonexistent relationship, claim, or evidence record."""
        self.cur.execute("INSERT INTO sources (id, slug, name, source_type, base_url) VALUES ('src-1', 'etenders', 'eTenders', 'tender_portal', 'http://etenders.gov.za')")
        self.cur.execute("""
            INSERT INTO evidence_records (id, source_id, origin_url, sha256_payload_hash, payload_storage_uri, mime_type, byte_size)
            VALUES ('ev-1', 'src-1', 'http://etenders.gov.za/1', 'a0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef', 's3://bucket/1', 'application/pdf', 1024)
        """)
        
        with self.assertRaises(sqlite3.IntegrityError):
            self.cur.execute("""
                INSERT INTO relationship_evidence (id, relationship_id, claim_id, evidence_record_id, verbatim_excerpt)
                VALUES ('re-1', 'nonexistent-rel', 'nonexistent-claim', 'ev-1', 'Excerpt')
            """)

    def test_f_historical_preservation(self):
        """Test F: Superseded claim remains queryable and linked without deletion."""
        self.cur.execute("""
            INSERT INTO claims (id, claim_type, subject_raw_text, predicate, object_raw_text, assertion_status)
            VALUES ('c-old', 'relationship_assertion', 'Person W', 'occupies_office', 'CFO', 'substantiated')
        """)
        self.cur.execute("""
            INSERT INTO claims (id, claim_type, subject_raw_text, predicate, object_raw_text, assertion_status, superseded_by_claim_id)
            VALUES ('c-new', 'relationship_assertion', 'Person X', 'occupies_office', 'CFO', 'substantiated', NULL)
        """)
        self.cur.execute("UPDATE claims SET assertion_status = 'superseded', superseded_by_claim_id = 'c-new' WHERE id = 'c-old'")
        
        self.cur.execute("SELECT id, assertion_status, superseded_by_claim_id FROM claims WHERE id = 'c-old'")
        row = self.cur.fetchone()
        self.assertEqual(row, ('c-old', 'superseded', 'c-new'))

if __name__ == '__main__':
    unittest.main()
