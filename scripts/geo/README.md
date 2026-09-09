# Stats SA Geographic Ingestion Guide

This directory contains scripts for controlled, reproducible ingestion of official Statistics South Africa (Stats SA) geographic reference data into the `main_places` and `sub_places` PostgreSQL tables.

---

## 1. Source Files & Provenance

* **Main Place Lookup**: `MainPlace/MainPlaceLookupTable.xls` (3,109 data rows)
* **Sub Place Lookup**: `SubPlace/SubPlaceLookupTable.xls` (21,243 data rows)
* **Provenance Metadata**:
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

## 3. Ingestion Accounting Semantics

The ingestion engine uses an atomic staging mechanism to calculate exact database operations:
* **`inserted`**: Genuinely newly created rows inserted into the table.
* **`updated`**: Pre-existing rows matched by unique constraint (`mp_code` or `sp_code`) and refreshed via `ON CONFLICT DO UPDATE`.
* **`quarantined`**: Source rows deliberately excluded from database insertion due to verified source anomalies.

### Fresh Ingestion (Empty Tables):
* **Main Places**: `inserted: 3109`, `updated: 0`
* **Sub Places**: `inserted: 21241`, `updated: 0`
* **Quarantined**: `2`

### Repeat Ingestion (Populated Tables):
* **Main Places**: `inserted: 0`, `updated: 3109`
* **Sub Places**: `inserted: 0`, `updated: 21241`
* **Quarantined**: `2`

---

## 4. Known Source Anomaly Quarantine

The official Stats SA file contains exactly **2 orphaned rural Sub Places**:
* `11497004` (`Swellendam NU`) -> Derived parent MP `11497`
* `12332002` (`Prince Albert NU`) -> Derived parent MP `12332`

These parent codes are absent from the Main Place file. The ingestion script **explicitly quarantines and logs** these two records without inserting them and **without fabricating fake parent records**. Any unexpected/unregistered orphan triggers a fail-closed `IngestionValidationError` prior to database execution.

---

## 5. Running Automated Tests

To run the automated test suite against the live PostgreSQL database:

```bash
python -m unittest tests/geo/test_stats_sa_ingestion.py -v
```
