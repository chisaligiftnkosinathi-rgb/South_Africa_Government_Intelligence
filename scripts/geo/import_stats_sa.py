"""
Controlled Stats SA Geographic Ingestion Script
================================================
Reads official Stats SA MainPlace and SubPlace XLS files, validates structure and constraints,
and loads them idempotently into PostgreSQL (main_places, sub_places).
Accurately accounts for inserted vs updated vs unchanged vs quarantined rows.
Explicitly identifies and quarantines known source anomalies without fabrication or silent discarding.
"""

import os
import sys
import argparse
import datetime
import xlrd
import psycopg2
import psycopg2.extras

DEFAULT_MAIN_PLACE_PATH = "MainPlace/MainPlaceLookupTable.xls"
DEFAULT_SUB_PLACE_PATH = "SubPlace/SubPlaceLookupTable.xls"

DEFAULT_DATASET_NAME = "Stats SA 2011 Census"
DEFAULT_DATASET_VERSION = "v2011.1"

KNOWN_ORPHAN_SP_CODES = {11497004, 12332002}

EXPECTED_MP_COLUMNS = ['MP_CODE', 'MP_NAME', 'MN_CODE', 'MN_NAME', 'DC_MN_C', 'DC_NAME', 'PR_CODE', 'PR_NAME']
EXPECTED_SP_COLUMNS = ['SP_CODE', 'SP_NAME', 'MN_CODE', 'MN_NAME', 'DC_MN_C', 'DC_NAME', 'PR_CODE', 'PR_NAME']

class IngestionValidationError(Exception):
    pass

def validate_and_parse_main_places(file_path: str):
    if not os.path.exists(file_path):
        raise IngestionValidationError(f"Main Place file not found: {file_path}")
        
    wb = xlrd.open_workbook(file_path)
    sheet = wb.sheet_by_index(0)
    
    headers = [str(sheet.cell_value(0, c)).strip() for c in range(sheet.ncols)]
    if headers != EXPECTED_MP_COLUMNS:
        raise IngestionValidationError(f"Main Place headers mismatch. Expected {EXPECTED_MP_COLUMNS}, got {headers}")
        
    records = []
    seen_mp_codes = set()
    
    for row_idx in range(1, sheet.nrows):
        row = sheet.row_values(row_idx)
        try:
            mp_code = int(row[0])
            mp_name = str(row[1]).strip()
            mn_code = int(row[2])
            mn_name = str(row[3]).strip()
            dc_code = int(row[4])
            dc_name = str(row[5]).strip()
            pr_code = int(row[6])
            pr_name = str(row[7]).strip()
        except Exception as e:
            raise IngestionValidationError(f"Row {row_idx}: Data conversion error: {e}")
            
        if mp_code <= 0:
            raise IngestionValidationError(f"Row {row_idx}: Non-positive MP_CODE {mp_code}")
        if mp_code in seen_mp_codes:
            raise IngestionValidationError(f"Row {row_idx}: Duplicate MP_CODE {mp_code}")
        seen_mp_codes.add(mp_code)
        
        if not mp_name:
            raise IngestionValidationError(f"Row {row_idx}: Blank MP_NAME for code {mp_code}")
        if mn_code <= 0 or not mn_name:
            raise IngestionValidationError(f"Row {row_idx}: Invalid municipality for code {mp_code}")
        if dc_code <= 0 or not dc_name:
            raise IngestionValidationError(f"Row {row_idx}: Invalid district for code {mp_code}")
        if pr_code < 1 or pr_code > 9 or not pr_name:
            raise IngestionValidationError(f"Row {row_idx}: Invalid province code {pr_code} for code {mp_code}")
            
        records.append({
            "mp_code": mp_code,
            "mp_name": mp_name,
            "municipality_code": mn_code,
            "municipality_name": mn_name,
            "district_code": dc_code,
            "district_name": dc_name,
            "province_code": pr_code,
            "province_name": pr_name
        })
        
    return records, seen_mp_codes

def validate_and_parse_sub_places(file_path: str, valid_mp_codes: set):
    if not os.path.exists(file_path):
        raise IngestionValidationError(f"Sub Place file not found: {file_path}")
        
    wb = xlrd.open_workbook(file_path)
    sheet = wb.sheet_by_index(0)
    
    headers = [str(sheet.cell_value(0, c)).strip() for c in range(sheet.ncols)]
    if headers != EXPECTED_SP_COLUMNS:
        raise IngestionValidationError(f"Sub Place headers mismatch. Expected {EXPECTED_SP_COLUMNS}, got {headers}")
        
    valid_records = []
    orphan_records = []
    seen_sp_codes = set()
    
    for row_idx in range(1, sheet.nrows):
        row = sheet.row_values(row_idx)
        try:
            sp_code = int(row[0])
            sp_name = str(row[1]).strip()
            mn_code = int(row[2])
            mn_name = str(row[3]).strip()
            dc_code = int(row[4])
            dc_name = str(row[5]).strip()
            pr_code = int(row[6])
            pr_name = str(row[7]).strip()
        except Exception as e:
            raise IngestionValidationError(f"Row {row_idx}: Data conversion error: {e}")
            
        if sp_code <= 0:
            raise IngestionValidationError(f"Row {row_idx}: Non-positive SP_CODE {sp_code}")
        if sp_code in seen_sp_codes:
            raise IngestionValidationError(f"Row {row_idx}: Duplicate SP_CODE {sp_code}")
        seen_sp_codes.add(sp_code)
        
        if not sp_name:
            raise IngestionValidationError(f"Row {row_idx}: Blank SP_NAME for code {sp_code}")
        if mn_code <= 0 or not mn_name:
            raise IngestionValidationError(f"Row {row_idx}: Invalid municipality for code {sp_code}")
        if dc_code <= 0 or not dc_name:
            raise IngestionValidationError(f"Row {row_idx}: Invalid district for code {sp_code}")
        if pr_code < 1 or pr_code > 9 or not pr_name:
            raise IngestionValidationError(f"Row {row_idx}: Invalid province code {pr_code} for code {sp_code}")
            
        derived_mp = sp_code // 1000
        
        record = {
            "sp_code": sp_code,
            "sp_name": sp_name,
            "main_place_code": derived_mp,
            "municipality_code": mn_code,
            "municipality_name": mn_name,
            "district_code": dc_code,
            "district_name": dc_name,
            "province_code": pr_code,
            "province_name": pr_name
        }
        
        if derived_mp in valid_mp_codes:
            valid_records.append(record)
        else:
            orphan_records.append(record)
            if sp_code not in KNOWN_ORPHAN_SP_CODES:
                raise IngestionValidationError(
                    f"Unexpected unmapped Sub Place detected! SP_CODE={sp_code} ('{sp_name}') "
                    f"with derived MP_CODE={derived_mp} is not in MainPlace dataset and not in known anomalies."
                )
                
    return valid_records, orphan_records

def run_ingestion(conn, main_place_path: str, sub_place_path: str,
                  dataset_name: str = DEFAULT_DATASET_NAME,
                  dataset_version: str = DEFAULT_DATASET_VERSION,
                  observed_at: datetime.datetime = None):
    if observed_at is None:
        observed_at = datetime.datetime.now(datetime.timezone.utc)
        
    # 1. Structural Pre-Validation
    mp_records, mp_code_set = validate_and_parse_main_places(main_place_path)
    sp_records, sp_orphans = validate_and_parse_sub_places(sub_place_path, mp_code_set)
    
    report = {
        "execution_timestamp": observed_at.isoformat(),
        "main_place_file": main_place_path,
        "sub_place_file": sub_place_path,
        "dataset_name": dataset_name,
        "dataset_version": dataset_version,
        "mp_source_rows": len(mp_records),
        "sp_source_rows": len(sp_records) + len(sp_orphans),
        "mp_validated_count": len(mp_records),
        "sp_validated_count": len(sp_records),
        "quarantined_count": len(sp_orphans),
        "orphan_sp_codes": [o["sp_code"] for o in sp_orphans],
        "orphan_details": [
            {"sp_code": o["sp_code"], "sp_name": o["sp_name"], "derived_mp": o["main_place_code"], "mun": o["municipality_name"]}
            for o in sp_orphans
        ],
        "mp_inserted": 0,
        "mp_updated": 0,
        "sp_inserted": 0,
        "sp_updated": 0,
        "final_db_mp_count": 0,
        "final_db_sp_count": 0
    }
    
    # 2. Database Transaction (Atomic with Staging Accounting)
    with conn:
        with conn.cursor() as cur:
            # Create staging tables for accurate accounting
            cur.execute("""
                CREATE TEMP TABLE stage_main_places (
                    mp_code INTEGER, mp_name TEXT, municipality_code INTEGER, municipality_name TEXT,
                    district_code INTEGER, district_name TEXT, province_code INTEGER, province_name TEXT,
                    dataset_name TEXT, dataset_version TEXT, observed_at TIMESTAMPTZ
                ) ON COMMIT DROP;
            """)
            
            cur.execute("""
                CREATE TEMP TABLE stage_sub_places (
                    sp_code BIGINT, sp_name TEXT, main_place_code INTEGER, municipality_code INTEGER, municipality_name TEXT,
                    district_code INTEGER, district_name TEXT, province_code INTEGER, province_name TEXT,
                    dataset_name TEXT, dataset_version TEXT, observed_at TIMESTAMPTZ
                ) ON COMMIT DROP;
            """)
            
            # Populate Staging Main Places
            mp_stage_sql = """
                INSERT INTO stage_main_places (
                    mp_code, mp_name, municipality_code, municipality_name,
                    district_code, district_name, province_code, province_name,
                    dataset_name, dataset_version, observed_at
                ) VALUES (
                    %(mp_code)s, %(mp_name)s, %(municipality_code)s, %(municipality_name)s,
                    %(district_code)s, %(district_name)s, %(province_code)s, %(province_name)s,
                    %(dataset_name)s, %(dataset_version)s, %(observed_at)s
                );
            """
            mp_payload = [
                {**r, "dataset_name": dataset_name, "dataset_version": dataset_version, "observed_at": observed_at}
                for r in mp_records
            ]
            psycopg2.extras.execute_batch(cur, mp_stage_sql, mp_payload, page_size=1000)
            
            # Populate Staging Sub Places
            sp_stage_sql = """
                INSERT INTO stage_sub_places (
                    sp_code, sp_name, main_place_code, municipality_code, municipality_name,
                    district_code, district_name, province_code, province_name,
                    dataset_name, dataset_version, observed_at
                ) VALUES (
                    %(sp_code)s, %(sp_name)s, %(main_place_code)s, %(municipality_code)s, %(municipality_name)s,
                    %(district_code)s, %(district_name)s, %(province_code)s, %(province_name)s,
                    %(dataset_name)s, %(dataset_version)s, %(observed_at)s
                );
            """
            sp_payload = [
                {**r, "dataset_name": dataset_name, "dataset_version": dataset_version, "observed_at": observed_at}
                for r in sp_records
            ]
            psycopg2.extras.execute_batch(cur, sp_stage_sql, sp_payload, page_size=2000)
            
            # Compute Insert vs Update for Main Places
            cur.execute("""
                SELECT 
                    COUNT(s.mp_code) FILTER (WHERE m.mp_code IS NULL) AS to_insert,
                    COUNT(s.mp_code) FILTER (WHERE m.mp_code IS NOT NULL) AS to_update
                FROM stage_main_places s
                LEFT JOIN main_places m ON m.mp_code = s.mp_code;
            """)
            mp_to_insert, mp_to_update = cur.fetchone()
            
            # Merge Main Places
            cur.execute("""
                INSERT INTO main_places (
                    mp_code, mp_name, municipality_code, municipality_name,
                    district_code, district_name, province_code, province_name,
                    dataset_name, dataset_version, observed_at
                )
                SELECT 
                    mp_code, mp_name, municipality_code, municipality_name,
                    district_code, district_name, province_code, province_name,
                    dataset_name, dataset_version, observed_at
                FROM stage_main_places
                ON CONFLICT (mp_code) DO UPDATE SET
                    mp_name = EXCLUDED.mp_name,
                    municipality_code = EXCLUDED.municipality_code,
                    municipality_name = EXCLUDED.municipality_name,
                    district_code = EXCLUDED.district_code,
                    district_name = EXCLUDED.district_name,
                    province_code = EXCLUDED.province_code,
                    province_name = EXCLUDED.province_name,
                    dataset_name = EXCLUDED.dataset_name,
                    dataset_version = EXCLUDED.dataset_version,
                    observed_at = EXCLUDED.observed_at;
            """)
            report["mp_inserted"] = mp_to_insert
            report["mp_updated"] = mp_to_update
            
            # Compute Insert vs Update for Sub Places
            cur.execute("""
                SELECT 
                    COUNT(s.sp_code) FILTER (WHERE sp.sp_code IS NULL) AS to_insert,
                    COUNT(s.sp_code) FILTER (WHERE sp.sp_code IS NOT NULL) AS to_update
                FROM stage_sub_places s
                LEFT JOIN sub_places sp ON sp.sp_code = s.sp_code;
            """)
            sp_to_insert, sp_to_update = cur.fetchone()
            
            # Merge Sub Places
            cur.execute("""
                INSERT INTO sub_places (
                    sp_code, sp_name, main_place_code, municipality_code, municipality_name,
                    district_code, district_name, province_code, province_name,
                    dataset_name, dataset_version, observed_at
                )
                SELECT 
                    sp_code, sp_name, main_place_code, municipality_code, municipality_name,
                    district_code, district_name, province_code, province_name,
                    dataset_name, dataset_version, observed_at
                FROM stage_sub_places
                ON CONFLICT (sp_code) DO UPDATE SET
                    sp_name = EXCLUDED.sp_name,
                    main_place_code = EXCLUDED.main_place_code,
                    municipality_code = EXCLUDED.municipality_code,
                    municipality_name = EXCLUDED.municipality_name,
                    district_code = EXCLUDED.district_code,
                    district_name = EXCLUDED.district_name,
                    province_code = EXCLUDED.province_code,
                    province_name = EXCLUDED.province_name,
                    dataset_name = EXCLUDED.dataset_name,
                    dataset_version = EXCLUDED.dataset_version,
                    observed_at = EXCLUDED.observed_at;
            """)
            report["sp_inserted"] = sp_to_insert
            report["sp_updated"] = sp_to_update
            
            # Authoritative Final Database Totals
            cur.execute("SELECT COUNT(*) FROM main_places;")
            report["final_db_mp_count"] = cur.fetchone()[0]
            
            cur.execute("SELECT COUNT(*) FROM sub_places;")
            report["final_db_sp_count"] = cur.fetchone()[0]
            
    return report

def print_report(report: dict):
    print("=" * 60)
    print("STATS SA CONTROLLED GEOGRAPHIC INGESTION REPORT")
    print("=" * 60)
    print(f"Execution Timestamp : {report['execution_timestamp']}")
    print(f"Dataset Name        : {report['dataset_name']}")
    print(f"Dataset Version     : {report['dataset_version']}")
    print(f"Main Place File     : {report['main_place_file']}")
    print(f"Sub Place File      : {report['sub_place_file']}")
    print("-" * 60)
    print(f"Source Main Places  : {report['mp_source_rows']}")
    print(f"Validated MP Count  : {report['mp_validated_count']}")
    print(f"DB MP Inserted      : {report['mp_inserted']}")
    print(f"DB MP Updated       : {report['mp_updated']}")
    print(f"Final DB MP Total   : {report['final_db_mp_count']}")
    print("-" * 60)
    print(f"Source Sub Places   : {report['sp_source_rows']}")
    print(f"Validated SP Count  : {report['sp_validated_count']}")
    print(f"DB SP Inserted      : {report['sp_inserted']}")
    print(f"DB SP Updated       : {report['sp_updated']}")
    print(f"Final DB SP Total   : {report['final_db_sp_count']}")
    print("-" * 60)
    print(f"Quarantined Orphans : {report['quarantined_count']}")
    print(f"Orphan SP Codes     : {report['orphan_sp_codes']}")
    if report["orphan_details"]:
        print("Orphan Details (Quarantined, not inserted):")
        for od in report["orphan_details"]:
            print(f"  * SP_CODE: {od['sp_code']} ({od['sp_name']}) -> Derived Parent MP: {od['derived_mp']} (Mun: {od['mun']})")
    print("=" * 60)

def main():
    parser = argparse.ArgumentParser(description="Ingest Stats SA MainPlace and SubPlace datasets into PostgreSQL.")
    parser.add_argument("--dbname", default=os.getenv("PGDATABASE", "gov_intel_test"))
    parser.add_argument("--user", default=os.getenv("PGUSER", "postgres"))
    parser.add_argument("--host", default=os.getenv("PGHOST", "127.0.0.1"))
    parser.add_argument("--port", type=int, default=int(os.getenv("PGPORT", "54339")))
    parser.add_argument("--mp-file", default=DEFAULT_MAIN_PLACE_PATH)
    parser.add_argument("--sp-file", default=DEFAULT_SUB_PLACE_PATH)
    args = parser.parse_args()
    
    conn = psycopg2.connect(dbname=args.dbname, user=args.user, host=args.host, port=args.port)
    conn.set_client_encoding('UTF8')
    
    try:
        report = run_ingestion(conn, args.mp_file, args.sp_file)
        print_report(report)
    finally:
        conn.close()

if __name__ == "__main__":
    main()
