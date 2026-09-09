"""
Geographic Integrity and Municipal Verification Layer
=====================================================
Read-only inspection and verification layer for Stats SA geographic reference data.
Validates global dataset invariants, checks relational integrity, and produces
auditable municipal profile reports (e.g. for the City of Mbombela pilot).
"""

import os
import sys
import argparse
import psycopg2
import psycopg2.extras

def verify_global_integrity(conn):
    """
    Executes comprehensive read-only integrity checks across main_places and sub_places.
    Returns a dictionary with status and metrics for each check.
    """
    checks = {}
    with conn.cursor() as cur:
        # Check I: Global row counts
        cur.execute("SELECT COUNT(*) FROM main_places;")
        mp_count = cur.fetchone()[0]
        cur.execute("SELECT COUNT(*) FROM sub_places;")
        sp_count = cur.fetchone()[0]
        checks["global_counts"] = {
            "main_places_count": mp_count,
            "sub_places_count": sp_count,
            "passed": (mp_count == 3109 and sp_count == 21241)
        }

        # Check A: Every Sub Place has a valid Main Place FK
        cur.execute("""
            SELECT COUNT(*)
            FROM sub_places sp
            LEFT JOIN main_places mp ON mp.mp_code = sp.main_place_code
            WHERE mp.mp_code IS NULL;
        """)
        unmatched_sp = cur.fetchone()[0]
        checks["sub_place_fk_integrity"] = {
            "unmatched_count": unmatched_sp,
            "passed": (unmatched_sp == 0)
        }

        # Check B: SP_CODE // 1000 == main_place_code
        cur.execute("""
            SELECT COUNT(*)
            FROM sub_places
            WHERE main_place_code != (sp_code / 1000);
        """)
        parent_arithmetic_mismatches = cur.fetchone()[0]
        checks["parent_arithmetic_match"] = {
            "mismatch_count": parent_arithmetic_mismatches,
            "passed": (parent_arithmetic_mismatches == 0)
        }

        # Check C: No duplicate MP_CODE
        cur.execute("""
            SELECT COUNT(*) FROM (
                SELECT mp_code FROM main_places GROUP BY mp_code HAVING COUNT(*) > 1
            ) dupes;
        """)
        mp_dupes = cur.fetchone()[0]
        checks["main_place_uniqueness"] = {
            "duplicate_count": mp_dupes,
            "passed": (mp_dupes == 0)
        }

        # Check D: No duplicate SP_CODE
        cur.execute("""
            SELECT COUNT(*) FROM (
                SELECT sp_code FROM sub_places GROUP BY sp_code HAVING COUNT(*) > 1
            ) dupes;
        """)
        sp_dupes = cur.fetchone()[0]
        checks["sub_place_uniqueness"] = {
            "duplicate_count": sp_dupes,
            "passed": (sp_dupes == 0)
        }

        # Check E: No Main Place has internal conflicting administrative identity
        cur.execute("""
            SELECT COUNT(*) FROM (
                SELECT mp_code
                FROM main_places
                GROUP BY mp_code
                HAVING COUNT(DISTINCT municipality_code) > 1
                    OR COUNT(DISTINCT district_code) > 1
                    OR COUNT(DISTINCT province_code) > 1
            ) conflicts;
        """)
        mp_admin_conflicts = cur.fetchone()[0]
        checks["main_place_admin_consistency"] = {
            "conflict_count": mp_admin_conflicts,
            "passed": (mp_admin_conflicts == 0)
        }

        # Check F: Sub Place matches its parent Main Place administrative identity
        cur.execute("""
            SELECT COUNT(*)
            FROM sub_places sp
            JOIN main_places mp ON mp.mp_code = sp.main_place_code
            WHERE sp.municipality_code != mp.municipality_code
               OR sp.district_code != mp.district_code
               OR sp.province_code != mp.province_code;
        """)
        admin_mismatches = cur.fetchone()[0]
        checks["sub_place_parent_admin_agreement"] = {
            "mismatch_count": admin_mismatches,
            "passed": (admin_mismatches == 0)
        }

        # Check G: Province codes between 1 and 9
        cur.execute("""
            SELECT 
                (SELECT COUNT(*) FROM main_places WHERE province_code < 1 OR province_code > 9) +
                (SELECT COUNT(*) FROM sub_places WHERE province_code < 1 OR province_code > 9);
        """)
        invalid_prov_codes = cur.fetchone()[0]
        checks["province_code_range"] = {
            "invalid_count": invalid_prov_codes,
            "passed": (invalid_prov_codes == 0)
        }

        # Check H: No blank geographic names
        cur.execute("""
            SELECT 
                (SELECT COUNT(*) FROM main_places WHERE length(trim(mp_name)) = 0 OR length(trim(municipality_name)) = 0) +
                (SELECT COUNT(*) FROM sub_places WHERE length(trim(sp_name)) = 0 OR length(trim(municipality_name)) = 0);
        """)
        blank_names = cur.fetchone()[0]
        checks["non_blank_names"] = {
            "blank_count": blank_names,
            "passed": (blank_names == 0)
        }

        # Check J: Quarantined anomalies check (ensuring they remain strictly absent from DB)
        cur.execute("SELECT COUNT(*) FROM sub_places WHERE sp_code IN (11497004, 12332002);")
        quarantine_leaks = cur.fetchone()[0]
        checks["quarantine_status"] = {
            "leaked_count": quarantine_leaks,
            "quarantined_codes": [11497004, 12332002],
            "passed": (quarantine_leaks == 0)
        }

    all_passed = all(c["passed"] for c in checks.values())
    return {"all_passed": all_passed, "checks": checks}

def get_municipal_summary(conn, municipality_code: int):
    """
    Returns deterministic geographic summary for a municipality by code.
    """
    with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
        # Administrative details
        cur.execute("""
            SELECT DISTINCT 
                municipality_code, municipality_name, 
                district_code, district_name, 
                province_code, province_name
            FROM main_places
            WHERE municipality_code = %s;
        """, (municipality_code,))
        meta = cur.fetchone()
        if not meta:
            return None

        # Main Places listing
        cur.execute("""
            SELECT mp_code, mp_name
            FROM main_places
            WHERE municipality_code = %s
            ORDER BY mp_code ASC;
        """, (municipality_code,))
        main_places = cur.fetchall()

        # Sub Places listing
        cur.execute("""
            SELECT sp_code, sp_name, main_place_code
            FROM sub_places
            WHERE municipality_code = %s
            ORDER BY sp_code ASC;
        """, (municipality_code,))
        sub_places = cur.fetchall()

        return {
            "municipality_code": meta["municipality_code"],
            "municipality_name": meta["municipality_name"],
            "district_code": meta["district_code"],
            "district_name": meta["district_name"],
            "province_code": meta["province_code"],
            "province_name": meta["province_name"],
            "main_place_count": len(main_places),
            "sub_place_count": len(sub_places),
            "main_places": main_places,
            "sub_places": sub_places
        }

def find_municipality_code_by_name(conn, name_query: str):
    """
    Resolves municipality code deterministically by searching municipality_name.
    """
    with conn.cursor() as cur:
        cur.execute("""
            SELECT DISTINCT municipality_code, municipality_name
            FROM main_places
            WHERE municipality_name ILIKE %s
            ORDER BY municipality_code ASC;
        """, (f"%{name_query}%",))
        rows = cur.fetchall()
        return rows

def generate_mbombela_pilot_report(conn):
    """
    Generates the complete verification and geographic pilot profile for City of Mbombela.
    """
    # 1. Resolve Mbombela
    matches = find_municipality_code_by_name(conn, "mbombela")
    if not matches:
        raise ValueError("City of Mbombela municipality could not be resolved from loaded data!")
    mbombela_code = matches[0][0]

    # 2. Extract Municipal Summary
    summary = get_municipal_summary(conn, mbombela_code)

    # 3. Global Integrity
    integrity = verify_global_integrity(conn)

    return {
        "summary": summary,
        "integrity": integrity
    }

def print_pilot_report(report: dict):
    s = report["summary"]
    integ = report["integrity"]

    print("=" * 70)
    print("SOUTH AFRICAN GOVERNMENT INTELLIGENCE PLATFORM")
    print("GEOGRAPHIC PILOT REPORT: CITY OF MBOMBELA (STATS SA 2011 CENSUS)")
    print("=" * 70)
    print("1. MUNICIPAL IDENTITY & ADMINISTRATIVE HIERARCHY")
    print("-" * 70)
    print(f"Municipality Code : {s['municipality_code']}")
    print(f"Municipality Name : {s['municipality_name']}")
    print(f"District Code     : {s['district_code']}")
    print(f"District Name     : {s['district_name']}")
    print(f"Province Code     : {s['province_code']}")
    print(f"Province Name     : {s['province_name']}")
    print("-" * 70)
    print(f"Total Main Places : {s['main_place_count']}")
    print(f"Total Sub Places  : {s['sub_place_count']}")
    print("=" * 70)

    print("\n2. MAIN PLACES IN CITY OF MBOMBELA (Ordered by MP_CODE)")
    print("-" * 70)
    print(f"{'MP_CODE':<10} | {'MAIN PLACE NAME'}")
    print("-" * 70)
    for mp in s["main_places"]:
        print(f"{mp['mp_code']:<10} | {mp['mp_name']}")
    print("-" * 70)

    print(f"\n3. SUB PLACES IN CITY OF MBOMBELA (First 15 of {s['sub_place_count']}, Ordered by SP_CODE)")
    print("-" * 70)
    print(f"{'SP_CODE':<12} | {'PARENT MP':<10} | {'SUB PLACE NAME'}")
    print("-" * 70)
    for sp in s["sub_places"][:15]:
        print(f"{sp['sp_code']:<12} | {sp['main_place_code']:<10} | {sp['sp_name']}")
    if len(s["sub_places"]) > 15:
        print(f"... [{len(s['sub_places']) - 15} additional Sub Places verified in database]")
    print("-" * 70)

    print("\n4. GLOBAL GEOGRAPHIC INTEGRITY & ANOMALY STATUS")
    print("-" * 70)
    for name, c in integ["checks"].items():
        status = "PASSED [OK]" if c["passed"] else "FAILED [X]"
        print(f" * {name:<35}: {status}")
    print("-" * 70)
    print(f"Overall Dataset Integrity Status : {'PASSED (100%)' if integ['all_passed'] else 'FAILED'}")
    print(f"Quarantined Stats SA Anomalies   : {integ['checks']['quarantine_status']['quarantined_codes']} (Excluded from DB)")
    print("=" * 70)

def main():
    parser = argparse.ArgumentParser(description="Geographic integrity verification and Mbombela pilot reporting.")
    parser.add_argument("--dbname", default=os.getenv("PGDATABASE", "gov_intel_test"))
    parser.add_argument("--user", default=os.getenv("PGUSER", "postgres"))
    parser.add_argument("--host", default=os.getenv("PGHOST", "127.0.0.1"))
    parser.add_argument("--port", type=int, default=int(os.getenv("PGPORT", "54339")))
    args = parser.parse_args()

    conn = psycopg2.connect(dbname=args.dbname, user=args.user, host=args.host, port=args.port)
    conn.set_client_encoding('UTF8')
    try:
        report = generate_mbombela_pilot_report(conn)
        print_pilot_report(report)
    finally:
        conn.close()

if __name__ == "__main__":
    main()
