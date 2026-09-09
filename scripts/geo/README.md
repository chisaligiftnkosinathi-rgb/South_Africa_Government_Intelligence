# Stats SA Geographic Ingestion Guide

This directory contains scripts for controlled, reproducible ingestion of official Statistics South Africa (Stats SA) geographic reference data into the `main_places` and `sub_places` PostgreSQL tables.

---

## 1. Source Files & Provenance

* **Main Place Lookup**: `MainPlace/MainPlaceLookupTable.xls` (3,109 rows)
* **Sub Place Lookup**: `SubPlace/SubPlaceLookupTable.xls` (21,243 rows)
* **Provenance Defaults**:
  * `dataset_name`: `'Stats SA 2011 Census'`
  * `dataset_version`: `'v2011.1'`
  * `observed_at`: UTC execution timestamp

---

## 2. Ingestion Command

To execute the controlled ingestion against PostgreSQL:

```bash
python scripts/geo/import_stats_sa.py --dbname <dbname> --user <user> --host <host> --port <port>
```

Example for local test database:
```bash
python scripts/geo/import_stats_sa.py --dbname gov_intel_test --port 54339
```

---

## 3. Structural Validation & Anomaly Quarantine

The ingestion script enforces strict validation rules:
1. **Pre-Validation**: File existence, exact header columns, non-empty names, positive codes, and province codes strictly between 1 and 9.
2. **Deterministic Parent Derivation**: Each Sub Place derives its parent Main Place code via integer division (`SP_CODE // 1000`).
3. **Known Anomaly Quarantine**:
   - The official Stats SA file contains exactly **2 orphaned rural Sub Places**:
     * `11497004` (`Swellendam NU`) -> Derived parent MP `11497`
     * `12332002` (`Prince Albert NU`) -> Derived parent MP `12332`
   - These parent codes are absent from the Main Place file.
   - The ingestion script **explicitly quarantines and logs** these two records without inserting them and **without fabricating fake parent records**.
   - Any unexpected/unregistered orphan triggers a fail-closed `IngestionValidationError` prior to database execution.
4. **Idempotency**: All inserts execute in an atomic transaction using `ON CONFLICT (code) DO UPDATE` to ensure safe, repeatable execution without duplicate rows or key errors.

---

## 4. Expected Results

* **`main_places` Table**: Exactly **3,109** records inserted.
* **`sub_places` Table**: Exactly **21,241** records inserted.
* **Orphan Records**: Exactly **2** records quarantined and reported.

---

## 5. Running Automated Tests

To run the automated test suite against the live PostgreSQL database:

```bash
python -m unittest tests/geo/test_stats_sa_ingestion.py -v
```
