# SIH26046 AIIA Clinical Trials Dashboard

The AIIA Clinical Trials Dashboard is a synthetic-data Clinical Trial Management System (CTMS) built for Smart India Hackathon problem statement **SIH26046**. It demonstrates controlled trial activation, participant and visit workflows, safety review, institution administration, patient self-service, auditability, and role-shaped live dashboards for an Ayurveda research scenario.

> **Synthetic data only.** This is a demonstration system. Do not use it with real patient data or as a production clinical, regulatory, or pharmacovigilance system without independent engineering, privacy, security, clinical, and regulatory validation.

## Problem statement and objectives

Trial teams need to coordinate approvals, sites, recruitment, visits, safety, consent, and oversight without exposing data outside each user's remit. The project demonstrates server-enforced role/site boundaries, traceable clinical state transitions, Patient self-service, de-identified oversight, live operational views, and transparent safety decision support.

## Implemented capabilities

- JWT staff and Patient authentication, logout token revocation, bcrypt password hashes, and development-only demo accounts.
- Eight-role RBAC, server-side site scoping, and fail-closed behavior.
- Ethics, CTRI, regulatory-readiness, compliance, and trial-activation workflows.
- Subject screening, failure, enrollment/randomization, activation, visits, completion, withdrawal, and lost-to-follow-up workflows.
- Transactional audit records for supported production mutations.
- Institution/site and scoped staff administration.
- Adverse-event review, serious-event dashboards, exact-term PRR signal calculations, and de-identified safety-case PDFs.
- Separate staff and Patient portals, Patient dashboard, visits, inquiries/requests, and electronic informed consent.
- Role-shaped dashboards and WebSocket updates through Redis with a single-process fallback.
- Deterministic synthetic data, seeding, and simulation tools.

## Architecture and stack

```text
Browser -> React/Vite (:5173) -> FastAPI (:8000) -> PostgreSQL 16 (:5432)
   ^              |                    |
   +---- /ws -----+                    +-> Redis 7 (:6379)
```

| Layer | Repository-confirmed implementation |
| --- | --- |
| Frontend | React 18, Vite 6, Tailwind CSS, Recharts |
| API | Python, FastAPI 0.115.6, Uvicorn 0.34.0 |
| ORM/validation | SQLModel 0.0.22, SQLAlchemy, Pydantic via FastAPI |
| Data/schema | PostgreSQL 16, Alembic 1.14.0; SQLite in tests |
| Auth/live | PyJWT 2.10.1, bcrypt 5.0.0, Redis 7/redis-py 5.2.1, WebSockets |
| PDF | ReportLab 4.2.5; pypdf 5.1.0 in generated-file tests |
| Packaging | Docker Compose |

The backend entrypoint waits for PostgreSQL, applies `alembic upgrade head`, and starts Uvicorn. Vite proxies `/api` and `/ws`. The API enforces authorization; hidden frontend controls are not security boundaries.

## Eight roles and authorization boundaries

`backend/app/rbac.py` and `GET /api/rbac-matrix` are authoritative.

| Role key | Scope | Boundaries |
| --- | --- | --- |
| `admin` | Trial-wide | All defined permissions, including administration and export. |
| `institution_admin` | Own site | Clinical/compliance/user/request/e-consent reads; user management and Patient responses; no clinical writes/export. |
| `principal_investigator` | Own site | Clinical read/write and compliance/user/request/e-consent read; no export or trial-wide approval writes. |
| `coordinator` | Own site | Subject, visit, AE read/write plus request/e-consent read; no compliance, user management, or export. |
| `patient` | Own site and linked Subject | Permitted trial/site/visit reads; own requests and own e-consent. No Subject-read, AE-read, audit, user, or export permission. |
| `sponsor` | Trial-wide | Read, compliance, CTRI/regulatory updates, activation, and export; no site clinical writes. Output must remain de-identified. |
| `ethics_committee` | Trial-wide | Trial/site/visit/AE/compliance/audit/e-consent read and ethics updates; deliberately no Subject-read/export. |
| `regulator` | Trial-wide | Read-only oversight of clinical/compliance/audit/user/e-consent data plus export. |

Site-scoped queries are narrowed by the API, and direct cross-site access returns `403`. Patients are further limited to their linked Subject for owned workflows. Every route still requires its declared permission.

## Clinical workflows

Trial activation evaluates protocol facts, dates, current ethics approval, CTRI registration, regulatory approval, and lifecycle state. An eligible trial becomes `recruiting`; incomplete, expired, or inconsistent gates return controlled errors.

```text
screening -> not_randomized
screening -> enrolled -> active -> completed
             |           |       -> withdrawn
             +-----------+------ -> lost_to_follow_up
```

Screening requires a recruiting Trial and Site. The server assigns Subject code, initial state, timestamps, and effective site. Enrollment requires ordered non-future dates and a randomized arm. Activation confirms first dose, persists the `active` status and updated timestamp, and writes an activation audit entry; the Subject model has no `first_dose_date` field. Terminal outcomes require appropriate dates/reasons.

Authorized site users explicitly schedule one visit for an enrolled/active Subject. `(subject_id, visit_number)` is unique. A scheduled visit may be completed or marked missed after its window; out-of-window completion becomes a protocol deviation requiring a description. Production does not auto-expand a protocol schedule.

Adverse events store trial/site/Subject, severity, seriousness, causality, outcome, reporting, and optional coding fields. Supported clinical mutations and their audit entry share a transaction. Audit append-only behavior is an application convention, not a database trigger.

## Safety-signal detection

`GET /api/trials/{trial_id}/safety-signals` groups exact `term_verbatim` values and calculates `a`, `b`, `c`, `d`, PRR, and Pearson chi-square for every visible target-site/term pair. The full trial forms the comparator while target sites remain scoped. Ordering is deterministic; zero denominators return explicit non-estimable results.

A demonstration signal requires `a >= 3`, `PRR >= 2`, and chi-square `>= 4`. This is **demonstration decision support only**: no normalization, medical coding, or MedDRA population occurs, and it is not validated NPvCC/pharmacovigilance detection. Patient and anonymous access are denied.

## De-identified safety PDF

`GET /api/adverse-events/{event_id}/safety-report.pdf` requires `export`, granted only to Administrator, Sponsor, and Regulator. All other roles and anonymous callers are denied. It loads only Trial, Site, de-identified Subject, and AdverseEvent data. It does not query/render Patient names/emails, EConsent signer/signature data, ABHA IDs, IP addresses, user agents, or Patient-request messages. Missing events return `404`; inconsistent linkage returns `409`.

The PDF is a **de-identified demonstration decision-support artifact**, not an official regulatory submission or standardized CDSCO, CIOMS, or NPvCC form. The Regulator dashboard has a one-click action; Ethics sees the safety table without export.

## Patient portal and e-consent

Patients use `/api/auth/patient/login`; staff and Patient portals reject wrong-account types with generic invalid-credential responses. Implemented Patient workflows include a Patient dashboard, own visits, creating/reviewing own inquiries, receiving site-scoped institution responses, reading consent information/status, signing/replacing their own e-consent, and retrieving their own certificate.

Consent stores signer identity, language, optional ABHA ID, signature data, SHA-256 digest, status, time, IP, and user agent. These sensitive fields are excluded from Sponsor safety output. Hashing and audit logging do not themselves establish legal/regulatory compliance.

## Demo access and live updates

In development, `GET /api/auth/demo-users` supplies the available synthetic staff personas used by the demo interface. Staff sign in through the staff login; Patients use the separate Patient login. Demo-user endpoints and buttons are development conveniences and should not be exposed as a production authentication design.

Dashboard updates are delivered over WebSocket. Redis provides pub/sub fan-out; if Redis is unavailable, one backend process can use the in-process fallback. That fallback does not distribute updates across multiple backend processes.

With the backend running and the intended synthetic database confirmed, safe simulation examples are:

```powershell
docker compose exec backend python scripts/simulate.py
```

```powershell
docker compose exec backend python scripts/simulate.py adverse-event --serious
```

Simulation writes persistent synthetic rows to the connected database. Confirm the target database and obtain approval before running it; do not reset the preserved database to undo simulation output.

## Repository structure

```text
.
|-- README.md / HANDOVER.md
|-- docker-compose.yml / .env.example
|-- backend/
|   |-- app/{models,routers,services}/
|   |-- alembic/versions/       migrations 0001-0005
|   |-- tests/
|   |-- requirements.txt
|   `-- README.md               detailed backend contracts
|-- frontend/{src,package.json}
`-- scripts/{seed.py,simulate.py}
```

## Environment and Docker

Prerequisites are Git, Docker with Compose, and free ports `5173`, `8000`, `5432`, `6379`. Compose defaults work without `.env`; optional overrides:

```powershell
Copy-Item .env.example .env
```

Never commit real credentials. Non-development deployments must override the insecure development `JWT_SECRET` and review `APP_ENV`, `DATABASE_URL`, `REDIS_URL`, `CORS_ORIGINS`, token lifetime, and demo password. The committed stack sets `APP_ENV=development`.

Start:

```powershell
docker compose up --build
```

Background start:

```powershell
docker compose up --build -d
```

Frontend: `http://localhost:5173`; API: `http://localhost:8000/`; health: `http://localhost:8000/api/health`.

Stop while preserving PostgreSQL data:

```powershell
docker compose down
```

Do **not** use `docker compose down -v` during normal work; it deletes the database volume. Back up important databases before destructive operations.

## Database and migrations

Alembic revisions are `0001_initial_schema.py`, `0002_trial_activation_fields.py`, `0003_visit_subject_number_unique.py`, `0004_user_hierarchy_and_patient_portal.py`, and `0005_digital_econsent.py`. Startup upgrades automatically. Manual commands with the backend running:

```powershell
docker compose exec backend alembic upgrade head
```

```powershell
docker compose exec backend alembic check
```

Add/review a migration for every schema change. Never hand-edit a deployed schema, use application `create_all()` as a deployment substitute, reseed a preserved database, or delete its volume casually.

## Synthetic data

```powershell
docker compose exec backend python scripts/seed.py
```

Set passwords without replacing trial rows:

```powershell
docker compose exec backend python scripts/seed.py --passwords
```

This intentionally replaces seeded data and requires explicit approval:

```powershell
docker compose exec backend python scripts/seed.py --reset
```

The synthetic multi-site Ashwagandha trial contains a Jaipur site 02 exact-term `Loose stools` cluster for the PRR demonstration. No real Patient data is supported.

## Tests and API documentation

Backend full suite:

```powershell
docker compose run --rm backend pytest -q
```

Focused safety and migration checks:

```powershell
docker compose run --rm backend pytest -q tests/test_safety_signals.py tests/test_safety_report_export.py
```

```powershell
docker compose run --rm backend pytest -q tests/test_migrations.py
```

The frontend defines no automated `test` script. Its available verification is:

```powershell
docker compose run --rm frontend npm run build
```

Do not invoke/document `npm test` until a runner/script exists. With the API running, use Swagger at `http://localhost:8000/docs`, ReDoc at `/redoc`, and OpenAPI JSON at `/openapi.json`. Generated OpenAPI is authoritative. Some static metadata in `backend/app/main.py` still describes proposed capabilities as delivered; it is not evidence of compliance or AI/interoperability implementation.

## Privacy and security properties

- Synthetic data only; real patient data is unsupported.
- Bcrypt password hashes, signed JWTs, database User rechecks, and logout revocation.
- Server-side permissions and site scope.
- Patients lack Subject/AE/audit/user/export permission.
- Sponsor PDF output has a narrow de-identified data boundary excluding Patient account, consent/signature, ABHA, message, IP, and user-agent data.
- Supported mutations and audit rows commit together; rollback paths are tested.
- Generated PDF tests parse output and assert protected fields are absent.

These are implementation properties, not certifications. TLS, external secrets, backup/restore, encryption, monitoring, retention, incident response, penetration testing, and deployment hardening are not established here.

## Warnings, limitations, and compliance disclaimer

- Demonstration CTMS, not a validated production clinical system.
- No formal GCP, CDSCO, CIOMS, NPvCC, CDISC SDTM, FHIR, 21 CFR Part 11, or other compliance is claimed.
- No AI/ML medical-coding engine, MedDRA population, CDISC export, or FHIR representation exists.
- AE production routes are read-only; synthetic simulation creates demo events.
- No automatic production visit schedule, rescheduling/cancellation/amendment workflow, database row-level security, or database audit trigger.
- Production Subject/Visit writes do not publish simulation events; Redis fallback cannot cross backend processes.
- Frontend has no automated tests. Verified build may show Vite's bundle warning.
- ReportLab tests may show a third-party `ast.NameConstant` deprecation warning.

Domain references describe context, fields, gates, or future direction only; they do not mean certification, validation, acceptance, or compliance. Clinical, privacy, legal, regulatory, and security specialists must evaluate any real-world use.

## Troubleshooting

- **Backend problem:** inspect backend output with `docker compose logs backend`.
- **Empty synthetic database:** first confirm that the backend points to the intended database. Run `docker compose exec backend python scripts/seed.py` only after receiving approval; seeding writes persistent synthetic data.
- **Existing users have no demo passwords:** after confirming the database and approval, use `docker compose exec backend python scripts/seed.py --passwords`; this updates demo passwords without replacing trial rows.
- **Demo buttons are absent:** the demo-user endpoints and buttons are development-only. Confirm `APP_ENV=development`; their absence outside development is expected.
- **Expired-token `401`:** sign in again through the correct staff or Patient portal and use the new bearer token.
- **Permission or site-scope `403`:** verify the signed-in role, required permission, assigned site, and target record. Client filters cannot widen server-enforced scope.
- **Redis fallback is active:** a single backend can continue with in-process fan-out, but updates will not cross multiple backend processes. Inspect health and backend logs for the Redis connection detail.
- **WebSocket does not connect:** verify the backend and frontend are running, inspect backend logs, confirm the Vite `/ws` proxy target, and check whether a proxy or VPN blocks WebSocket upgrade requests. Ordinary dashboard refresh remains available.

## Recommended future work (not implemented)

1. Build one narrow de-identified interoperability output based only on present fields: CDISC-inspired DM/SV/AE CSV **or** FHIR-aligned ResearchStudy JSON. Require export authorization, privacy/linkage/schema/empty-data/determinism tests, and demonstration labeling.
2. Add frontend automated tests for authentication, Patient flows, role actions, and downloads.
3. Add controlled production AE creation/review and protocol-specific visit/correction workflows.
4. Add deployment hardening, secret management, backups, monitoring, retention, security review, and suitable database controls.
5. Correct stale runtime metadata/comments that overstate GCP, AI, interoperability, or regulatory capability.
6. Address bundle size only as a separately approved performance task.

An AI/ML medical-coding engine remains explicitly out of scope.
