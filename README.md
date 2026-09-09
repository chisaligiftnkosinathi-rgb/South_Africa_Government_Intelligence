# South African Government Intelligence & Civic Platform

A platform bridging civic education, constitutional accountability, and public procurement transparency across all spheres of the South African state.

> **Learn how government works → understand who has authority → see what government is buying → track tenders → connect opportunities to the responsible institution.**

---

## 🏛️ Core Architecture Pillars

1. **Government Atlas**: Interactive mapping of institutions, constitutional mandates (Schedule 4/5), political leadership, administrative offices, and municipal wards.
2. **Civic Academy**: Educational workflows breaking down constitutional structures, municipal budgets, and supply chain management (SCM) processes.
3. **Procurement Observatory**: Ingestion and structured monitoring of tenders, awards, RFQs, CIDB gradings, and compliance requirements from national, provincial, and local bodies.
4. **Government Explainer**: Zero-hallucination institutional reasoning engine backed by verifiable evidence.
5. **Opportunity Intelligence**: Matching suppliers and SMEs to relevant public sector opportunities.

---

## 🔒 Evidence Architecture

The system enforces a strict evidentiary lineage:
$$\text{Official Source (Gazettes, Portals, Minutes)} \longrightarrow \text{Evidence Snapshot} \longrightarrow \text{Entity / Edge Graph} \longrightarrow \text{AI Reasoning}$$

No claim regarding institutional authority, municipal budgets, or procurement awards is surfaced without a cryptographic content hash and link to an official source record.

---

## 📁 Repository Structure

```text
├── docs/
│   └── architecture/
│       └── canonical_data_model.md   # Supabase/PostgreSQL schema specification
├── apps/                             # Frontend & API applications (upcoming)
├── packages/                         # Shared libraries, schemas, validators
├── workers/                          # Ingestion workers & scrapers (Railway)
└── README.md
```

See [docs/architecture/canonical_data_model.md](docs/architecture/canonical_data_model.md) for the complete data model specification.
