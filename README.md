# AIIA Clinical Trials Dashboard

A real-time, cloud-based, GCP-compliant **Clinical Trial Management System (CTMS)** for
Ayurveda research — built for Smart India Hackathon 2026, problem statement **SIH26046**
(Ministry of Ayush / All India Institute of Ayurveda).

> **All data in this system is synthetic.** No real patient data is used anywhere.

---

## Quick start

```bash
docker compose up --build
```

Then open:

| What | Where |
| --- | --- |
| Dashboard (React) | http://localhost:5173 |
| API root | http://localhost:8000 |
| Interactive API docs | http://localhost:8000/docs |
| Health check | http://localhost:8000/api/health |

The dashboard shows five status lights — React, FastAPI, PostgreSQL, the schema, and the
synthetic data. The first four go green on their own once the stack boots. The fifth stays
red until you load the data:

```bash
docker compose exec backend python scripts/seed.py
```

That inserts one complete synthetic trial: 4 sites, 12 users, 225 screened participants
(186 enrolled), ~1,100 visits, ~60 adverse events and a starting audit trail. It also gives
every user a password and prints the demo logins. Reload the dashboard and sign in.

---

## Signing in

Five personas, one shared password. The seed script prints them; they are also the one-click
buttons on the login screen, served by `GET /api/auth/demo-users` (which answers only while
`APP_ENV=development` — a deployed system must never hand out logins).

| Role | Email | Sees |
| --- | --- | --- |
| Principal Investigator | `meenakshi.sharma@demo.aiia-ctms.in` | Site 01 New Delhi only |
| Clinical Research Coordinator | `kavita.nair@demo.aiia-ctms.in` | Site 01 New Delhi only |
| Sponsor | `vikram.desai@demo.aiia-ctms.in` | All sites, read-only |
| Ethics Committee | `lalitha.krishnan@demo.aiia-ctms.in` | All sites: safety, deviations, compliance |
| Regulator | `shri.arvind.kulkarni@demo.aiia-ctms.in` | All sites, read-only, plus the audit trail |

**Password: `aiia2026`** for all of them. Change it with `DEMO_PASSWORD` in `.env` *before*
seeding. The database stores a bcrypt hash, never the password itself.

All twelve seeded users get the same password, not just these five — useful when you want a
*second* site to prove the scoping. NIA Jaipur's investigator is
`rajeev.ranjan.sinha@demo.aiia-ctms.in`; their coordinator is `sunil.meena@demo.aiia-ctms.in`.
There is also an Administrator, `priya.raghavan@demo.aiia-ctms.in`, who can do everything —
deliberately left off the login screen, because "the account that bypasses the rules" is not a
persona worth demoing.

Log in by hand if you prefer:

```bash
curl -s -X POST http://localhost:8000/api/auth/login -H 'Content-Type: application/json' -d '{"email":"vikram.desai@demo.aiia-ctms.in","password":"aiia2026"}'
```

That returns an **access token** — a signed ID card the server hands you at login. Send it
back on every request as `Authorization: Bearer <token>`. It lasts 12 hours; logging out
cancels that one token and leaves your other sessions alone.

---

## Who can do what

**RBAC** (role-based access control) attaches permissions to job titles rather than to
people — a hotel keycard opens your floor, the manager's opens every floor. The table below
is generated from `backend/app/rbac.py`, served live at `GET /api/rbac-matrix`, and rendered
in the UI under **Access rules**.

| Permission | Principal Investigator | Coordinator | Sponsor | Ethics Committee | Regulator | Administrator |
| --- | --- | --- | --- | --- | --- | --- |
| `trial:read` — view the trial and its protocol | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ |
| `site:read` — view participating sites | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ |
| `subject:read` — view participants | ✅ | ✅ | ✅ | — | ✅ | ✅ |
| `subject:write` — screen and enrol participants | ✅ | ✅ | — | — | — | ✅ |
| `visit:read` — view the visit schedule | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ |
| `visit:write` — record visits | ✅ | ✅ | — | — | — | ✅ |
| `ae:read` — view adverse events | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ |
| `ae:write` — report adverse events | ✅ | ✅ | — | — | — | ✅ |
| `compliance:read` — view ethics and regulatory compliance | ✅ | — | — | ✅ | ✅ | ✅ |
| `audit:read` — view the audit trail | — | — | — | ✅ | ✅ | ✅ |
| `user:read` — view study personnel | ✅ | — | ✅ | — | ✅ | ✅ |
| `export` — export data for submission | — | — | ✅ | — | ✅ | ✅ |
| **Row scope** | own site | own site | all sites | all sites | all sites | all sites |

Two limits apply independently, and they are genuinely different things:

- **Permission** — may this role touch this *kind* of thing at all? The Ethics Committee has
  no `subject:read`, so `/api/subjects` is `403` for them at every site. That is deliberate:
  an independent reviewer's remit is safety, deviations and compliance, not reading through
  who is enrolled.
- **Site scope** — *whose* rows do they get? An investigator has `subject:read`, but only
  for their own hospital. Another site's participant is a `403`, not an empty page, and
  `?site_id=` cannot widen the scope — a filter you can remove by editing the URL is not
  access control.

Every refusal says which permission was missing:
`"Ethics Committee cannot do this. Missing permission: subject:read"`.

---

## The live dashboards

Five screens, one per persona, each showing eight KPIs and three or four panels drawn from
the same seeded data. The role comes from the signed token, not from the URL, so a regulator
cannot ask for the sponsor's screen by editing an address.

Updates arrive over a **WebSocket** — a phone line the browser holds open, so the server can
speak first instead of the page asking "any news?" on a timer. Behind it is **Redis pub/sub**,
which is a radio station: the API broadcasts "an enrolment happened at site 2" on one
channel, and every open dashboard hears it and recomputes its own numbers. If Redis is
missing the backend falls back to an in-process fan-out automatically and says so in
`/api/health` — the demo never dies on a missing dependency.

### Showing it live

Two ways to make something happen. In the UI, open **Simulate an event** and press a button.
Or from a terminal:

```bash
docker compose exec backend python scripts/simulate.py
```

```bash
docker compose exec backend python scripts/simulate.py adverse-event --serious
```

```bash
docker compose exec backend python scripts/simulate.py --count 5 --every 4
```

```bash
docker compose exec backend python scripts/simulate.py --as sponsor
```

The last one is refused, on purpose: a Sponsor has no `subject:write`, because a monitor who
could edit the data would undermine the data. That makes the better demo anyway — leave the
Sponsor's screen open, enrol someone as the Coordinator in another window, and watch the
Sponsor's total move with nobody touching it.

These write **real rows**: a participant with a full visit schedule, an adverse event with no
MedDRA code yet, or a visit completed outside its window. Each one also writes an audit entry
naming who did it. Enrolment goes from 186 to 187 because there is a 187th person in the
table. Put the baseline back with:

```bash
docker compose exec backend python scripts/seed.py --reset
```

### Verifying it end to end

Only the site roles can write, so throughout this the **Coordinator** fires the events and
everyone else watches. Use two browser windows — one of them private, so the two tokens do not
overwrite each other.

1. Window A: sign in as the **Sponsor**. Top right shows a green **Live** dot and, next to it,
   which fan-out is in use (`redis` or `in-process`).
2. Window B: sign in as the **Coordinator** (site 01). Their screen has an active
   **Simulate an event** panel.
3. In window B, press *Enrol a participant*.
4. Window A moves on its own: **Enrolled** and **Of target** change, the tiles that changed are
   highlighted for a moment, and a banner names the new participant *and who enrolled them*.
   Nobody touched window A.
5. Now make window A the **Ethics Committee** and press *Enrol a participant* again in B. Two
   things to point at: their tiles do **not** move — an enrolment is not their business, they
   review safety and deviations — and the notice reads only *"Trial data changed; your figures
   have been recalculated."* They have no `subject:read`, so they are not told **which**
   participant. Naming a record to somebody who cannot open it would undo the access rules.
   Their own Simulate buttons are greyed out, with the reason on hover.
6. Make window A **NIA Jaipur's investigator** (`rajeev.ranjan.sinha@demo.aiia-ctms.in`) and
   press *Enrol* in B once more. Nothing happens at all: the event was at site 01 and they are
   site 02, so they are not even told. Click **refresh** beside the live dot to confirm it is
   not a stale screen.
7. Put the **Ethics Committee** back in window A and press the red *Report a SERIOUS event* in
   B. Now their numbers do move — **Serious events** and **All adverse events** — and this time
   the notice names the event in full, because an ethics reviewer *does* have `ae:read`. Same
   mechanism as step 5, opposite outcome; the difference is one permission.

The Coordinator cannot aim at another site either. Their `site_id` is taken from their token,
so `{"site_id": 3}` in the request body is overwritten with their own — a site scope you could
escape by editing a payload would not be a scope.

---

## Other commands

Wipe and reload the data (useful after changing the generator):

```bash
docker compose exec backend python scripts/seed.py --reset
```

Give an already-seeded database the demo passwords, without touching the trial data:

```bash
docker compose exec backend python scripts/seed.py --passwords
```

Freeze the demo to a fixed date, so every number is identical on every laptop:

```bash
docker compose exec backend python scripts/seed.py --reset --date 2026-08-25 --seed 20260101
```

Run the tests (321 of them, no network needed):

```bash
docker compose exec backend pytest
```

Apply migrations by hand — the entrypoint already does this on every boot, so you only
need it after writing a new migration:

```bash
docker compose exec backend alembic upgrade head
```

Check the models and the migrations still agree. It should print
`No new upgrade operations detected.`:

```bash
docker compose exec backend alembic check
```

Tear everything down, database included, for a clean slate:

```bash
docker compose down -v
```

---

## The data

One trial, generated in pure Python by `backend/app/synthetic.py` and inserted by
`scripts/seed.py`:

> **ASHWA-GAD** — a multicentre, randomised, double-blind, placebo-controlled trial of
> *Ashwagandha* (Withania somnifera) root churna in adults with Generalised Anxiety
> Disorder (Ayurvedic diagnosis: *Chittodvega*), across AIIA Delhi, NIA Jaipur, IPGAE
> Kolkata and GAU Jamnagar.

It is built to be realistic rather than tidy, because the later phases have to cope with
real-world mess:

- Adverse-event narratives are written the way a busy coordinator types them — clinical
  shorthand, inconsistent capitalisation, run-on sentences. Phase 4's NLP reads these.
- No adverse event has a MedDRA code yet. That empty column *is* Phase 4's work queue.
- Recruitment is uneven across sites, and one site has a deliberate cluster of
  gastrointestinal events for Phase 4's signal detection to find.
- 84 visits are flagged as protocol deviations, and a couple of serious events were
  reported to the ethics committee late — Phase 5's compliance checks need real problems.
- Audit entries are timestamped when the thing they describe actually happened, not at
  load time.
- Participants are de-identified by design: no name, address, phone or date of birth is
  stored anywhere, only a year of birth and an age.

Explore it at http://localhost:8000/docs, or start here:

| Endpoint | What it gives you |
| --- | --- |
| `/api/stats` | Every headline number in one call — enrolment, per-site recruitment, visits, safety, audit |
| `/api/stats/enrollment-timeline` | The cumulative recruitment curve, by month |
| `/api/trials`, `/api/sites` | The study and the four sites running it |
| `/api/subjects?status=enrolled` | Participants, filterable by site, status, arm and prakriti |
| `/api/subjects/{id}/visits` | One participant's whole visit schedule |
| `/api/adverse-events?serious_only=true` | The safety picture, filterable by severity and causality |
| `/api/audit-log` | Who did what, when — newest first |

Every list endpoint returns the same envelope — `total`, `limit`, `offset`, `items` — so a
table can show "showing 50 of 186".

---

## Jargon, in one line each

| Term | Plain meaning |
| --- | --- |
| **CTMS** | Project-management software for a clinical trial — like Jira, but for tracking patients, visits and safety instead of tickets. |
| **GCP** (Good Clinical Practice) | The international rulebook for running trials ethically and verifiably. Here it means: audit everything, change nothing silently. |
| **CDISC SDTM** | The standard spreadsheet layout regulators expect trial data in — like a tax form: everyone submits the same boxes in the same order. |
| **FHIR** | The standard format hospital systems use to exchange records — the USB-C of health data. |
| **CTRI** | India's public trial registry. Registering a trial there is like filing a company with the registrar: it must exist on the record before you start. |
| **NDCT Rules 2019** | India's regulations for new drugs and clinical trials — the legal gates a trial must pass through in order. |
| **Pharmacovigilance** | Drug-safety monitoring: watching for harmful side effects and raising the alarm early. |
| **Adverse event (AE)** | Anything bad that happens to a participant during a trial, whether or not the treatment caused it. |
| **Severity vs seriousness** | Two different things. *Severity* is how intense it felt (mild / moderate / severe). *Seriousness* is a regulatory category — death, life-threatening, hospitalisation, disability, birth defect — and it starts a reporting clock. A severe headache is not serious; a mild reaction that puts someone in hospital overnight is. |
| **MedDRA** | The standard dictionary of medical terms. It turns "loose motions", "the runs" and "diarrhoea" into one agreed code, so events can be counted. |
| **Protocol deviation** | Anything that departed from the written plan — a visit two weeks late, a missed blood test. The rule is to record it, never to hide it. |
| **Prakriti / dosha** | An Ayurvedic constitutional type (vata / pitta / kapha) — roughly, a baseline body-type classification recorded per participant. |
| **Audit trail** | An append-only log of who changed what, when and why. Like a bank statement: a mistake is fixed by adding a correcting entry, never by erasing the original. Required by **21 CFR Part 11**, the regulation for electronic records. |
| **Migration** (Alembic) | A numbered script that changes the database's shape — version control for table structure. Running them in order builds the schema from empty, the same way on every machine. |
| **RBAC** (role-based access control) | Permissions attached to job titles, not people — a hotel keycard opens your floor, the manager's opens all of them. |
| **JWT** (JSON Web Token) | The access token you get at login: a note saying "this is Kavita, a coordinator at site 1", stamped with a signature only the server can forge. It is *signed, not sealed* — anyone holding it can read it, so it carries no secrets, and the server trusts it because tampering breaks the signature. |
| **Hashing** (bcrypt) | A one-way scramble. The database stores the scramble of your password, never the password, so a stolen database still cannot log anyone in. Deliberately slow, to make guessing expensive. |
| **WebSocket** | A phone line held open between browser and server, so the server can push updates instantly instead of the page asking "any news?" on a timer. |
| **Pub/sub** (publish–subscribe) | A radio station. The API *publishes* "an enrolment happened at site 2" once; every dashboard that *subscribed* hears it. The publisher never needs to know who is listening, so one event reaches five screens without addressing any of them. |

---

## Architecture

```
Browser ──▶ Vite dev server (:5173) ──/api──▶ FastAPI (:8000) ──▶ PostgreSQL (:5432)
   ▲                                              │
   └────────────── /ws ───────────────────────────┤
        (live KPI push)                           └──▶ Redis (:6379)
                                                       (pub/sub fan-out)
```

The Vite dev server proxies `/api` and `/ws` to the backend, so the browser only ever
talks to one origin — no CORS configuration needed for the demo.

A write and a broadcast are two separate steps. A `POST` inserts the row, writes the audit
entry, and *then* publishes a one-line event. Each open socket recomputes that viewer's own
dashboard from the database and pushes the result — so what arrives at the browser has already
been through the same permission and site-scope rules as `GET /api/dashboard`. The event says
*that* something changed; it never carries someone else's numbers.

If Redis is unreachable, `EventBus` falls back to an in-process fan-out and the app keeps
working — one backend container behaves identically either way. Redis is what makes it still
work with several containers behind a load balancer.

## Layout

```
.
├── docker-compose.yml     # the whole system, one command
├── backend/               # FastAPI
│   ├── alembic/
│   │   └── versions/      # numbered migration scripts - the real schema
│   ├── app/
│   │   ├── main.py        # app setup, health, info
│   │   ├── config.py      # settings from environment variables
│   │   ├── db.py          # engine, sessions, health check
│   │   ├── enums.py       # the controlled vocabularies (statuses, severities...)
│   │   ├── security.py    # password hashing, token issue/verify, logout deny-list
│   │   ├── rbac.py        # who may do what, and whose rows they see
│   │   ├── audit.py       # append-only "who did what, when" writer
│   │   ├── kpi.py         # every dashboard number, computed in one place
│   │   ├── events.py      # the Redis pub/sub bus, with an in-process fallback
│   │   ├── models/        # the seven tables, as SQLModel classes
│   │   ├── routers/       # the API, one file per area
│   │   │   ├── auth.py    #   login, logout, me, demo-users
│   │   │   ├── dashboard.py  # the five role screens
│   │   │   ├── live.py    #   the /ws/dashboard WebSocket
│   │   │   ├── simulate.py   # write a row and broadcast it
│   │   │   └── ...        #   trials, subjects, safety, compliance, stats
│   │   └── synthetic.py   # the data generator - pure Python, no database
│   ├── entrypoint.sh      # wait for Postgres, migrate, then start uvicorn
│   └── tests/             # 321 tests: auth, rbac, api, dashboards, live, migrations
├── frontend/              # React + Vite + Tailwind
│   └── src/
│       ├── auth.jsx       # who is signed in; the token lives here
│       ├── api.js         # fetch wrapper that attaches the token
│       ├── Login.jsx      # the six one-click demo personas
│       ├── Shell.jsx      # header, live badge, navigation
│       ├── useLiveDashboard.js  # opens the WebSocket, reconnects, flags changes
│       ├── blocks.jsx     # the four panel renderers (table/breakdown/series/checklist)
│       ├── dashboards/    # one file per persona
│       ├── RbacMatrix.jsx # the access-rules table, straight from the API
│       └── Simulate.jsx   # the "make something happen" buttons
└── scripts/
    ├── seed.py            # inserts the generated data, sets the demo passwords
    └── simulate.py        # fire events from a terminal instead of the UI
```

### Where the schema lives

Two files describe every table, and they must never disagree:

- `backend/app/models/` — what the Python code believes the tables look like.
- `backend/alembic/versions/` — what actually gets built in a real database.

`backend/tests/test_migrations.py` runs the migrations into a throwaway SQLite file and
compares the result against the models column by column, so a model change with no
migration fails the tests instead of failing in production. `alembic check` is the same
check from the other direction.

The app itself never creates tables. `entrypoint.sh` runs `alembic upgrade head` before
uvicorn starts, so the schema has exactly one owner.

## Tech stack

- **Backend** — FastAPI, SQLModel/SQLAlchemy, PostgreSQL, Redis, Celery/RQ for async AI jobs
- **Interop** — `fhir.resources` for FHIR; a custom CDISC SDTM mapping layer
- **AI/ML** — scikit-learn (dropout & recruitment prediction); spaCy + medspaCy for
  adverse-event NLP and MedDRA coding
- **Frontend** — React, Vite, Tailwind, Recharts
- **Infra** — Docker Compose

## Build phases

- [x] **Phase 0** — Scaffold: Docker Compose + Postgres + FastAPI + React, wired and running
- [x] **Phase 1** — Data model (Trial, Site, Subject, Visit, AdverseEvent, User/Role,
      AuditLog) + Alembic migrations + synthetic seed + read-only API
- [x] **Phase 2** — Auth + RBAC + 5 role dashboards with live KPIs over WebSocket
- [ ] **Phase 3** — Feature 1: AI Data-Harmonization Engine
- [ ] **Phase 4** — Feature 2: Pharmacovigilance NLP + signal alerts
- [ ] **Phase 5** — Feature 3: Compliance module (CTRI export, NDCT gates, audit trail,
      e-signatures, compliance score)
- [ ] **Phase 6** — Feature 5: Ayurveda data model + Feature 4 polish + demo seed

## Troubleshooting

**Database light is red.** Postgres takes a few seconds on first boot; the page re-checks
every 5 seconds and turns green on its own. If it stays red:
`docker compose logs backend`.

**"Synthetic trial data" light is red, or every number is zero.** The database is empty —
the schema exists but nothing has been loaded into it. Run
`docker compose exec backend python scripts/seed.py`.

**Seed script says "already seeded; nothing to do".** That is deliberate: running it twice
must not double the data. Use `--reset` to wipe and reload.

**Login says "incorrect email or password".** The users exist but have no password — this
happens on a database seeded before passwords were added. Run
`docker compose exec backend python scripts/seed.py --passwords`. It sets them without
touching the trial data.

**The login screen shows no demo buttons.** They come from `/api/auth/demo-users`, which only
answers while `APP_ENV=development`. Type the email and password from the table above instead.

**A page suddenly returns 401 and bounces me to the login screen.** The token expired. It
lasts 12 hours by default; sign in again, or set `ACCESS_TOKEN_TTL_MINUTES` in `.env` for a
long demo day. Logging out in one tab also invalidates that tab's token only, so a second tab
signed in as the same person keeps working.

**403 with "Missing permission: ...".** Working as designed — see
[Who can do what](#who-can-do-what). A site role asking for another site's record gets a 403
too, and that is the same rule.

**The badge next to the live dot says `in-process` instead of `redis`.** The backend could not
reach Redis and fell back, which is why the demo still works. With one backend container the
behaviour is identical — Redis is what makes it work across several. To get it back:
`docker compose up -d redis`, then `docker compose restart backend`.

**The dot says "Not live" (red) and numbers only change when I click refresh.** The WebSocket
did not connect. Running the frontend outside Docker, check `VITE_PROXY_TARGET`; a corporate
proxy or VPN that strips `Upgrade` headers will also block it. The dashboard still works —
the **refresh** link beside the dot fetches the same numbers over ordinary HTTP.

**Simulating changed the numbers and I want the demo figures back.**
`docker compose exec backend python scripts/seed.py --reset`. The simulated rows were real
rows, which is why they persist.

**`scripts/simulate.py` says "nothing to do (409)".** The database is empty, so there is
nobody to enrol or report against. Seed it first.

**"column does not exist" or the schema light is red.** The container is running against a
database at the wrong migration. Run `docker compose exec backend alembic upgrade head`,
or `docker compose down -v && docker compose up --build` to rebuild from empty.

**Port already in use.** Something else holds 5432, 8000, 5173 or 6379. Either stop it, or
change the left-hand number in the relevant `ports:` entry in `docker-compose.yml`.

**Frontend won't start after adding a dependency.** The container's `node_modules` lives in
a Docker volume, so a new entry in `package.json` needs a rebuild:
`docker compose up --build frontend`.
