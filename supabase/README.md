# Database Schema & Migration Guide (v0.4.1)

This directory contains the canonical PostgreSQL/Supabase database migrations for the South African Government Intelligence & Civic Platform.

---

## 1. Migration Order & Execution

| Order | Migration File | Scope & Purpose |
| :--- | :--- | :--- |
| **01** | `20260909000001_initial_core_schema.sql` | Core Schema v0.4.1: Custom Enums, Entity Registry, Evidence Layer, Claim Store, First-Class Canonical Relationships, Domain Entities, Authority Rules Engine, and Invariant Constraints. |

### To Run in Supabase:
* Using Supabase CLI:
  ```bash
  supabase db reset
  # or
  supabase migration up
  ```
* Direct execution on PostgreSQL / Supabase SQL Editor:
  Execute `supabase/migrations/20260909000001_initial_core_schema.sql`.

---

## 2. Table Dependency & Referential Architecture

The schema adheres to strict, topological foreign-key hierarchies:

```text
               ┌───────────────┐
               │    sources    │
               └───────┬───────┘
                       │ (1:N)
                       ▼
               ┌───────────────────────┐
               │   evidence_records    │ ◄── [Append-Only Trigger]
               └───────┬───────────────┘
                       │
         ┌─────────────┴──────────────┐
         │                            │
         ▼                            ▼
  ┌──────────────┐             ┌──────────────┐
  │   claims     │             │ authority_   │
  └──────┬───────┘             │    rules     │
         │                     └──────┬───────┘
         ├────────────────────────┐   │
         ▼                        ▼   ▼
  ┌──────────────┐             ┌───────────────────────┐
  │   entities   │             │ relationship_evidence │
  └──────┬───────┘             └───────────▲───────────┘
         │ (Inheritance PKs)               │ (1:N FK)
    ┌────┴────────────────────────┐        │
    ▼                             ▼        │
[Domain Tables]             ┌──────────────┴────────┐
(institutions, offices,     │     relationships     │
 people, functions, wards,  └───────────────────────┘
 tenders, awards, suppliers)
```

---

## 3. Major Invariants Implemented

1. **No Polymorphic Foreign Keys**:
   - Universal graph edges are represented in `relationships`.
   - `source_entity_id` and `target_entity_id` strictly reference `entities(id)`.
   - `relationship_evidence.relationship_id` strictly references `relationships(id)`.
2. **Entity Inheritance**:
   - Domain entity tables (`institutions`, `offices`, `people`, `institution_functions`, `wards`, `tenders`, `awards`, `suppliers`) use `id UUID PRIMARY KEY REFERENCES entities(id) ON DELETE RESTRICT`.
3. **Canonical Relationship Identity & Deduplication**:
   - Enforced by unique constraint:
     `CONSTRAINT uq_relationship_identity UNIQUE (source_entity_id, relationship_predicate, target_entity_id, effective_from)`.
4. **Decoupled Claim Vectors**:
   - `processing_stage`: `extracted`, `normalized`, `resolved`, `validated`, `canonicalized`.
   - `assertion_status`: `unverified`, `substantiated`, `contested`, `superseded`, `revoked`.
5. **Contextual Authority Ordering**:
   - `authority_rules.authority_rank`: integer precedence within a specific `(claim_predicate, source_type, statutory_instrument)` scope.
6. **Immutable Evidence Snapshots**:
   - Trigger `trg_prevent_evidence_records_mutation` blocks any `UPDATE` or `DELETE` operations on `evidence_records`.

---

## 4. Running Verification Tests Locally

A test suite verifying all schema invariants is located in `tests/schema/test_schema_invariants.py`.

To run the tests:
```bash
python tests/schema/test_schema_invariants.py -v
```

### Verified Scenarios:
* **Test A**: Invalid relationship FK target fails.
* **Test B**: Domain entity referencing nonexistent `entities.id` fails.
* **Test C**: Duplicate relationship edge insertion fails.
* **Test D**: Extraction confidence (`0.0 - 1.0`) and date order (`effective_to >= effective_from`) check constraints.
* **Test E**: Provenance bridge rejects nonexistent relationship, claim, or evidence records.
* **Test F**: Historical claims remain preserved and linked via `superseded_by_claim_id` upon supersedence.
