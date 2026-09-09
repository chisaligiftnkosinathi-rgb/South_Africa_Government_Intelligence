# Database Schema & Migration Guide

This directory contains the canonical PostgreSQL/Supabase database migrations for the South African Government Intelligence & Civic Platform.

---

## 1. Migration Order & Execution

| Order | Migration File | Scope & Purpose |
| :--- | :--- | :--- |
| **01** | `20260909000001_initial_core_schema.sql` | **Core Governance Schema v0.4.1**: Entity Registry, Evidence Layer, Claim Store, First-Class Canonical Relationships, Domain Entities (`institutions`, `offices`, `people`, `institution_functions`, `wards`, `tenders`, `awards`, `suppliers`), and Authority Rules Engine. |
| **02** | `20260909000002_geographic_reference_layer.sql` | **Geographic Reference Layer**: Stats SA Census `main_places` and `sub_places`. Completely decoupled from the governance graph (zero FKs to entities or institutions). |

### To Run in Supabase:
* Using Supabase CLI:
  ```bash
  supabase migration up
  ```
* Direct execution on PostgreSQL / Supabase SQL Editor:
  Execute migrations sequentially in alphabetical order.

---

## 2. Table Dependency & Architecture Separation

The database deliberately isolates the **Governance Graph** from the **Geographic Reference Layer**:

```text
========================================
1. GOVERNANCE GRAPH LAYER (Migration 01)
========================================
sources ──> evidence_records ──> claims
                                    │
    ┌───────────────────────────────┴──────────────────────────────┐
    ▼                                                              ▼
entities (PK substrate)                                      authority_rules
    │                                                              │
    ├─► [Domain Entities]                                          │
    │   (institutions, offices, people, functions, wards, etc.)    │
    │                                                              │
    └─► relationships ◄── relationship_evidence ◄──────────────────┘

=============================================
2. GEOGRAPHIC REFERENCE LAYER (Migration 02)
=============================================
main_places (Stats SA MP_CODE)
    │ (1:N FK via mp_code)
    ▼
sub_places (Stats SA SP_CODE)

* INVARIANT: No foreign keys exist between the Geographic Reference Layer
  and the Governance Graph. They are connected exclusively through explicit
  cross-reference queries or resolution models.
```

---

## 3. Running Verification Tests Locally

The test suite in `tests/schema/` tests all invariants across both layers:

```bash
# Test Core Governance Schema invariants (FKs, inheritance, deduplication, historical claims)
python tests/schema/test_schema_invariants.py -v

# Test Geographic Reference Layer invariants (place uniqueness, code checks, decoupling)
python tests/schema/test_geographic_schema.py -v

# Validate source Stats SA Excel data files without inserting into DB
python tests/schema/validate_stats_sa_source_files.py
```
