-- =============================================================================
-- Migration: 20260909000001_initial_core_schema.sql
-- Description: Core Schema v0.4.1 for SA Government Intelligence Platform
-- Architecture: Evidence Layer, Canonical Graph, Domain Entities, Authority Engine
-- Invariants: Strict FKs, No Polymorphic Relationships, Immutable Evidence, 
--             Two-Vector Claim Statuses, Contextual Authority Precedence.
-- =============================================================================

-- Enable pgcrypto for UUID generation if not already active
CREATE EXTENSION IF NOT EXISTS "pgcrypto";

-- -----------------------------------------------------------------------------
-- 1. ENUMS & DOMAIN TYPES
-- -----------------------------------------------------------------------------

CREATE TYPE source_type_enum AS ENUM (
    'gazette',
    'tender_portal',
    'municipal_site',
    'auditor_general_report',
    'national_treasury_api',
    'council_minutes'
);

CREATE TYPE processing_stage_enum AS ENUM (
    'extracted',
    'normalized',
    'resolved',
    'validated',
    'canonicalized'
);

CREATE TYPE assertion_status_enum AS ENUM (
    'unverified',
    'substantiated',
    'contested',
    'superseded',
    'revoked'
);

CREATE TYPE claim_type_enum AS ENUM (
    'entity_existence',
    'attribute_assertion',
    'relationship_assertion',
    'temporal_status'
);

CREATE TYPE provenance_role_enum AS ENUM (
    'primary_authorizing',
    'corroborating',
    'superseding',
    'contesting'
);

CREATE TYPE entity_type_enum AS ENUM (
    'institution',
    'office',
    'person',
    'function',
    'ward',
    'tender',
    'award',
    'supplier'
);

CREATE TYPE relationship_predicate_enum AS ENUM (
    'oversees_institution',
    'houses_office',
    'occupies_office',
    'responsible_for_function',
    'contains_ward',
    'issued_tender',
    'stipulates_requirement',
    'awarded_contract',
    'recipient_supplier',
    'delegates_procurement_authority'
);

CREATE TYPE government_sphere_enum AS ENUM (
    'national',
    'provincial',
    'local_metro',
    'local_district',
    'local_local',
    'chapter_9',
    'soe'
);

CREATE TYPE sa_province_enum AS ENUM (
    'EC', 'FS', 'GP', 'KZN', 'LP', 'MP', 'NC', 'NW', 'WC'
);

CREATE TYPE office_branch_enum AS ENUM (
    'political',
    'administrative',
    'judicial',
    'statutory_oversight'
);

CREATE TYPE constitutional_schedule_enum AS ENUM (
    'schedule_4a',
    'schedule_4b',
    'schedule_5a',
    'schedule_5b',
    'national_exclusive'
);

CREATE TYPE tender_type_enum AS ENUM (
    'rfq',
    'rfp',
    'eoi',
    'formal_tender',
    'emergency_procurement'
);

CREATE TYPE tender_status_enum AS ENUM (
    'open',
    'under_evaluation',
    'awarded',
    'cancelled',
    'expired'
);

-- -----------------------------------------------------------------------------
-- 2. CANONICAL ENTITY REGISTRY (UNIVERSAL NODE SUBSTRATE)
-- -----------------------------------------------------------------------------

CREATE TABLE entities (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    entity_type entity_type_enum NOT NULL,
    canonical_identifier TEXT NOT NULL UNIQUE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_entities_type ON entities(entity_type);
CREATE INDEX idx_entities_identifier ON entities(canonical_identifier);

-- -----------------------------------------------------------------------------
-- 3. EVIDENCE LAYER (IMMUTABLE CAPTURE & CONTEXTUAL AUTHORITY)
-- -----------------------------------------------------------------------------

CREATE TABLE sources (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    slug TEXT NOT NULL UNIQUE,
    name TEXT NOT NULL,
    source_type source_type_enum NOT NULL,
    base_url TEXT NOT NULL,
    polling_cadence_minutes INTEGER NOT NULL DEFAULT 360,
    is_active BOOLEAN NOT NULL DEFAULT true,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE evidence_records (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    source_id UUID NOT NULL REFERENCES sources(id) ON DELETE RESTRICT,
    origin_url TEXT NOT NULL,
    captured_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    sha256_payload_hash CHAR(64) NOT NULL,
    payload_storage_uri TEXT NOT NULL,
    mime_type TEXT NOT NULL,
    byte_size INTEGER NOT NULL CHECK (byte_size >= 0),
    retrieval_metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
    extraction_metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
    raw_extracted_text TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_evidence_records_source ON evidence_records(source_id);
CREATE INDEX idx_evidence_records_hash ON evidence_records(sha256_payload_hash);
CREATE INDEX idx_evidence_records_captured ON evidence_records(captured_at);

-- Minimal Immutability Protection Trigger: evidence_records is append-only
CREATE OR REPLACE FUNCTION trg_evidence_records_immutable()
RETURNS TRIGGER AS $$
BEGIN
    RAISE EXCEPTION 'evidence_records rows are immutable and cannot be updated or deleted.';
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trg_prevent_evidence_records_mutation
BEFORE UPDATE OR DELETE ON evidence_records
FOR EACH ROW EXECUTE FUNCTION trg_evidence_records_immutable();

CREATE TABLE authority_rules (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    claim_predicate relationship_predicate_enum NOT NULL,
    source_type source_type_enum NOT NULL,
    authority_rank INTEGER NOT NULL CHECK (authority_rank > 0),
    can_substantiate_alone BOOLEAN NOT NULL DEFAULT false,
    can_supersede_prior BOOLEAN NOT NULL DEFAULT false,
    requires_corroboration BOOLEAN NOT NULL DEFAULT false,
    statutory_instrument TEXT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT uq_authority_rule UNIQUE (claim_predicate, source_type, statutory_instrument)
);

CREATE INDEX idx_authority_rules_lookup ON authority_rules(claim_predicate, source_type);

-- -----------------------------------------------------------------------------
-- 4. CLAIMS & ASSERTION STORE (TWO-VECTOR LIFECYCLE)
-- -----------------------------------------------------------------------------

CREATE TABLE claims (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    claim_type claim_type_enum NOT NULL,
    subject_raw_text TEXT NOT NULL,
    subject_canonical_id UUID REFERENCES entities(id) ON DELETE RESTRICT,
    predicate relationship_predicate_enum NOT NULL,
    object_raw_text TEXT NOT NULL,
    object_canonical_id UUID REFERENCES entities(id) ON DELETE RESTRICT,
    object_value JSONB NOT NULL DEFAULT '{}'::jsonb,
    effective_from DATE,
    effective_to DATE,
    extraction_confidence NUMERIC(4,3) CHECK (extraction_confidence >= 0.000 AND extraction_confidence <= 1.000),
    resolution_confidence NUMERIC(4,3) CHECK (resolution_confidence >= 0.000 AND resolution_confidence <= 1.000),
    processing_stage processing_stage_enum NOT NULL DEFAULT 'extracted',
    assertion_status assertion_status_enum NOT NULL DEFAULT 'unverified',
    superseded_by_claim_id UUID REFERENCES claims(id) ON DELETE RESTRICT,
    contested_by_claim_id UUID REFERENCES claims(id) ON DELETE RESTRICT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT chk_claim_dates CHECK (effective_to IS NULL OR effective_from IS NULL OR effective_to >= effective_from)
);

CREATE INDEX idx_claims_subject_canonical ON claims(subject_canonical_id);
CREATE INDEX idx_claims_object_canonical ON claims(object_canonical_id);
CREATE INDEX idx_claims_predicate ON claims(predicate);
CREATE INDEX idx_claims_status ON claims(assertion_status, processing_stage);

CREATE TABLE evidence_claims (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    evidence_id UUID NOT NULL REFERENCES evidence_records(id) ON DELETE RESTRICT,
    claim_id UUID NOT NULL REFERENCES claims(id) ON DELETE RESTRICT,
    excerpt TEXT NOT NULL,
    locator JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT uq_evidence_claim UNIQUE (evidence_id, claim_id)
);

CREATE INDEX idx_evidence_claims_claim ON evidence_claims(claim_id);
CREATE INDEX idx_evidence_claims_evidence ON evidence_claims(evidence_id);

-- -----------------------------------------------------------------------------
-- 5. CANONICAL RELATIONSHIPS (FIRST-CLASS EDGES & STRICT DEDUPLICATION)
-- -----------------------------------------------------------------------------

CREATE TABLE relationships (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    source_entity_id UUID NOT NULL REFERENCES entities(id) ON DELETE RESTRICT,
    relationship_predicate relationship_predicate_enum NOT NULL,
    target_entity_id UUID NOT NULL REFERENCES entities(id) ON DELETE RESTRICT,
    relationship_attributes JSONB NOT NULL DEFAULT '{}'::jsonb,
    effective_from DATE NOT NULL,
    effective_to DATE,
    observed_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT chk_relationship_dates CHECK (effective_to IS NULL OR effective_to >= effective_from),
    CONSTRAINT uq_relationship_identity UNIQUE (source_entity_id, relationship_predicate, target_entity_id, effective_from)
);

CREATE INDEX idx_relationships_source ON relationships(source_entity_id);
CREATE INDEX idx_relationships_target ON relationships(target_entity_id);
CREATE INDEX idx_relationships_predicate ON relationships(relationship_predicate);
CREATE INDEX idx_relationships_temporal ON relationships(effective_from, effective_to);

CREATE TABLE relationship_evidence (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    relationship_id UUID NOT NULL REFERENCES relationships(id) ON DELETE CASCADE,
    claim_id UUID NOT NULL REFERENCES claims(id) ON DELETE RESTRICT,
    evidence_record_id UUID NOT NULL REFERENCES evidence_records(id) ON DELETE RESTRICT,
    provenance_role provenance_role_enum NOT NULL DEFAULT 'primary_authorizing',
    verbatim_excerpt TEXT NOT NULL,
    locator JSONB NOT NULL DEFAULT '{}'::jsonb,
    adjudication_rule_id UUID REFERENCES authority_rules(id) ON DELETE RESTRICT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_rel_evidence_rel_id ON relationship_evidence(relationship_id);
CREATE INDEX idx_rel_evidence_claim_id ON relationship_evidence(claim_id);
CREATE INDEX idx_rel_evidence_evidence_id ON relationship_evidence(evidence_record_id);

CREATE TABLE entity_evidence (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    entity_id UUID NOT NULL REFERENCES entities(id) ON DELETE CASCADE,
    claim_id UUID NOT NULL REFERENCES claims(id) ON DELETE RESTRICT,
    evidence_record_id UUID NOT NULL REFERENCES evidence_records(id) ON DELETE RESTRICT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT uq_entity_evidence UNIQUE (entity_id, claim_id, evidence_record_id)
);

CREATE INDEX idx_entity_evidence_entity ON entity_evidence(entity_id);

-- -----------------------------------------------------------------------------
-- 6. DOMAIN ENTITY TABLES (INHERITING ENTITIES.ID AS PRIMARY KEY)
-- -----------------------------------------------------------------------------

CREATE TABLE institutions (
    id UUID PRIMARY KEY REFERENCES entities(id) ON DELETE RESTRICT,
    slug TEXT NOT NULL UNIQUE,
    name TEXT NOT NULL,
    short_name TEXT NOT NULL,
    sphere government_sphere_enum NOT NULL,
    province sa_province_enum,
    demarcation_code TEXT,
    mandate_summary TEXT,
    contact_details JSONB NOT NULL DEFAULT '{}'::jsonb,
    last_observed_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_institutions_sphere ON institutions(sphere);
CREATE INDEX idx_institutions_province ON institutions(province);
CREATE INDEX idx_institutions_demarcation ON institutions(demarcation_code);

CREATE TABLE offices (
    id UUID PRIMARY KEY REFERENCES entities(id) ON DELETE RESTRICT,
    title TEXT NOT NULL,
    branch office_branch_enum NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE people (
    id UUID PRIMARY KEY REFERENCES entities(id) ON DELETE RESTRICT,
    full_name TEXT NOT NULL,
    public_profile_url TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE institution_functions (
    id UUID PRIMARY KEY REFERENCES entities(id) ON DELETE RESTRICT,
    category TEXT NOT NULL,
    constitutional_schedule constitutional_schedule_enum NOT NULL,
    escalation_level INTEGER NOT NULL CHECK (escalation_level >= 1 AND escalation_level <= 4),
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE wards (
    id UUID PRIMARY KEY REFERENCES entities(id) ON DELETE RESTRICT,
    demarcation_code TEXT NOT NULL,
    ward_number INTEGER NOT NULL CHECK (ward_number > 0),
    boundaries_geojson JSONB,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_wards_demarcation ON wards(demarcation_code);

CREATE TABLE tenders (
    id UUID PRIMARY KEY REFERENCES entities(id) ON DELETE RESTRICT,
    native_bid_number TEXT NOT NULL,
    canonical_urn TEXT NOT NULL UNIQUE,
    title TEXT NOT NULL,
    description TEXT,
    tender_type tender_type_enum NOT NULL,
    category TEXT NOT NULL,
    cidb_grading TEXT,
    estimated_value_zar NUMERIC(15,2) CHECK (estimated_value_zar IS NULL OR estimated_value_zar >= 0),
    publish_date TIMESTAMPTZ NOT NULL,
    closing_date TIMESTAMPTZ NOT NULL,
    current_status tender_status_enum NOT NULL DEFAULT 'open',
    last_observed_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT chk_tender_dates CHECK (closing_date >= publish_date)
);

CREATE INDEX idx_tenders_status ON tenders(current_status);
CREATE INDEX idx_tenders_closing ON tenders(closing_date);

CREATE TABLE awards (
    id UUID PRIMARY KEY REFERENCES entities(id) ON DELETE RESTRICT,
    awarded_amount_zar NUMERIC(15,2) NOT NULL CHECK (awarded_amount_zar >= 0),
    award_date DATE NOT NULL,
    contract_duration_months INTEGER CHECK (contract_duration_months IS NULL OR contract_duration_months > 0),
    bbbee_points_scored NUMERIC(5,2) CHECK (bbbee_points_scored IS NULL OR (bbbee_points_scored >= 0 AND bbbee_points_scored <= 100)),
    price_points_scored NUMERIC(5,2) CHECK (price_points_scored IS NULL OR (price_points_scored >= 0 AND price_points_scored <= 100)),
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE suppliers (
    id UUID PRIMARY KEY REFERENCES entities(id) ON DELETE RESTRICT,
    legal_name TEXT NOT NULL,
    trading_name TEXT,
    registration_number TEXT,
    csd_number TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_suppliers_csd ON suppliers(csd_number);
CREATE INDEX idx_suppliers_reg ON suppliers(registration_number);
