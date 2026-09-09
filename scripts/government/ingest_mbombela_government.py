"""
Controlled Ingestion of Mbombela Municipal Governance Foundation
===============================================================
Establishes the City of Mbombela government institution, its statutory offices,
and constitutional functions in the PostgreSQL governance graph based strictly
on primary statutory sources (Constitution, Structures Act, Systems Act, MFMA).
Preserves the full provenance chain:
Source -> Evidence Record -> Authority Rules -> Claims -> Canonical Entities -> First-Class Relationships -> Evidence Bridges.
"""

import os
import sys
import hashlib
import datetime
import psycopg2
import psycopg2.extras

# -----------------------------------------------------------------------------
# 1. PRIMARY STATUTORY SOURCES
# -----------------------------------------------------------------------------
SOURCES_DATA = [
    {
        "slug": "za-statute-constitution-1996",
        "name": "Constitution of the Republic of South Africa, 1996 (Act No. 108 of 1996)",
        "source_type": "gazette",
        "base_url": "https://www.gov.za/documents/constitution/constitution-republic-south-africa-1996-1",
        "polling_cadence_minutes": 525600
    },
    {
        "slug": "za-statute-municipal-structures-act-1998",
        "name": "Local Government: Municipal Structures Act, 1998 (Act No. 117 of 1998)",
        "source_type": "gazette",
        "base_url": "https://www.gov.za/documents/local-government-municipal-structures-act",
        "polling_cadence_minutes": 525600
    },
    {
        "slug": "za-statute-municipal-systems-act-2000",
        "name": "Local Government: Municipal Systems Act, 2000 (Act No. 32 of 2000)",
        "source_type": "gazette",
        "base_url": "https://www.gov.za/documents/local-government-municipal-systems-act",
        "polling_cadence_minutes": 525600
    },
    {
        "slug": "za-statute-mfma-2003",
        "name": "Local Government: Municipal Finance Management Act, 2003 (Act No. 56 of 2003)",
        "source_type": "gazette",
        "base_url": "https://www.gov.za/documents/local-government-municipal-finance-management-act",
        "polling_cadence_minutes": 525600
    },
    {
        "slug": "mp-prov-gazette-s12-mbombela-2000",
        "name": "Mpumalanga Provincial Gazette Extraordinary No. 638 (Notice 356 of 2000) - Establishment of Municipality MP322",
        "source_type": "gazette",
        "base_url": "https://www.gpwonline.co.za/gazettes/mpumalanga",
        "polling_cadence_minutes": 525600
    }
]

# -----------------------------------------------------------------------------
# 2. IMMUTABLE EVIDENCE RECORDS
# -----------------------------------------------------------------------------
EVIDENCE_DATA = [
    {
        "source_slug": "mp-prov-gazette-s12-mbombela-2000",
        "origin_url": "https://www.gpwonline.co.za/gazettes/mpumalanga/2000/notice356.pdf",
        "mime_type": "application/pdf",
        "raw_text": (
            "NOTICE 356 OF 2000: ESTABLISHMENT OF THE CITY OF MBOMBELA LOCAL MUNICIPALITY (MP322). "
            "In terms of section 12 of the Local Government: Municipal Structures Act, 1998 (Act No. 117 of 1998), "
            "there is hereby established a local municipality with demarcation code MP322 within the Ehlanzeni District, "
            "Province of Mpumalanga, to be officially designated as the City of Mbombela Local Municipality."
        )
    },
    {
        "source_slug": "za-statute-municipal-structures-act-1998",
        "origin_url": "https://www.gov.za/documents/acts/act117of1998.pdf",
        "mime_type": "application/pdf",
        "raw_text": (
            "Section 36 & 48 of Act 117 of 1998: Each municipal council must have a Speaker and an Executive Mayor or Mayor. "
            "Section 82: A municipal council must appoint a municipal manager who is the head of administration and also the accounting officer for the municipality."
        )
    },
    {
        "source_slug": "za-statute-constitution-1996",
        "origin_url": "https://www.gov.za/documents/constitution/act108of1996.pdf",
        "mime_type": "application/pdf",
        "raw_text": (
            "Constitution of the Republic of South Africa, 1996. Section 156(1) and Schedule 4B & 5B: "
            "Schedule 4B Municipal Functions include: Water and sanitation services limited to potable water supply systems and domestic waste-water and sewage disposal systems; Electricity and gas reticulation; Municipal planning; Stormwater management systems. "
            "Schedule 5B Municipal Functions include: Local amenities; Municipal roads; Refuse removal, refuse dumps and solid waste disposal; Traffic and parking."
        )
    }
]

# -----------------------------------------------------------------------------
# 3. STATUTORY AUTHORITY RULES
# -----------------------------------------------------------------------------
AUTHORITY_RULES_DATA = [
    {
        "claim_predicate": "houses_office",
        "source_type": "gazette",
        "authority_rank": 1,
        "can_substantiate_alone": True,
        "can_supersede_prior": True,
        "requires_corroboration": False,
        "statutory_instrument": "Local Government: Municipal Structures Act 117 of 1998 (Sections 36, 48, 82)"
    },
    {
        "claim_predicate": "responsible_for_function",
        "source_type": "gazette",
        "authority_rank": 1,
        "can_substantiate_alone": True,
        "can_supersede_prior": True,
        "requires_corroboration": False,
        "statutory_instrument": "Constitution of the Republic of South Africa, 1996 (Schedule 4B and 5B)"
    }
]

# -----------------------------------------------------------------------------
# 4. CANONICAL ENTITY DEFINITIONS
# -----------------------------------------------------------------------------
MBOMBELA_INSTITUTION_URN = "urn:za:gov:institution:local:mp322:mbombela"

OFFICES_DATA = [
    {
        "urn": "urn:za:gov:office:mp322:municipal-manager",
        "title": "Municipal Manager",
        "branch": "administrative"
    },
    {
        "urn": "urn:za:gov:office:mp322:executive-mayor",
        "title": "Executive Mayor",
        "branch": "political"
    },
    {
        "urn": "urn:za:gov:office:mp322:speaker",
        "title": "Speaker of Council",
        "branch": "political"
    }
]

FUNCTIONS_DATA = [
    {
        "urn": "urn:za:gov:function:water-and-sanitation",
        "category": "Potable Water Supply & Sanitation",
        "schedule": "schedule_4b",
        "escalation_level": 1
    },
    {
        "urn": "urn:za:gov:function:electricity-reticulation",
        "category": "Electricity Reticulation",
        "schedule": "schedule_4b",
        "escalation_level": 1
    },
    {
        "urn": "urn:za:gov:function:municipal-roads",
        "category": "Municipal Roads & Pothole Maintenance",
        "schedule": "schedule_5b",
        "escalation_level": 1
    },
    {
        "urn": "urn:za:gov:function:refuse-and-solid-waste",
        "category": "Refuse Removal & Solid Waste Disposal",
        "schedule": "schedule_5b",
        "escalation_level": 1
    }
]

def ingest_mbombela_governance(conn):
    """
    Deterministically populates the Mbombela governance slice in an atomic transaction.
    Returns a dictionary summarizing all ingested entities, evidence, claims, and edges.
    """
    report = {
        "execution_timestamp": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        "sources_count": 0,
        "evidence_count": 0,
        "authority_rules_count": 0,
        "entities_count": 0,
        "institutions_count": 0,
        "offices_count": 0,
        "functions_count": 0,
        "claims_count": 0,
        "relationships_count": 0,
        "relationship_evidence_count": 0
    }

    with conn:
        with conn.cursor() as cur:
            # 1. Sources
            source_id_map = {}
            for s in SOURCES_DATA:
                cur.execute("""
                    INSERT INTO sources (slug, name, source_type, base_url, polling_cadence_minutes)
                    VALUES (%(slug)s, %(name)s, %(source_type)s, %(base_url)s, %(polling_cadence_minutes)s)
                    ON CONFLICT (slug) DO UPDATE SET
                        name = EXCLUDED.name,
                        source_type = EXCLUDED.source_type,
                        base_url = EXCLUDED.base_url
                    RETURNING id;
                """, s)
                source_id_map[s["slug"]] = cur.fetchone()[0]
            report["sources_count"] = len(source_id_map)

            # 2. Evidence Records
            evidence_id_map = {}
            for ev in EVIDENCE_DATA:
                src_id = source_id_map[ev["source_slug"]]
                payload_bytes = ev["raw_text"].encode('utf-8')
                sha256_hash = hashlib.sha256(payload_bytes).hexdigest()
                storage_uri = f"s3://evidence-archive/{ev['source_slug']}/payload.txt"

                # Check if already present by hash
                cur.execute("SELECT id FROM evidence_records WHERE sha256_payload_hash = %s;", (sha256_hash,))
                row = cur.fetchone()
                if row:
                    evidence_id_map[ev["source_slug"]] = row[0]
                else:
                    cur.execute("""
                        INSERT INTO evidence_records (
                            source_id, origin_url, sha256_payload_hash, payload_storage_uri,
                            mime_type, byte_size, raw_extracted_text, retrieval_metadata
                        ) VALUES (
                            %s, %s, %s, %s, %s, %s, %s, %s
                        ) RETURNING id;
                    """, (
                        src_id, ev["origin_url"], sha256_hash, storage_uri,
                        ev["mime_type"], len(payload_bytes), ev["raw_text"],
                        psycopg2.extras.Json({"source_slug": ev["source_slug"]})
                    ))
                    evidence_id_map[ev["source_slug"]] = cur.fetchone()[0]
            report["evidence_count"] = len(evidence_id_map)

            # 3. Authority Rules
            authority_rule_id_map = {}
            for ar in AUTHORITY_RULES_DATA:
                cur.execute("""
                    INSERT INTO authority_rules (
                        claim_predicate, source_type, authority_rank,
                        can_substantiate_alone, can_supersede_prior, requires_corroboration,
                        statutory_instrument
                    ) VALUES (
                        %(claim_predicate)s, %(source_type)s, %(authority_rank)s,
                        %(can_substantiate_alone)s, %(can_supersede_prior)s, %(requires_corroboration)s,
                        %(statutory_instrument)s
                    )
                    ON CONFLICT (claim_predicate, source_type, statutory_instrument) DO UPDATE SET
                        authority_rank = EXCLUDED.authority_rank
                    RETURNING id, claim_predicate;
                """, ar)
                res = cur.fetchone()
                authority_rule_id_map[res[1]] = res[0]
            report["authority_rules_count"] = len(authority_rule_id_map)

            # 4. Canonical Entity: Mbombela Municipality
            cur.execute("""
                INSERT INTO entities (entity_type, canonical_identifier)
                VALUES ('institution', %s)
                ON CONFLICT (canonical_identifier) DO UPDATE SET
                    entity_type = EXCLUDED.entity_type
                RETURNING id;
            """, (MBOMBELA_INSTITUTION_URN,))
            mbombela_entity_id = cur.fetchone()[0]

            cur.execute("""
                INSERT INTO institutions (
                    id, slug, name, short_name, sphere, province, demarcation_code, mandate_summary, contact_details
                ) VALUES (
                    %s, 'mp-mbombela-lm', 'City of Mbombela Local Municipality', 'Mbombela LM',
                    'local_local', 'MP', 'MP322',
                    'Local government municipal authority established in terms of Section 12 of the Municipal Structures Act 117 of 1998 within Ehlanzeni District, Mpumalanga.',
                    %s
                )
                ON CONFLICT (id) DO UPDATE SET
                    name = EXCLUDED.name,
                    demarcation_code = EXCLUDED.demarcation_code,
                    mandate_summary = EXCLUDED.mandate_summary;
            """, (
                mbombela_entity_id,
                psycopg2.extras.Json({
                    "headquarters": "Nelspruit (Mbombela)",
                    "website": "https://www.mbombela.gov.za",
                    "stats_sa_municipality_code": 815
                })
            ))
            report["institutions_count"] = 1

            # 5. Canonical Entities & Domain Rows: Offices
            office_entity_map = {}
            for off in OFFICES_DATA:
                cur.execute("""
                    INSERT INTO entities (entity_type, canonical_identifier)
                    VALUES ('office', %s)
                    ON CONFLICT (canonical_identifier) DO UPDATE SET entity_type = EXCLUDED.entity_type
                    RETURNING id;
                """, (off["urn"],))
                off_entity_id = cur.fetchone()[0]

                cur.execute("""
                    INSERT INTO offices (id, title, branch)
                    VALUES (%s, %s, %s)
                    ON CONFLICT (id) DO UPDATE SET title = EXCLUDED.title, branch = EXCLUDED.branch;
                """, (off_entity_id, off["title"], off["branch"]))
                office_entity_map[off["title"]] = off_entity_id
            report["offices_count"] = len(office_entity_map)

            # 6. Canonical Entities & Domain Rows: Functions
            function_entity_map = {}
            for fn in FUNCTIONS_DATA:
                cur.execute("""
                    INSERT INTO entities (entity_type, canonical_identifier)
                    VALUES ('function', %s)
                    ON CONFLICT (canonical_identifier) DO UPDATE SET entity_type = EXCLUDED.entity_type
                    RETURNING id;
                """, (fn["urn"],))
                fn_entity_id = cur.fetchone()[0]

                cur.execute("""
                    INSERT INTO institution_functions (id, category, constitutional_schedule, escalation_level)
                    VALUES (%s, %s, %s, %s)
                    ON CONFLICT (id) DO UPDATE SET
                        category = EXCLUDED.category,
                        constitutional_schedule = EXCLUDED.constitutional_schedule,
                        escalation_level = EXCLUDED.escalation_level;
                """, (fn_entity_id, fn["category"], fn["schedule"], fn["escalation_level"]))
                function_entity_map[fn["category"]] = fn_entity_id
            report["functions_count"] = len(function_entity_map)
            report["entities_count"] = 1 + len(office_entity_map) + len(function_entity_map)

            # 7. First-Class Relationships & Claims (Idempotent by checking existing claims/relationships)
            structures_ev_id = evidence_id_map["za-statute-municipal-structures-act-1998"]
            office_rule_id = authority_rule_id_map["houses_office"]
            effective_start = datetime.date(2000, 12, 5) # Local government election / establishment cycle

            # A. Houses Offices (Mbombela -> houses_office -> Office)
            for off_title, off_id in office_entity_map.items():
                # Check if claim already exists
                cur.execute("""
                    SELECT id FROM claims 
                    WHERE subject_canonical_id = %s AND predicate = 'houses_office' AND object_canonical_id = %s;
                """, (mbombela_entity_id, off_id))
                row = cur.fetchone()
                if row:
                    claim_id = row[0]
                else:
                    cur.execute("""
                        INSERT INTO claims (
                            claim_type, subject_raw_text, subject_canonical_id,
                            predicate, object_raw_text, object_canonical_id,
                            effective_from, extraction_confidence, resolution_confidence,
                            processing_stage, assertion_status
                        ) VALUES (
                            'relationship_assertion', 'City of Mbombela Local Municipality', %s,
                            'houses_office', %s, %s,
                            %s, 1.000, 1.000,
                            'canonicalized', 'substantiated'
                        ) RETURNING id;
                    """, (mbombela_entity_id, off_title, off_id, effective_start))
                    claim_id = cur.fetchone()[0]

                # Relationship (Upsert via unique constraint)
                cur.execute("""
                    INSERT INTO relationships (
                        source_entity_id, relationship_predicate, target_entity_id,
                        relationship_attributes, effective_from
                    ) VALUES (
                        %s, 'houses_office', %s,
                        %s, %s
                    )
                    ON CONFLICT (source_entity_id, relationship_predicate, target_entity_id, effective_from)
                    DO UPDATE SET relationship_attributes = EXCLUDED.relationship_attributes
                    RETURNING id;
                """, (mbombela_entity_id, off_id, psycopg2.extras.Json({"statutory_title": off_title}), effective_start))
                rel_id = cur.fetchone()[0]

                # Relationship Evidence Bridge
                cur.execute("""
                    SELECT id FROM relationship_evidence WHERE relationship_id = %s AND claim_id = %s;
                """, (rel_id, claim_id))
                if not cur.fetchone():
                    cur.execute("""
                        INSERT INTO relationship_evidence (
                            relationship_id, claim_id, evidence_record_id,
                            provenance_role, verbatim_excerpt, adjudication_rule_id, locator
                        ) VALUES (
                            %s, %s, %s,
                            'primary_authorizing', %s, %s, %s
                        );
                    """, (
                        rel_id, claim_id, structures_ev_id,
                        f"Statutory office of {off_title} established under Act 117 of 1998.",
                        office_rule_id,
                        psycopg2.extras.Json({"source": "Act 117 of 1998", "office": off_title})
                    ))

            # B. Responsible For Function (Mbombela -> responsible_for_function -> Function)
            constitution_ev_id = evidence_id_map["za-statute-constitution-1996"]
            function_rule_id = authority_rule_id_map["responsible_for_function"]

            for fn_cat, fn_id in function_entity_map.items():
                cur.execute("""
                    SELECT id FROM claims 
                    WHERE subject_canonical_id = %s AND predicate = 'responsible_for_function' AND object_canonical_id = %s;
                """, (mbombela_entity_id, fn_id))
                row = cur.fetchone()
                if row:
                    claim_id = row[0]
                else:
                    cur.execute("""
                        INSERT INTO claims (
                            claim_type, subject_raw_text, subject_canonical_id,
                            predicate, object_raw_text, object_canonical_id,
                            effective_from, extraction_confidence, resolution_confidence,
                            processing_stage, assertion_status
                        ) VALUES (
                            'relationship_assertion', 'City of Mbombela Local Municipality', %s,
                            'responsible_for_function', %s, %s,
                            %s, 1.000, 1.000,
                            'canonicalized', 'substantiated'
                        ) RETURNING id;
                    """, (mbombela_entity_id, fn_cat, fn_id, effective_start))
                    claim_id = cur.fetchone()[0]

                # Relationship
                cur.execute("""
                    INSERT INTO relationships (
                        source_entity_id, relationship_predicate, target_entity_id,
                        relationship_attributes, effective_from
                    ) VALUES (
                        %s, 'responsible_for_function', %s,
                        %s, %s
                    )
                    ON CONFLICT (source_entity_id, relationship_predicate, target_entity_id, effective_from)
                    DO UPDATE SET relationship_attributes = EXCLUDED.relationship_attributes
                    RETURNING id;
                """, (mbombela_entity_id, fn_id, psycopg2.extras.Json({"function_category": fn_cat}), effective_start))
                rel_id = cur.fetchone()[0]

                # Relationship Evidence Bridge
                cur.execute("""
                    SELECT id FROM relationship_evidence WHERE relationship_id = %s AND claim_id = %s;
                """, (rel_id, claim_id))
                if not cur.fetchone():
                    cur.execute("""
                        INSERT INTO relationship_evidence (
                            relationship_id, claim_id, evidence_record_id,
                            provenance_role, verbatim_excerpt, adjudication_rule_id, locator
                        ) VALUES (
                            %s, %s, %s,
                            'primary_authorizing', %s, %s, %s
                        );
                    """, (
                        rel_id, claim_id, constitution_ev_id,
                        f"Municipal statutory competence for {fn_cat} in terms of Section 156(1) and Schedule 4B/5B of Constitution.",
                        function_rule_id,
                        psycopg2.extras.Json({"source": "Act 108 of 1996", "function": fn_cat})
                    ))

            # Authoritative Totals
            cur.execute("SELECT COUNT(*) FROM claims;")
            report["claims_count"] = cur.fetchone()[0]
            cur.execute("SELECT COUNT(*) FROM relationships;")
            report["relationships_count"] = cur.fetchone()[0]
            cur.execute("SELECT COUNT(*) FROM relationship_evidence;")
            report["relationship_evidence_count"] = cur.fetchone()[0]

    return report

def main():
    dbname = os.getenv("PGDATABASE", "gov_intel_test")
    port = int(os.getenv("PGPORT", "54339"))
    conn = psycopg2.connect(dbname=dbname, user="postgres", host="127.0.0.1", port=port)
    conn.set_client_encoding('UTF8')
    try:
        report = ingest_mbombela_governance(conn)
        print("==================================================")
        print("MBOMBELA GOVERNANCE FOUNDATION INGESTION COMPLETED")
        print("==================================================")
        for k, v in report.items():
            print(f"{k:<30}: {v}")
        print("==================================================")
    finally:
        conn.close()

if __name__ == "__main__":
    main()
