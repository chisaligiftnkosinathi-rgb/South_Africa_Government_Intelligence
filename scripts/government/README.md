# Government Governance Ingestion & Atlas Foundation

This directory contains scripts and documentation for ingesting and establishing primary governance entities, statutory offices, and constitutional functions in the PostgreSQL canonical graph.

---

## 1. Execution & Ingestion

To ingest the City of Mbombela governance foundation based on primary statutory instruments:

```bash
python scripts/government/ingest_mbombela_government.py
```

### Ingested Canonical Entities:
1. **Institution**: `City of Mbombela Local Municipality` (`MP322`, `mp-mbombela-lm`)
2. **Statutory Offices**:
   * `Municipal Manager` (`administrative` branch, Head of Administration & Accounting Officer)
   * `Executive Mayor` (`political` branch)
   * `Speaker of Council` (`political` branch)
3. **Constitutional Functions**:
   * `Potable Water Supply & Sanitation` (Schedule 4B)
   * `Electricity Reticulation` (Schedule 4B)
   * `Municipal Roads & Pothole Maintenance` (Schedule 5B)
   * `Refuse Removal & Solid Waste Disposal` (Schedule 5B)

---

## 2. Ingestion Guarantees & Invariants

* **Strict Provenance**: Every entity, claim, and relationship connects to an immutable `evidence_records` snapshot and an authoritative `sources` record.
* **First-Class Relationships**: All edges are modeled in `relationships` with `ON CONFLICT` deduplication keys.
* **No Direct Person Attachment**: Natural persons never attach directly to an institution.
* **Decoupled Geography**: The geographic layer (`main_places`, `sub_places`) remains completely untouched and independent.

---

## 3. Running Automated Verification Tests

```bash
python -m unittest tests/government/test_mbombela_government_integrity.py -v
```
