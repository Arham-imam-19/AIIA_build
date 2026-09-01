# CLAUDE.md — AIIA Clinical Trials Dashboard

Permanent project brief. Read this first in any new session.

## What we are building

A real-time, cloud-based, **GCP-aware Clinical Trial Management System (CTMS) for Ayurveda
research**, for the All India Institute of Ayurveda / Ministry of Ayush.

- **Smart India Hackathon 2026**, problem statement **SIH26046**.
- Interoperable via **CDISC SDTM** and **FHIR**; compliance tracking for **CTRI** and the
  **NDCT Rules 2019**; role-based KPI dashboards for five personas; pharmacovigilance.
- **Synthetic data only. Never real patient data.** This is absolute, not a preference.

A CTMS is project-management software for a clinical trial — like Jira, but tracking
participants, visits and safety events instead of tickets.

## The five differentiating features

Priority order. Each is layered on a working skeleton; none may block the demo.

1. **AI Data-Harmonization Engine** — messy site data mapped to **CDISC SDTM** and **FHIR**,
   with a confidence score per mapping and a human-review queue for low-confidence ones.
   *SDTM is the standard spreadsheet layout regulators expect trial data in — like a tax
   form, same boxes in the same order for everyone. FHIR is the standard format hospital
   systems use to exchange records — the USB-C of health data.*
2. **Real-time pharmacovigilance** — NLP over free-text adverse-event notes to assign
   **MedDRA** codes, severity and causality, plus signal detection over clusters.
   *Pharmacovigilance is drug-safety monitoring. MedDRA is the standard medical dictionary
   that turns "loose motions", "the runs" and "diarrhoea" into one code so events can be
   counted.*
3. **Compliance-by-design** — CTRI registration fields, NDCT-2019 gates enforced in order,
   an immutable audit trail (21 CFR Part 11), e-signatures, and a per-trial compliance score.
4. **Role-based live KPI dashboards** over WebSocket for five personas: Principal
   Investigator, Sponsor, Ethics Committee, Regulator, Clinical Research Coordinator (CRC).
5. **Ayurveda-native data model** — prakriti/dosha, classical formulation and posology,
   AYUSH-specific outcome measures.

## Tech stack

- **Backend** — FastAPI, SQLModel/SQLAlchemy, PostgreSQL, Redis (live updates), Alembic
- **Frontend** — React, Vite, Tailwind, Recharts
- **Infra** — Docker Compose; everything runs with one command
- **AI/ML (later phases)** — scikit-learn; spaCy + medspaCy for adverse-event NLP

## Commands

```bash
docker compose up --build                                      # start everything
docker compose exec backend python scripts/seed.py             # load the synthetic trial
docker compose exec backend python scripts/seed.py --reset     # wipe and reload
docker compose exec backend python scripts/seed.py --passwords # passwords only, keep data
docker compose exec backend python scripts/simulate.py         # fire a live event
docker compose exec backend pytest                             # run the tests
docker compose exec backend alembic check                      # models vs migrations agree?
docker compose down -v                                         # clean slate, drops the DB
```

Ports: frontend 5173, backend 8000, Postgres 5432, Redis 6379.

Demo logins: five personas, password `aiia2026` (`config.DEMO_PASSWORD`, override with
`DEMO_PASSWORD` **before** seeding). `scripts/seed.py` prints them and
`GET /api/auth/demo-users` serves them, development only.

| Role | Email |
| --- | --- |
| Principal Investigator | `meenakshi.sharma@demo.aiia-ctms.in` (site 01) |
| Coordinator | `kavita.nair@demo.aiia-ctms.in` (site 01) |
| Sponsor | `vikram.desai@demo.aiia-ctms.in` |
| Ethics Committee | `lalitha.krishnan@demo.aiia-ctms.in` |
| Regulator | `shri.arvind.kulkarni@demo.aiia-ctms.in` |

All twelve seeded users share that password, so a second site is available for proving scope
(`rajeev.ranjan.sinha@demo.aiia-ctms.in`, site 02). `priya.raghavan@demo.aiia-ctms.in` is an
Administrator — real role, deliberately not one of the five demo personas and not published by
`/api/auth/demo-users`, whose `DEMO_ROLE_ORDER` lists five roles only.

## Phase plan

Work **one phase at a time**. Stop after each and wait for "next".

- [x] **Phase 0** — Scaffold: Docker Compose + Postgres + FastAPI + React, wired and green
- [x] **Phase 1** — Data model, migrations, synthetic seed, read-only API
- [x] **Phase 2** — Auth + RBAC + 5 role dashboards + live KPIs over WebSocket
- [ ] **Phase 3** — Feature 1: AI Data-Harmonization Engine
- [ ] **Phase 4** — Feature 2: pharmacovigilance NLP + signal alerts
- [ ] **Phase 5** — Feature 3: compliance module (CTRI export, NDCT gates, e-signatures, score)
- [ ] **Phase 6** — Feature 5: Ayurveda model + Feature 4 polish + demo seed + rehearsal

### What Phases 0 and 1 actually delivered (done and verified)

Seven tables — `trials`, `sites`, `users`, `subjects`, `visits`, `adverse_events`,
`audit_logs` — built by migration `0001_initial_schema.py`. One synthetic trial:

> **ASHWA-GAD** — multicentre, randomised, double-blind, placebo-controlled trial of
> *Ashwagandha* root churna in adults with Generalised Anxiety Disorder (Ayurvedic
> diagnosis *Chittodvega*), across AIIA Delhi, NIA Jaipur, IPGAE Kolkata, GAU Jamnagar.

Seeded volumes: 1 trial, 4 sites, 12 users, 225 screened / 186 enrolled, 1116 visits,
61 adverse events (4 serious), 84 protocol deviations, 15 audit entries.

The data is deliberately messy where later phases need it to be: AE narratives are written
in coordinator shorthand for Phase 4's NLP, no AE has a MedDRA code yet (that empty column
is Phase 4's work queue), one site carries a planted gastrointestinal cluster for signal
detection, and some serious events were reported to the ethics committee late so Phase 5's
compliance checks have real problems to flag.

### What Phase 2 delivered (done and verified)

**321 tests, all passing.** (`test_health_database_is_connected` needs real Postgres and is
expected to fail outside Docker — its own docstring says so.)

*Auth* — `app/security.py`: bcrypt hashing, JWT issue/verify, and a logout deny-list keyed on
the token's `jti` so signing out kills that one token and not the person's other sessions.
Tokens last `ACCESS_TOKEN_TTL_MINUTES`, default 720 (12 h). `app/routers/auth.py`:
`login`, `logout`, `me`, `demo-users`.

*RBAC* — `app/rbac.py` holds the whole policy: twelve permissions × six roles, plus site
scoping. Two limits apply independently and must not be conflated:

- **Permission** — may this role touch this *kind* of thing? Ethics has no `subject:read`, so
  `/api/subjects` is 403 for them everywhere. Their remit is safety, deviations, compliance.
- **Site scope** — *whose* rows? PI and Coordinator see one hospital. Another site's record is
  **403, not an empty list**, and `?site_id=` cannot widen it. Site-scoped *writes* have their
  `site_id` overwritten from the token, so a payload cannot escape the scope either.

Served at `GET /api/rbac-matrix` and rendered under **Access rules**, so the docs cannot
disagree with the code. Refusals name the missing permission:
`"Ethics Committee cannot do this. Missing permission: subject:read"`.

*Dashboards* — `app/kpi.py` computes every number in one place; `app/routers/dashboard.py`
serves `GET /api/dashboard` with **no `?role=` parameter** — the role comes from the token.
Five screens, 8 tiles + 3–4 panels each, in four renderable shapes
(`table` / `breakdown` / `series` / `checklist`). Admin gets the regulator's view rather than a
sixth screen nobody demos. An unseeded database returns `seeded: false` and a message naming
`seed.py`, not a 500.

*Live* — `app/events.py` is a Redis pub/sub bus on channel `aiia:events` with an **in-process
fallback** when Redis is unreachable; `/api/health` and the header pill report which is in use.
`app/routers/live.py` serves `WS /ws/dashboard?token=…`. The token goes in the query string
because browsers cannot set headers on a WebSocket handshake; an unauthorised socket is
**accepted then closed with 1008** (policy violation), since the handshake has already
succeeded by the time we know who is asking, so there is no 401 to send.

Each socket recomputes *that viewer's* dashboard from the database and pushes the result, so a
pushed payload has been through the same permissions as the HTTP one. The event says only
*that* something changed. A viewer who cannot read subjects gets the event trimmed to
`{type, at, message, detail_withheld}` — naming a record to somebody who cannot open it would
undo the access rules.

*Simulate* — `POST /api/simulate/{enrollment,adverse-event,deviation}` **writes real rows**:
INSERT the subject/AE/visit, INSERT an audit entry attributed to the logged-in user, then
publish. Enrolment goes 186 → 187 because there is a 187th person in the table.
`scripts/seed.py --reset` restores the baseline. Two front doors: the **Simulate an event**
panel (buttons greyed out with a reason for roles that cannot write) and `scripts/simulate.py`,
stdlib-only, which goes over HTTP on purpose — a row written behind the API's back would move
the numbers while announcing nothing.

Deliberate demo beat: `scripts/simulate.py --as sponsor` is refused with
`403 Missing permission: subject:write`. A monitor who could edit the data would undermine the
data, so the refusal *is* the feature.

## Schema management — read before touching tables

**Alembic IS installed and IS the owner of the schema.** `alembic==1.14.0` is in
`backend/requirements.txt`, and `backend/entrypoint.sh` runs `alembic upgrade head` on
every boot before uvicorn starts. Phase 1's tables were created by migration `0001`, not by
`create_all`. The `/api/health` schema light reports the live revision (`rev 0001`).

> Note: an earlier instruction described alembic as absent and the tables as `create_all`-built.
> That was checked and is not the case. This section reflects the verified state — if it ever
> looks wrong, confirm with `docker compose exec backend alembic current` before acting on it.

Rules that follow from this:

- **The app never creates tables.** `app/db.py:create_all_tables()` exists for tests only.
  Adding `create_all()` to a startup path would silently paper over a forgotten migration.
- **New table or column ⇒ new migration** in `backend/alembic/versions/`, numbered
  (`0002_...`), and `backend/tests/test_migrations.py` must still pass. That test runs the
  migrations into a throwaway SQLite database and diffs the result against the models
  column by column, so a model change with no migration fails the tests rather than
  production.
- `alembic check` must print `No new upgrade operations detected.`
- The underlying constraint still holds: **a one-command boot outranks migration purity.**
  If migrations ever block `docker compose up --build`, fix the boot first and reconcile
  the schema after.

## Working rules

- **One phase at a time.** State the goal in one line, build, then give the exact commands
  to run and how to verify. Then **STOP** and wait for "next". Never start the next phase.
- **Define every new term in one plain sentence with a real-world analogy** before using
  it. The user knows basic Python and React, but not clinical-trial or web jargon. This
  applies to SDTM, FHIR, RBAC, JWT, WebSocket, pub/sub, signal detection, MedDRA — all of it.
- **Ship a working end-to-end skeleton early.** AI features layer on top and never block.
- **Simple, readable code over cleverness.** It must run on a laptop.
- When the user pastes an error: explain the cause in plain English first, then fix it.
- Commit after each phase with a clear message — **but ask first.** See the hazard below.
- Optimise for a complete, clickable, demo-ready system over perfection. It is a hackathon.

## Repository hazard — ask before any git operation

The git repository root is **`/Users/afroz`**, the user's entire home directory, not the
project folder. There is no root `.gitignore`, and `/Users/afroz/.claude.json` contains
OAuth credentials. A careless `git add -A` would stage the user's whole home directory
including secrets.

`/Users/afroz/Adlm/.gitignore` covers the project subtree only. **Never stage or commit
without asking the user how they want this handled.** No Phase 0 or Phase 1 commit has been
made yet for this reason.

## Layout

```
.
├── CLAUDE.md              # this file
├── docker-compose.yml     # the whole system, one command
├── backend/
│   ├── alembic/versions/  # numbered migrations - the real schema
│   ├── app/
│   │   ├── main.py        # app setup, health, info
│   │   ├── config.py      # settings, plain os.getenv
│   │   ├── db.py          # engine, sessions, health check
│   │   ├── enums.py       # controlled vocabularies (roles, statuses, severities)
│   │   ├── security.py    # bcrypt, JWT issue/verify, logout deny-list
│   │   ├── rbac.py        # the whole access policy: permissions + site scope
│   │   ├── audit.py       # append-only audit writer
│   │   ├── kpi.py         # every dashboard number, one place
│   │   ├── events.py      # Redis pub/sub bus + in-process fallback
│   │   ├── models/        # the seven tables as SQLModel classes
│   │   ├── routers/       # the API, one file per area
│   │   │   ├── auth.py       # login, logout, me, demo-users
│   │   │   ├── dashboard.py  # the five role screens
│   │   │   ├── live.py       # WS /ws/dashboard
│   │   │   ├── simulate.py   # write a real row, then broadcast
│   │   │   └── ...           # trials, subjects, safety, compliance, stats, common
│   │   └── synthetic.py   # the data generator - pure Python, no database
│   ├── entrypoint.sh      # wait for Postgres, migrate, then start uvicorn
│   └── tests/             # 321 tests
├── frontend/src/
│   ├── auth.jsx           # who is signed in; the token lives here
│   ├── api.js             # fetch wrapper, attaches the token
│   ├── useLiveDashboard.js # the WebSocket, reconnect, change flagging
│   ├── blocks.jsx         # the four panel renderers
│   ├── dashboards/        # one file per persona
│   ├── Login.jsx  Shell.jsx  RbacMatrix.jsx  Simulate.jsx
│   └── App.jsx  main.jsx  index.css
└── scripts/
    ├── seed.py            # inserts the generated data, sets demo passwords
    └── simulate.py        # fire events from a terminal (stdlib only, over HTTP)
```

## Known follow-ups, deliberately not done yet

Noted so they are not rediscovered as bugs:

- **Phase 4 realism.** All four `SAE_CATALOGUE` templates are SEVERE and no non-serious
  template is, so in the seeded data severe ⟺ serious. That means the dataset never
  demonstrates the severity-vs-seriousness distinction the code teaches. Worth fixing when
  Phase 4 touches the safety data. (AE severity being ~90 % mild is *not* a bug — it matches
  the catalogue weights.)
- **No commits yet.** Phases 0–2 are all unstaged, for the reason above.
- **Never rendered in a browser.** The frontend has been parse-checked and every import
  resolves, but `npm install` and `docker compose up --build` have not been run in this
  environment. First real boot may surface ordinary wiring errors.
