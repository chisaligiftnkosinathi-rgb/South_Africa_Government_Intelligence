# Agent Operating Contract (AOC)

This document governs the multi-agent collaboration model for the **South African Government Intelligence & Civic Platform**.

---

## 1. Separation of Concerns & Roles

| Entity | Role | Responsibilities | Permissions |
| :--- | :--- | :--- | :--- |
| **User (You)** | **Product Owner & Release Authority** | Sets priorities, goals, boundaries, authorizes code changes, and holds exclusive push authority. | Full Authority + Git Push (`git push`) |
| **ChatGPT** | **Architect, Reviewer, & Analyst** | Researches legal/civic domains, critiques schema designs, specifies entity contracts, and inspects committed code. | GitHub Read (`pull: true`, `push: false`) |
| **Antigravity** | **Implementation & Engineering Agent** | Writes code in `c:\Projects\South_Africa`, writes database migrations, creates automated tests, runs verification commands, and creates local Git commits. | Workspace Write + Local Git Commit (No push) |
| **GitHub** | **Shared State of Truth** | Central synchronized source for repository files, specifications, migrations, documentation, and tests. | Canonical VCS |

---

## 2. The Development & Review Loop

```mermaid
sequenceDiagram
    autonumber
    actor User as Product Owner
    participant GPT as ChatGPT (Architect / Reviewer)
    participant AGY as Antigravity (Implementer)
    participant GH as GitHub (Repo)

    GPT->>User: Issues architectural critique & explicit task contract
    User->>AGY: Passes task contract
    Note over AGY: Implements code & writes tests in local workspace
    AGY->>AGY: Executes local verification & tests
    AGY->>AGY: Creates local Git commit (No push)
    AGY->>User: Reports completion with commit hash & changes
    User->>User: Reviews and executes "git push origin main"
    User->>GPT: Requests review of commit on GitHub
    GPT->>GH: Inspects diffs, migrations, and files directly
    GPT->>User: Approves or issues structured feedback
```

---

## 3. Engineering Invariants & Guardrails

1. **Evidence-First Invariant**:
   - **No bare scrapers**: Never do `scraper -> database -> AI`.
   - Every scraped payload, document, or gazette notice must first land in `evidence_records` with an immutable SHA-256 hash, captured timestamp, and source URL before any structured entity (`institutions`, `offices`, `tenders`) or relational edge is substantiated.
2. **Entity-Office Decoupling**:
   - People never belong directly to an `institution`. People hold `offices` via `person_appointments`.
   - Wards strictly belong to exactly one local municipality within a defined demarcation cycle.
3. **Small, Coherent Commits**:
   - Every commit must represent a single, reviewable unit of work (e.g. `docs: ...`, `schema: ...`, `test: ...`).
   - Every change must pass verification before being committed.
4. **Push Boundary**:
   - Only the Product Owner runs `git push`. Antigravity creates local commits only.
