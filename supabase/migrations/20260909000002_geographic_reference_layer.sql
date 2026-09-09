-- =============================================================================
-- Migration: 20260909000002_geographic_reference_layer.sql
-- Description: Geographic Reference Layer (Stats SA Main Places & Sub Places)
-- Architecture: Isolated geographic reference data, completely decoupled from
--               the governance entity graph (no FKs to entities/institutions).
-- Invariants: Strict geographic hierarchy, unique place codes, code range checks,
--             provenance fields, and non-destructive dataset versioning.
-- =============================================================================

-- Enable pgcrypto for UUID generation if not already active
CREATE EXTENSION IF NOT EXISTS "pgcrypto";

-- -----------------------------------------------------------------------------
-- 1. MAIN PLACES (STATS SA CENSUS MAIN PLACE LOOKUP)
-- -----------------------------------------------------------------------------

CREATE TABLE main_places (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    mp_code INTEGER NOT NULL UNIQUE,
    mp_name TEXT NOT NULL CHECK (length(trim(mp_name)) > 0),
    municipality_code INTEGER NOT NULL CHECK (municipality_code > 0),
    municipality_name TEXT NOT NULL CHECK (length(trim(municipality_name)) > 0),
    district_code INTEGER NOT NULL CHECK (district_code > 0),
    district_name TEXT NOT NULL CHECK (length(trim(district_name)) > 0),
    province_code INTEGER NOT NULL CHECK (province_code >= 1 AND province_code <= 9),
    province_name TEXT NOT NULL CHECK (length(trim(province_name)) > 0),
    dataset_name TEXT NOT NULL DEFAULT 'Stats SA Main Place Lookup Table',
    dataset_version TEXT,
    observed_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT chk_mp_code_positive CHECK (mp_code > 0)
);

CREATE INDEX idx_main_places_mp_code ON main_places(mp_code);
CREATE INDEX idx_main_places_mun_code ON main_places(municipality_code);
CREATE INDEX idx_main_places_dist_code ON main_places(district_code);
CREATE INDEX idx_main_places_prov_code ON main_places(province_code);
CREATE INDEX idx_main_places_name ON main_places(mp_name);

-- -----------------------------------------------------------------------------
-- 2. SUB PLACES (STATS SA CENSUS SUB PLACE LOOKUP)
-- -----------------------------------------------------------------------------

CREATE TABLE sub_places (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    sp_code BIGINT NOT NULL UNIQUE,
    sp_name TEXT NOT NULL CHECK (length(trim(sp_name)) > 0),
    main_place_code INTEGER NOT NULL REFERENCES main_places(mp_code) ON DELETE RESTRICT,
    municipality_code INTEGER NOT NULL CHECK (municipality_code > 0),
    municipality_name TEXT NOT NULL CHECK (length(trim(municipality_name)) > 0),
    district_code INTEGER NOT NULL CHECK (district_code > 0),
    district_name TEXT NOT NULL CHECK (length(trim(district_name)) > 0),
    province_code INTEGER NOT NULL CHECK (province_code >= 1 AND province_code <= 9),
    province_name TEXT NOT NULL CHECK (length(trim(province_name)) > 0),
    dataset_name TEXT NOT NULL DEFAULT 'Stats SA Sub Place Lookup Table',
    dataset_version TEXT,
    observed_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT chk_sp_code_positive CHECK (sp_code > 0),
    CONSTRAINT chk_sp_parent_code_match CHECK (main_place_code = (sp_code / 1000))
);

CREATE INDEX idx_sub_places_sp_code ON sub_places(sp_code);
CREATE INDEX idx_sub_places_mp_code ON sub_places(main_place_code);
CREATE INDEX idx_sub_places_mun_code ON sub_places(municipality_code);
CREATE INDEX idx_sub_places_dist_code ON sub_places(district_code);
CREATE INDEX idx_sub_places_prov_code ON sub_places(province_code);
CREATE INDEX idx_sub_places_name ON sub_places(sp_name);
