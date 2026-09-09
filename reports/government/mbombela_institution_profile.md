# Government Institutional Profile: City of Mbombela Local Municipality (MP322)

**Publication Date**: 2026-09-09  
**Platform Tier**: Government Atlas (Foundation Slice)  
**Status**: Authoritatively Substantiated (Fail-Closed Evidence Model)

---

## 1. Institution Identity & Legal Status

| Attribute | Canonical Value | Evidentiary Basis |
| :--- | :--- | :--- |
| **Legal Name** | City of Mbombela Local Municipality | Mpumalanga Provincial Gazette Extraordinary No. 638 (Notice 356 of 2000) |
| **Short / Colloquial Name**| Mbombela LM | Section 12 Establishment Notice |
| **Sphere of Government** | Local Government (`local_local`) | Constitution of the Republic of South Africa, 1996 (Chapter 7) |
| **Province** | Mpumalanga (`MP`, Code: `8`) | Section 103(1) of Constitution of the Republic of South Africa, 1996 |
| **District Municipality** | Ehlanzeni District Municipality (`DC32`) | Notice 356 of 2000 / Municipal Demarcation Board |
| **Demarcation Code** | `MP322` | Official Gazette Notice 356 of 2000 |
| **Canonical Entity URN** | `urn:za:gov:institution:local:mp322:mbombela` | Global Entity Registry (`entities` table) |

---

## 2. Geographic Jurisdiction & Demographic Cross-Reference

> **Architectural Boundary Note**: The geographic reference layer (Stats SA Census data) and the governance entity layer are **completely decoupled**. No foreign keys exist between `main_places`/`sub_places` and `institutions`. The linkage is established via explicit cross-reference metadata.

* **Stats SA Municipality Identifier**: `815` (`Mbombela`)
* **Underlying Main Places**: Exactly **25** official Main Places (from `81501 Broedershoek` to `81525 Nsikazi Part 2`, including `Nelspruit`, `Hazyview`, `Kanyamazane`, and `White River`).
* **Underlying Sub Places**: Exactly **108** official Sub Places.
* **Geographic Provenance**: Stats SA 2011 Census (`v2011.1`).

---

## 3. Legal & Constitutional Authority

The municipality derives its statutory existence and executive authority from:
1. **Constitution of the Republic of South Africa, 1996 (Act No. 108 of 1996)**:
   * **Section 151(1)**: Establishes the local sphere of government consisting of municipalities across the territory of the Republic.
   * **Section 156(1)**: Assigns executive authority and the right to administer local government matters listed in Schedules 4B and 5B.
2. **Local Government: Municipal Structures Act, 1998 (Act No. 117 of 1998)**:
   * **Section 12 Notice**: Formal establishment of the municipality as a Category B (local) municipal authority with a mayoral executive system combined with a ward participatory system.
3. **Local Government: Municipal Systems Act, 2000 (Act No. 32 of 2000)**:
   * Establishes the legal nature of a municipality as encompassing political structures, administration, and community.

---

## 4. Evidenced Institutional Structure & Statutory Offices

The following offices are formally substantiated in the canonical graph via first-class `houses_office` relationships:

| Office Title | Branch | Canonical URN | Authorizing Statutory Instrument |
| :--- | :--- | :--- | :--- |
| **Municipal Manager** | Administrative | `urn:za:gov:office:mp322:municipal-manager` | Section 82 of Local Government: Municipal Structures Act 117 of 1998 (Head of Administration & Accounting Officer) |
| **Executive Mayor** | Political | `urn:za:gov:office:mp322:executive-mayor` | Section 48 of Local Government: Municipal Structures Act 117 of 1998 |
| **Speaker of Council** | Political | `urn:za:gov:office:mp322:speaker` | Section 36 of Local Government: Municipal Structures Act 117 of 1998 (Chair of Council) |

> **Strict Governance Invariant**: No natural person is directly attached to the institution. People may only enter the canonical graph via `person_appointments` occupying a specific, substantiated `office`.

---

## 5. Evidenced Statutory Functions

The following competencies are formally linked to the municipality via first-class `responsible_for_function` relationships:

| Functional Category | Constitutional Schedule | Escalation Level | Statutory Source |
| :--- | :--- | :--- | :--- |
| **Potable Water Supply & Sanitation** | Schedule 4B | Level 1 (Local Authority) | Constitution of the Republic of South Africa, 1996 (Section 156(1) & Schedule 4B) |
| **Electricity Reticulation** | Schedule 4B | Level 1 (Local Authority) | Constitution of the Republic of South Africa, 1996 (Section 156(1) & Schedule 4B) |
| **Municipal Roads & Pothole Maintenance** | Schedule 5B | Level 1 (Local Authority) | Constitution of the Republic of South Africa, 1996 (Section 156(1) & Schedule 5B) |
| **Refuse Removal & Solid Waste Disposal**| Schedule 5B | Level 1 (Local Authority) | Constitution of the Republic of South Africa, 1996 (Section 156(1) & Schedule 5B) |

---

## 6. Evidentiary Traceability & Provenance Chain

Every canonical fact in this profile resolves back to immutable snapshots:

```text
CANONICAL RELATIONSHIP: (Mbombela LM) -[responsible_for_function]-> (Potable Water Supply)
  ├── Edge ID              : relationships.id (UUID)
  ├── Predicate            : responsible_for_function
  ├── Effective Date       : 2000-12-05 (Local government establishment cycle)
  ├── Claim Record         : claims.id (stage: canonicalized, status: substantiated)
  ├── Evidence Bridge      : relationship_evidence (role: primary_authorizing)
  ├── Adjudication Rule    : authority_rules (gazette / Constitution, rank = 1)
  ├── Evidence Record      : evidence_records.id (UUID)
  │     ├── SHA-256 Hash   : b0df7c67761002db6869b2d716d1f0ea092a95c478a59b6fe18544c41498b584
  │     ├── Storage URI    : s3://evidence-archive/za-statute-constitution-1996/payload.txt
  │     └── Verbatim Excerpt: "Section 156(1) and Schedule 4B & 5B: Water and sanitation services..."
  └── Origin Source        : sources.slug = 'za-statute-constitution-1996'
```

---

## 7. Confidence & Evidentiary Strength Evaluation

* **Institutional Existence & Demarcation (`MP322`)**: **High / Authoritative** (Gazette Notice 356 of 2000).
* **Statutory Offices (`Municipal Manager`, `Mayor`, `Speaker`)**: **High / Authoritative** (Act 117 of 1998 statutory mandate).
* **Core Service Functions**: **High / Authoritative** (Constitutional Schedule 4B/5B competence).

---

## 8. Explicit Unknowns & Fail-Closed Boundaries

In strict adherence to the platform's anti-hallucination mandate, the following areas remain **unresolved (unknown)** pending primary authoritative evidence:

1. **Current Incumbents / Appointed Officials**:
   * *Status*: **UNKNOWN — Insufficient Evidence**.
   * *Rationale*: While council websites or media mention current politicians, no audited Council Resolution extract or Provincial Gazette appointment notice has been ingested yet. No human appointment edges exist in the database.
2. **Current Ward Councillor Assignments**:
   * *Status*: **UNKNOWN — Insufficient Evidence**.
   * *Rationale*: Ward boundary Gazette notices and Electoral Commission (IEC) declared results have not yet been ingested.
3. **Delegated Financial Thresholds**:
   * *Status*: **UNKNOWN — Insufficient Evidence**.
   * *Rationale*: Awaiting formal ingestion of the City of Mbombela SCM Policy and Council Delegations Register.
