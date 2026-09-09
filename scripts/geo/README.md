# Stats SA Geographic Ingestion & Verification Guide

This directory contains scripts for controlled ingestion and read-only integrity verification of official Statistics South Africa (Stats SA) geographic reference data (`main_places` and `sub_places`).

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

## 4. Mbombela Pilot & Read-Only Integrity Verification

To run the read-only geographic integrity verification and generate the City of Mbombela pilot profile:

```bash
python scripts/geo/verify_mbombela_pilot.py --dbname gov_intel_test --port 54339
```

### What It Verifies:
1. **Source-Preserving & Read-Only**: Performs queries across existing tables without mutating any data or adding database objects.
2. **City of Mbombela Profile**:
   * **Municipality Code**: `815` (`Mbombela`)
   * **District**: `32` (`Ehlanzeni District Municipality`)
   * **Province**: `8` (`MPUMALANGA`)
   * **Main Places**: Exactly **25** Main Places (e.g. `81501 Broedershoek` to `81525 Nsikazi Part 2`), ordered deterministically by code.
   * **Sub Places**: Exactly **108** Sub Places, ordered deterministically by code.
3. **Integrity Invariants**:
   * All 21,241 Sub Places have valid Main Place foreign keys.
   * Arithmetic parent match (`sp_code // 1000 == main_place_code`) holds 100%.
   * Zero duplicate codes, zero blank names, zero admin hierarchy mismatches.
   * Province codes strictly between 1 and 9.
   * The **2 quarantined anomalies** (`11497004`, `12332002`) remain strictly excluded from the database.

---

## 5. Running Automated Tests

To run the full test suite against the live PostgreSQL database:

```bash
# Ingestion and accounting tests
python -m unittest tests/geo/test_stats_sa_ingestion.py -v

# Geographic integrity and Mbombela pilot tests
python -m unittest tests/geo/test_mbombela_geographic_integrity.py -v
```
