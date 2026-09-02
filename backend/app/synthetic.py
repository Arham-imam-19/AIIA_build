"""Generates a realistic SYNTHETIC Ayurveda clinical trial.

Everything here is invented. No real participant, record or contact detail
appears anywhere in this module, and none ever should.

Design note - why this file has no database code
------------------------------------------------
This module is pure Python: it takes a reference date and a random seed, and
returns nested dictionaries. It never imports SQLModel, opens a connection or
touches Postgres. `scripts/seed.py` is the thin layer that turns these dicts
into rows.

That split exists so the interesting part - the shape of the data, the enrolment
funnel, the date arithmetic, the referential integrity - can be unit-tested in
milliseconds without a database running.

Rows refer to each other by natural key (`_site_code`, `_subject_code`,
`_reported_by_email`) rather than by integer id, because ids do not exist until
the rows are inserted. Keys starting with an underscore are references for the
seeder to resolve; every other key is a real column.
"""

from __future__ import annotations

import hashlib
import random
from datetime import date, datetime, timedelta

from app.enums import (
    AECausality,
    AEOutcome,
    AESeverity,
    AuditAction,
    ConsentStatus,
    EthicsApprovalStatus,
    Prakriti,
    Sex,
    SiteStatus,
    StudyArm,
    SubjectStatus,
    TrialPhase,
    TrialStatus,
    UserRole,
    VisitStatus,
)

# Fixed so that two runs with the same reference date produce identical data.
DEFAULT_SEED = 20260101

# All demo accounts live on an obviously fake domain, so no synthetic user can
# ever be mistaken for a real mailbox.
EMAIL_DOMAIN = "demo.aiia-ctms.in"

# The protocol's visit timetable: (name, protocol day relative to baseline).
# Screening happens up to two weeks before baseline, hence day -14.
VISIT_SCHEDULE: list[tuple[str, int]] = [
    ("Screening", -14),
    ("Baseline (Day 0)", 0),
    ("Week 2 Follow-up", 14),
    ("Week 4 Follow-up", 28),
    ("Week 8 Follow-up", 56),
    ("End of Study (Day 84)", 84),
]

TREATMENT_DURATION_DAYS = 84

# ---------------------------------------------------------------------------
# Sites. The institutions are real, publicly known Ayurveda centres, which makes
# the demo recognisable to an Ayush audience. The investigators named at them are
# invented, as is every participant and every number.
# ---------------------------------------------------------------------------
SITE_SPECS: list[dict] = [
    {
        "site_code": "01",
        "name": "All India Institute of Ayurveda (AIIA), New Delhi",
        "city": "New Delhi",
        "state": "Delhi",
        "pi_name": "Dr. Meenakshi Sharma",
        "target_enrollment": 80,
        "status": SiteStatus.RECRUITING.value,
        "activation_offset": -238,  # days before the reference date
        # counts: still being screened / failed screening / enrolled
        "n_screening": 4,
        "n_screen_failed": 10,
        "n_enrolled": 68,
    },
    {
        "site_code": "02",
        "name": "National Institute of Ayurveda (NIA), Jaipur",
        "city": "Jaipur",
        "state": "Rajasthan",
        "pi_name": "Dr. Rajeev Ranjan Sinha",
        "target_enrollment": 70,
        "status": SiteStatus.RECRUITING.value,
        "activation_offset": -231,
        "n_screening": 3,
        "n_screen_failed": 8,
        "n_enrolled": 55,
    },
    {
        "site_code": "03",
        "name": "Institute of Post Graduate Ayurvedic Education & Research, Kolkata",
        "city": "Kolkata",
        "state": "West Bengal",
        "pi_name": "Dr. Ananya Bhattacharya",
        "target_enrollment": 50,
        "status": SiteStatus.RECRUITING.value,
        "activation_offset": -210,
        "n_screening": 2,
        "n_screen_failed": 6,
        "n_enrolled": 40,
    },
    {
        # Activated late, so it lags the others. This is what makes the "site
        # performance" KPI in the dashboards show something worth looking at.
        "site_code": "04",
        "name": "Gujarat Ayurved University, Jamnagar",
        "city": "Jamnagar",
        "state": "Gujarat",
        "pi_name": "Dr. Hiren Patel",
        "target_enrollment": 40,
        "status": SiteStatus.ACTIVATED.value,
        "activation_offset": -132,
        "n_screening": 2,
        "n_screen_failed": 4,
        "n_enrolled": 23,
    },
]

# How the enrolled participants at each site are distributed across outcomes.
# Roughly half have finished the 84-day course, a third are still in follow-up,
# and the rest dropped out - a plausible profile for a trial two-thirds through.
ENROLLED_STATUS_WEIGHTS: list[tuple[str, float]] = [
    (SubjectStatus.COMPLETED.value, 0.50),
    (SubjectStatus.ACTIVE.value, 0.33),
    (SubjectStatus.WITHDRAWN.value, 0.11),
    (SubjectStatus.LOST_TO_FOLLOW_UP.value, 0.06),
]

# Anxiety disorders are more often diagnosed in women, so the sample is skewed.
SEX_WEIGHTS: list[tuple[str, float]] = [
    (Sex.FEMALE.value, 0.56),
    (Sex.MALE.value, 0.43),
    (Sex.OTHER.value, 0.01),
]

# Classical Ayurvedic reasoning links anxiety (chittodvega) largely to vata
# imbalance, so vata-dominant constitutions are over-represented here. That
# gives the Phase 6 Ayurveda dashboards a real pattern to display.
PRAKRITI_WEIGHTS: list[tuple[str, float]] = [
    (Prakriti.VATA.value, 0.22),
    (Prakriti.VATA_PITTA.value, 0.26),
    (Prakriti.VATA_KAPHA.value, 0.14),
    (Prakriti.PITTA.value, 0.13),
    (Prakriti.PITTA_KAPHA.value, 0.12),
    (Prakriti.KAPHA.value, 0.09),
    (Prakriti.TRIDOSHA.value, 0.04),
]

SCREEN_FAILURE_REASONS = [
    "HAM-A score below inclusion threshold at screening",
    "Concurrent use of prohibited anxiolytic medication",
    "Abnormal liver function tests at screening",
    "Did not meet minimum age criterion",
    "Uncontrolled hypertension on screening examination",
    "Declined to provide written informed consent",
    "Pregnancy confirmed at screening",
    "Participation in another interventional trial within 90 days",
]

WITHDRAWAL_REASONS = [
    "Withdrew consent, no reason given",
    "Relocated out of the study area",
    "Unable to comply with the visit schedule due to work commitments",
    "Withdrawn by investigator following an adverse event",
    "Started a prohibited concomitant medication",
    "Personal reasons, family circumstances",
    "Difficulty tolerating the taste of the study churna",
]

DEVIATION_TEMPLATES = [
    "Visit conducted {days} days outside the protocol-defined window.",
    "Visit delayed by {days} days; participant unavailable, rescheduled at the "
    "earliest opportunity.",
    "Assessment performed {days} days late owing to a public holiday at the site.",
]

# ---------------------------------------------------------------------------
# Adverse-event catalogue.
#
# The narratives are written the way a busy coordinator actually types them:
# clinical shorthand (c/o = complains of, IP = investigational product,
# x3 days = for three days, SOS = as needed), inconsistent capitalisation,
# occasional run-on sentences. Phase 4's NLP has to cope with this, so cleaning
# it up here would only make that feature look better than it is.
# ---------------------------------------------------------------------------
AE_CATALOGUE: list[dict] = [
    {
        "term_verbatim": "Gastric irritation",
        "description": (
            "Pt c/o mild burning sensation in epigastric region, started 3 days "
            "after first dose of IP. no vomiting. advised to take churna after "
            "food with warm milk. settled in 2 days, IP continued."
        ),
        "severity": AESeverity.MILD.value,
        "causality": AECausality.PROBABLE.value,
        "outcome": AEOutcome.RECOVERED.value,
        "action_taken": "Dose administration timing changed, IP continued",
        "weight": 10,
    },
    {
        "term_verbatim": "Loose stools",
        "description": (
            "Subject reported loose motions, 3 episodes/day x2 days. no blood, no "
            "fever, no sign of dehydration. ORS advised. IP continued without "
            "interruption. resolved on its own."
        ),
        "severity": AESeverity.MILD.value,
        "causality": AECausality.POSSIBLE.value,
        "outcome": AEOutcome.RECOVERED.value,
        "action_taken": "None, IP continued",
        "weight": 12,
    },
    {
        "term_verbatim": "Daytime drowsiness",
        "description": (
            "c/o feeling sleepy during the daytime after the evening dose. mild, "
            "did not affect work. dose timing shifted to early evening and pt "
            "reports improvement."
        ),
        "severity": AESeverity.MILD.value,
        "causality": AECausality.PROBABLE.value,
        "outcome": AEOutcome.RECOVERED.value,
        "action_taken": "Dose administration timing changed",
        "weight": 9,
    },
    {
        "term_verbatim": "Headache",
        "description": (
            "Bilateral frontal headache, dull in nature, on and off x4 days. "
            "VAS 4/10. took tab paracetamol 500mg SOS twice. no photophobia, no "
            "vomiting. resolved completely."
        ),
        "severity": AESeverity.MILD.value,
        "causality": AECausality.UNLIKELY.value,
        "outcome": AEOutcome.RECOVERED.value,
        "action_taken": "Concomitant medication given",
        "weight": 8,
    },
    {
        "term_verbatim": "Nausea",
        "description": (
            "Nausea reported approx 30 min after the morning dose of study drug. "
            "no vomiting. mild and tolerable, pt willing to continue. IP continued."
        ),
        "severity": AESeverity.MILD.value,
        "causality": AECausality.POSSIBLE.value,
        "outcome": AEOutcome.RECOVERED.value,
        "action_taken": "None, IP continued",
        "weight": 7,
    },
    {
        "term_verbatim": "Increased appetite with weight gain",
        "description": (
            "Subject noted increased appetite since approx week 2. wt gain 1.6 kg "
            "over 4 weeks. not distressing to pt, no dietary change advised. "
            "ongoing at last visit."
        ),
        "severity": AESeverity.MILD.value,
        "causality": AECausality.POSSIBLE.value,
        "outcome": AEOutcome.ONGOING.value,
        "action_taken": "None",
        "weight": 5,
    },
    {
        "term_verbatim": "Skin rash",
        "description": (
            "itchy erythematous rash over both forearms noticed on day 19. "
            "no mucosal involvement, no breathlessness. tab cetirizine 10mg HS "
            "given. IP temporarily withheld x3 days, rash subsided, IP restarted "
            "with no recurrence."
        ),
        "severity": AESeverity.MODERATE.value,
        "causality": AECausality.POSSIBLE.value,
        "outcome": AEOutcome.RECOVERED.value,
        "action_taken": "IP temporarily interrupted",
        "weight": 5,
    },
    {
        "term_verbatim": "Giddiness on standing",
        "description": (
            "Pt c/o giddiness on standing up, esp in the mornings. BP 100/64 "
            "supine, 92/60 standing. advised adequate oral fluids and to rise "
            "slowly. improved over the next week."
        ),
        "severity": AESeverity.MILD.value,
        "causality": AECausality.POSSIBLE.value,
        "outcome": AEOutcome.RECOVERED.value,
        "action_taken": "Non-drug advice given",
        "weight": 6,
    },
    {
        "term_verbatim": "Hyperacidity",
        "description": (
            "known h/o acidity. c/o increased sour eructations and retrosternal "
            "burning x5 days. tab pantoprazole 40mg OD given x7 days. improved. "
            "IP continued throughout."
        ),
        "severity": AESeverity.MILD.value,
        "causality": AECausality.UNLIKELY.value,
        "outcome": AEOutcome.RECOVERED.value,
        "action_taken": "Concomitant medication given",
        "weight": 6,
    },
    {
        "term_verbatim": "Insomnia",
        "description": (
            "difficulty falling asleep reported at wk 4 visit, approx 1-1.5 hrs "
            "sleep latency. no daytime sedation. sleep hygiene counselling given. "
            "partially improved, still ongoing."
        ),
        "severity": AESeverity.MILD.value,
        "causality": AECausality.UNLIKELY.value,
        "outcome": AEOutcome.RECOVERING.value,
        "action_taken": "Non-drug advice given",
        "weight": 5,
    },
    {
        "term_verbatim": "Constipation",
        "description": (
            "Pt reports hard stools, passing motion every 2nd day since wk 3. "
            "adequate hydration advised, triphala churna at bedtime as per "
            "investigator advice. improved."
        ),
        "severity": AESeverity.MILD.value,
        "causality": AECausality.POSSIBLE.value,
        "outcome": AEOutcome.RECOVERED.value,
        "action_taken": "Non-drug advice given",
        "weight": 5,
    },
    {
        "term_verbatim": "Palpitations",
        "description": (
            "episodic palpitations x2 episodes, each lasting few minutes, self "
            "limiting. ECG done - within normal limits. thyroid profile normal. "
            "no further episodes reported."
        ),
        "severity": AESeverity.MODERATE.value,
        "causality": AECausality.NOT_ASSESSABLE.value,
        "outcome": AEOutcome.RECOVERED.value,
        "action_taken": "Investigations performed",
        "weight": 4,
    },
    {
        "term_verbatim": "Fatigue",
        "description": (
            "generalised tiredness reported over the last 10 days. Hb 11.2 g/dL. "
            "no other cause identified. mild, pt continuing IP and daily "
            "activities."
        ),
        "severity": AESeverity.MILD.value,
        "causality": AECausality.UNLIKELY.value,
        "outcome": AEOutcome.ONGOING.value,
        "action_taken": "None",
        "weight": 4,
    },
    {
        "term_verbatim": "Dry mouth",
        "description": (
            "c/o dryness of mouth, mild, noticed mostly in the afternoons. no "
            "difficulty swallowing. sips of water advised. continues at present."
        ),
        "severity": AESeverity.MILD.value,
        "causality": AECausality.POSSIBLE.value,
        "outcome": AEOutcome.ONGOING.value,
        "action_taken": "None",
        "weight": 3,
    },
]

# Serious adverse events (SAEs) get their own list because they are rare, must
# each be distinct, and carry hard reporting deadlines. "Serious" is a
# regulatory category - death, life-threatening, hospitalisation, lasting
# disability or a birth defect - not a measure of how unpleasant it was.
SAE_CATALOGUE: list[dict] = [
    {
        "term_verbatim": "Acute gastroenteritis requiring hospitalisation",
        "description": (
            "Admitted to hospital on study day 41 c/o repeated vomiting and loose "
            "motions since previous night, with clinical dehydration. IV fluids "
            "given x2 days, stool routine showed no ova/cyst. discharged stable on "
            "day 43. IP withheld during admission and restarted after discharge. "
            "investigator opinion - unlikely related to IP, food source at a family "
            "function suspected as several family members affected."
        ),
        "severity": AESeverity.SEVERE.value,
        "causality": AECausality.UNLIKELY.value,
        "outcome": AEOutcome.RECOVERED.value,
        "seriousness_criteria": "Required inpatient hospitalisation",
        "action_taken": "IP temporarily interrupted",
    },
    {
        "term_verbatim": "Road traffic accident with fracture of left tibia",
        "description": (
            "Subject met with a two-wheeler accident on day 58, sustained closed "
            "fracture left tibia. admitted, ORIF done under spinal anaesthesia. "
            "hospital stay 6 days. residual limp at last follow up, on "
            "physiotherapy. clearly unrelated to study drug, reported as SAE per "
            "protocol requirement."
        ),
        "severity": AESeverity.SEVERE.value,
        "causality": AECausality.UNRELATED.value,
        "outcome": AEOutcome.RECOVERED_WITH_SEQUELAE.value,
        "seriousness_criteria": "Required inpatient hospitalisation; persistent disability",
        "action_taken": "IP permanently discontinued",
    },
    {
        "term_verbatim": "Generalised urticaria with facial angioedema",
        "description": (
            "On day 12 pt developed widespread urticarial wheals with swelling of "
            "lips and periorbital region approx 2 hrs after the morning dose. "
            "no stridor but c/o throat tightness. taken to emergency, inj "
            "hydrocortisone and inj pheniramine given, observed overnight. "
            "settled by next morning. IP permanently discontinued. investigator "
            "assessed as possibly related - hypersensitivity to a component of the "
            "study churna cannot be excluded."
        ),
        "severity": AESeverity.SEVERE.value,
        "causality": AECausality.POSSIBLE.value,
        "outcome": AEOutcome.RECOVERED.value,
        "seriousness_criteria": "Life-threatening; required emergency treatment",
        "action_taken": "IP permanently discontinued",
    },
    {
        "term_verbatim": "Acute worsening of anxiety requiring psychiatric admission",
        "description": (
            "Marked worsening of anxiety symptoms in wk 6, HAM-A rose from 14 at "
            "baseline to 27. pt expressed hopelessness, referred urgently to "
            "psychiatry and admitted for 5 days for stabilisation. started on "
            "standard care as per psychiatrist. IP discontinued. unblinding "
            "requested by investigator - subject was on placebo arm. reported to "
            "IEC within 24 hrs."
        ),
        "severity": AESeverity.SEVERE.value,
        "causality": AECausality.UNRELATED.value,
        "outcome": AEOutcome.RECOVERING.value,
        "seriousness_criteria": "Required inpatient hospitalisation",
        "action_taken": "IP permanently discontinued; emergency unblinding performed",
    },
]

# For Phase 4's signal detection to have anything to find, one term has to occur
# more often at one site than chance would explain. Site 02 gets a cluster of
# gastrointestinal complaints - exactly the sort of pattern a safety monitor is
# meant to notice and investigate.
SIGNAL_CLUSTER_SITE = "02"
SIGNAL_CLUSTER_TERM = "Loose stools"
SIGNAL_CLUSTER_EXTRA_EVENTS = 7


def _weighted_pick(rng: random.Random, weighted: list[tuple[str, float]]) -> str:
    """Choose one value from (value, weight) pairs."""
    options = [value for value, _ in weighted]
    weights = [weight for _, weight in weighted]
    return rng.choices(options, weights=weights, k=1)[0]


def _allocate(total: int, weights: list[tuple[str, float]]) -> dict[str, int]:
    """Split `total` into whole numbers across weighted buckets.

    Uses the largest-remainder method so the parts always add back up to
    `total` exactly - important because these counts drive the enrolment funnel
    shown on the dashboards, and a funnel whose numbers do not reconcile is
    worse than no funnel.
    """
    raw = {name: total * weight for name, weight in weights}
    floors = {name: int(value) for name, value in raw.items()}
    shortfall = total - sum(floors.values())

    # Hand the leftover units to whichever buckets were rounded down hardest.
    remainders = sorted(
        raw.items(), key=lambda item: item[1] - int(item[1]), reverse=True
    )
    for index in range(shortfall):
        floors[remainders[index % len(remainders)][0]] += 1

    return floors


def _build_trial(reference_date: date) -> dict:
    start = reference_date - timedelta(days=250)
    return {
        "protocol_number": "AIIA-ASH-2026-01",
        "title": (
            "A Multicentre, Randomised, Double-Blind, Placebo-Controlled Trial to "
            "Evaluate the Efficacy and Safety of Ashwagandha (Withania somnifera) "
            "Root Churna in Adults with Generalised Anxiety Disorder"
        ),
        "short_title": "ASHWA-GAD Trial",
        "ctri_number": "CTRI/2026/01/078412",
        "ctri_registration_date": start - timedelta(days=21),
        "phase": TrialPhase.PHASE_3.value,
        "status": TrialStatus.RECRUITING.value,
        "indication": "Generalised Anxiety Disorder (HAM-A score 14-25 at screening)",
        "indication_ayurveda": "Chittodvega",
        "intervention": (
            "Ashwagandha (Withania somnifera) root churna 3 g twice daily with "
            "warm milk, after food, for 84 days"
        ),
        "comparator": "Matched placebo churna 3 g twice daily for 84 days",
        "design": (
            "Multicentre, randomised, double-blind, placebo-controlled, "
            "parallel-group, 1:1 allocation"
        ),
        "is_blinded": True,
        "primary_objective": (
            "To evaluate the efficacy of Ashwagandha root churna compared with "
            "placebo in reducing anxiety severity in adults with Generalised "
            "Anxiety Disorder over 84 days of treatment."
        ),
        "secondary_objective": (
            "To assess safety and tolerability; to evaluate change in sleep "
            "quality and quality of life; to explore whether response differs by "
            "baseline prakriti."
        ),
        "primary_endpoint": (
            "Change in Hamilton Anxiety Rating Scale (HAM-A) total score from "
            "baseline to Day 84"
        ),
        "sponsor_name": "All India Institute of Ayurveda (AIIA), Ministry of Ayush",
        "sponsor_type": "Government research institute",
        "target_enrollment": 240,
        "start_date": start,
        "planned_end_date": start + timedelta(days=540),
        "actual_end_date": None,
        "ethics_approval_number": "AIIA/IEC/2025/114",
        "ethics_approval_date": start - timedelta(days=45),
        "ethics_approval_status": EthicsApprovalStatus.APPROVED.value,
        "ethics_approval_valid_until": reference_date + timedelta(days=365),
        "regulatory_approval_number": "CDSCO/AYUSH/CT/2025/0391",
        "regulatory_approval_date": start - timedelta(days=30),
        "activated_at": datetime(start.year, start.month, start.day, 10) - timedelta(days=1),
    }


def _build_sites(reference_date: date) -> list[dict]:
    sites = []
    for spec in SITE_SPECS:
        activation = reference_date + timedelta(days=spec["activation_offset"])
        sites.append(
            {
                "site_code": spec["site_code"],
                "name": spec["name"],
                "city": spec["city"],
                "state": spec["state"],
                "country": "India",
                "pi_name": spec["pi_name"],
                "pi_email": _email(spec["pi_name"]),
                "contact_phone": None,
                "status": spec["status"],
                "target_enrollment": spec["target_enrollment"],
                "activation_date": activation,
                "closed_date": None,
            }
        )
    return sites


def _email(full_name: str) -> str:
    """Build a demo email address from a person's name."""
    cleaned = full_name.replace("Dr. ", "").replace("Prof. ", "").lower()
    slug = ".".join(part for part in cleaned.replace("-", " ").split() if part)
    return f"{slug}@{EMAIL_DOMAIN}"


def _build_users() -> list[dict]:
    """Demo accounts covering all five personas.

    `hashed_password` is intentionally absent: authentication is Phase 2, and
    that is where passwords get set. These rows describe who exists, not who can
    log in yet.
    """
    users: list[dict] = []

    # Institution Administrators (Site Admins who coordinate researchers & manage the hospital's trial operations)
    institution_admins = [
        ("Dr. Ananya Deshmukh", "01"),
        ("Dr. Rajesh Verma", "02"),
        ("Dr. Debashis Sen", "03"),
        ("Dr. Pravin Joshi", "04"),
    ]
    for name, site_code in institution_admins:
        site_name = next(s["name"] for s in SITE_SPECS if s["site_code"] == site_code)
        users.append(
            {
                "email": _email(name),
                "full_name": name,
                "role": UserRole.INSTITUTION_ADMIN.value,
                "organization": site_name,
                "_site_code": site_code,
            }
        )
    # One Principal Investigator per site.
    for spec in SITE_SPECS:
        users.append(
            {
                "email": _email(spec["pi_name"]),
                "full_name": spec["pi_name"],
                "role": UserRole.PRINCIPAL_INVESTIGATOR.value,
                "organization": spec["name"],
                "_site_code": spec["site_code"],
            }
        )

    # Coordinators, who do the day-to-day data entry.
    coordinators = [
        ("Kavita Nair", "01"),
        ("Sunil Meena", "02"),
        ("Rupa Das", "03"),
        ("Jigar Trivedi", "04"),
    ]
    for name, site_code in coordinators:
        site_name = next(s["name"] for s in SITE_SPECS if s["site_code"] == site_code)
        users.append(
            {
                "email": _email(name),
                "full_name": name,
                "role": UserRole.COORDINATOR.value,
                "organization": site_name,
                "_site_code": site_code,
            }
        )

    # Demo Patients (trial participants who can log into the Patient Portal)
    demo_patients = [
        ("Aarav Sharma", "01", "patient.01.014@demo.aiia-ctms.in", "AIIA-ASH-01-014"),
        ("Sunita Patel", "02", "patient.02.005@demo.aiia-ctms.in", "AIIA-ASH-02-005"),
    ]
    for name, site_code, email_addr, subject_code in demo_patients:
        site_name = next(s["name"] for s in SITE_SPECS if s["site_code"] == site_code)
        users.append(
            {
                "email": email_addr,
                "full_name": name,
                "role": UserRole.PATIENT.value,
                "organization": site_name,
                "_site_code": site_code,
                "_subject_code": subject_code,
            }
        )

    # Oversight roles are not tied to any one site, so `_site_code` is None.
    oversight = [
        (
            "Dr. Vikram Desai",
            UserRole.SPONSOR.value,
            "All India Institute of Ayurveda (AIIA), Ministry of Ayush",
        ),
        (
            "Dr. Lalitha Krishnan",
            UserRole.ETHICS_COMMITTEE.value,
            "AIIA Institutional Ethics Committee",
        ),
        (
            "Shri Arvind Kulkarni",
            UserRole.REGULATOR.value,
            "Central Drugs Standard Control Organisation (CDSCO)",
        ),
        (
            "Priya Raghavan",
            UserRole.ADMIN.value,
            "AIIA Clinical Data Management Unit",
        ),
    ]
    for name, role, organization in oversight:
        users.append(
            {
                "email": _email(name),
                "full_name": name,
                "role": role,
                "organization": organization,
                "_site_code": None,
            }
        )

    return users


def _build_subjects(rng: random.Random, reference_date: date) -> list[dict]:
    """One row per screened participant, across all four sites."""
    subjects: list[dict] = []

    for spec in SITE_SPECS:
        site_code = spec["site_code"]
        activation = reference_date + timedelta(days=spec["activation_offset"])
        sequence = 0

        # --- Participants who completed screening and were enrolled.
        status_counts = _allocate(spec["n_enrolled"], ENROLLED_STATUS_WEIGHTS)
        enrolled_statuses: list[str] = []
        for status, count in status_counts.items():
            enrolled_statuses.extend([status] * count)
        rng.shuffle(enrolled_statuses)

        for status in enrolled_statuses:
            sequence += 1
            subjects.append(
                _build_enrolled_subject(
                    rng=rng,
                    reference_date=reference_date,
                    site_code=site_code,
                    activation=activation,
                    sequence=sequence,
                    status=status,
                )
            )

        # --- Participants who failed screening: no enrolment, no arm.
        for _ in range(spec["n_screen_failed"]):
            sequence += 1
            screening_date = _random_date(
                rng, activation, reference_date - timedelta(days=10)
            )
            subjects.append(
                {
                    "_site_code": site_code,
                    "subject_code": _subject_code(site_code, sequence),
                    "status": SubjectStatus.SCREEN_FAILED.value,
                    "screening_date": screening_date,
                    "enrollment_date": None,
                    "randomization_date": None,
                    "arm": StudyArm.NOT_RANDOMIZED.value,
                    "screen_failure_reason": rng.choice(SCREEN_FAILURE_REASONS),
                    "completed_date": None,
                    "withdrawal_date": None,
                    "withdrawal_reason": None,
                    **_demographics(rng, screening_date, enrolled=False),
                }
            )

        # --- Participants currently in screening, i.e. the live top of the funnel.
        for _ in range(spec["n_screening"]):
            sequence += 1
            screening_date = _random_date(
                rng, reference_date - timedelta(days=13), reference_date
            )
            subjects.append(
                {
                    "_site_code": site_code,
                    "subject_code": _subject_code(site_code, sequence),
                    "status": SubjectStatus.SCREENING.value,
                    "screening_date": screening_date,
                    "enrollment_date": None,
                    "randomization_date": None,
                    "arm": StudyArm.NOT_RANDOMIZED.value,
                    "screen_failure_reason": None,
                    "completed_date": None,
                    "withdrawal_date": None,
                    "withdrawal_reason": None,
                    **_demographics(rng, screening_date, enrolled=False),
                }
            )

    return subjects


def _build_enrolled_subject(
    *,
    rng: random.Random,
    reference_date: date,
    site_code: str,
    activation: date,
    sequence: int,
    status: str,
) -> dict:
    """Create one enrolled participant, with dates consistent with `status`.

    The date arithmetic is the fiddly part, and it is what the tests check:

      * COMPLETED means the full 84 days have already elapsed, so enrolment must
        be at least 84 days ago.
      * ACTIVE means they are still inside the 84-day window, so enrolment is
        recent enough that the end-of-study visit has not come round yet.
      * WITHDRAWN / LOST_TO_FOLLOW_UP means they left partway, so the exit date
        sits between enrolment and today.
    """
    earliest_enrollment = activation + timedelta(days=3)

    if status == SubjectStatus.COMPLETED.value:
        # Enrol early enough that the full 84 days plus the visit window has
        # already elapsed, so a "completed" participant can never carry a
        # completion date in the future.
        latest = reference_date - timedelta(days=TREATMENT_DURATION_DAYS + 6)
        enrollment_date = _random_date(rng, earliest_enrollment, latest)
        completed_date = min(
            enrollment_date + timedelta(days=TREATMENT_DURATION_DAYS + rng.randint(0, 4)),
            reference_date,
        )
        withdrawal_date = None
        withdrawal_reason = None
    elif status == SubjectStatus.ACTIVE.value:
        earliest = max(
            earliest_enrollment,
            reference_date - timedelta(days=TREATMENT_DURATION_DAYS - 1),
        )
        enrollment_date = _random_date(
            rng, earliest, reference_date - timedelta(days=5)
        )
        completed_date = None
        withdrawal_date = None
        withdrawal_reason = None
    else:  # WITHDRAWN or LOST_TO_FOLLOW_UP
        latest = reference_date - timedelta(days=14)
        enrollment_date = _random_date(rng, earliest_enrollment, latest)
        # They left somewhere between day 7 and either day 84 or today,
        # whichever comes first.
        max_days_on_study = min(
            TREATMENT_DURATION_DAYS, (reference_date - enrollment_date).days
        )
        days_on_study = rng.randint(7, max(8, max_days_on_study))
        withdrawal_date = enrollment_date + timedelta(days=days_on_study)
        completed_date = None
        withdrawal_reason = rng.choice(WITHDRAWAL_REASONS)

    screening_date = enrollment_date - timedelta(days=rng.randint(3, 14))

    return {
        "_site_code": site_code,
        "subject_code": _subject_code(site_code, sequence),
        "status": status,
        "screening_date": screening_date,
        "enrollment_date": enrollment_date,
        # Randomisation happens the same day as enrolment in this protocol.
        "randomization_date": enrollment_date,
        "arm": rng.choice([StudyArm.TREATMENT.value, StudyArm.PLACEBO.value]),
        "screen_failure_reason": None,
        "completed_date": completed_date,
        "withdrawal_date": withdrawal_date,
        "withdrawal_reason": withdrawal_reason,
        **_demographics(rng, enrollment_date, enrolled=True),
    }


def _subject_code(site_code: str, sequence: int) -> str:
    """e.g. AIIA-ASH-01-014 - trial, site, then a per-site running number."""
    return f"AIIA-ASH-{site_code}-{sequence:03d}"


def _demographics(rng: random.Random, anchor: date, *, enrolled: bool) -> dict:
    age = rng.randint(18, 64)
    sex = _weighted_pick(rng, SEX_WEIGHTS)
    height = round(rng.uniform(148, 182), 1)
    # Loosely tie weight to height so the numbers are not absurd.
    weight = round(rng.uniform(18.5, 29.0) * (height / 100) ** 2, 1)
    return {
        "year_of_birth": anchor.year - age,
        "age_at_enrollment": age if enrolled else None,
        "sex": sex,
        "height_cm": height,
        "weight_kg": weight,
        # Prakriti is assessed at baseline, so only enrolled participants have one.
        "prakriti": _weighted_pick(rng, PRAKRITI_WEIGHTS) if enrolled else None,
    }


def _random_date(rng: random.Random, start: date, end: date) -> date:
    """A date in [start, end]. Falls back to `start` if the range is inverted."""
    span = (end - start).days
    if span <= 0:
        return start
    return start + timedelta(days=rng.randint(0, span))


def _build_visits(
    rng: random.Random,
    reference_date: date,
    subjects: list[dict],
    users: list[dict],
) -> list[dict]:
    """Expand each enrolled participant into their protocol visit schedule."""
    visits: list[dict] = []

    # The coordinator at each site is the person who records that site's visits.
    coordinator_by_site = {
        user["_site_code"]: user["email"]
        for user in users
        if user["role"] == UserRole.COORDINATOR.value
    }

    for subject in subjects:
        enrollment_date = subject["enrollment_date"]
        if enrollment_date is None:
            # Screen failures and in-screening participants get no study visits.
            continue

        exit_date = subject["withdrawal_date"]
        coordinator_email = coordinator_by_site.get(subject["_site_code"])

        for index, (visit_name, visit_day) in enumerate(VISIT_SCHEDULE, start=1):
            scheduled = enrollment_date + timedelta(days=visit_day)
            visit = {
                "_subject_code": subject["subject_code"],
                # Set below for visits that actually took place. A visit nobody
                # performed should not name a person who performed it.
                "_performed_by_email": None,
                "visit_name": visit_name,
                "visit_number": index,
                "visit_day": visit_day,
                "scheduled_date": scheduled,
                "actual_date": None,
                "status": VisitStatus.SCHEDULED.value,
                "is_protocol_deviation": False,
                "deviation_description": None,
                "notes": None,
            }

            if exit_date is not None and scheduled > exit_date:
                # They had already left the trial by the time this visit came up.
                visit["status"] = VisitStatus.CANCELLED.value
                visit["notes"] = "Participant no longer on study at this timepoint."
            elif scheduled > reference_date:
                # Still in the future: nothing to record yet.
                pass
            else:
                # The visit was due. Most happen, a few are missed.
                if rng.random() < 0.045:
                    visit["status"] = VisitStatus.MISSED.value
                    visit["is_protocol_deviation"] = True
                    visit["deviation_description"] = (
                        "Visit not performed within the protocol-defined window; "
                        "participant could not be contacted."
                    )
                else:
                    # The protocol allows a +/- 3 day window. Most visits land
                    # inside it; roughly one in sixteen slips outside and becomes
                    # a documented deviation. Together with the missed visits
                    # above that puts the overall deviation rate near 10%, which
                    # is the sort of figure a real trial of this size reports.
                    if rng.random() < 0.06:
                        drift = rng.choice([4, 5, 6, 7, 9, 11, -4, -5])
                    else:
                        drift = rng.choice([0, 0, 0, 1, -1, 1, 2, -2, 3, -3])

                    actual = scheduled + timedelta(days=drift)
                    # Never record a visit as happening in the future.
                    if actual > reference_date:
                        actual = reference_date
                    visit["actual_date"] = actual
                    visit["status"] = VisitStatus.COMPLETED.value
                    visit["_performed_by_email"] = coordinator_email

                    # Beyond the window it is a deviation and must be documented.
                    off_by = abs((actual - scheduled).days)
                    if off_by > 3:
                        visit["is_protocol_deviation"] = True
                        visit["deviation_description"] = rng.choice(
                            DEVIATION_TEMPLATES
                        ).format(days=off_by)

            visits.append(visit)

    return visits


def _build_adverse_events(
    rng: random.Random,
    reference_date: date,
    subjects: list[dict],
    users: list[dict],
) -> list[dict]:
    """Attach adverse events to enrolled participants.

    Only people who actually took the study drug can have one, so screen
    failures are excluded.
    """
    enrolled = [s for s in subjects if s["enrollment_date"] is not None]
    events: list[dict] = []
    counter = 0

    # The Principal Investigator is the person accountable for reporting safety
    # events at their site, so they are named as the reporter.
    pi_by_site = {
        user["_site_code"]: user["email"]
        for user in users
        if user["role"] == UserRole.PRINCIPAL_INVESTIGATOR.value
    }

    # --- Ordinary events, spread across the enrolled population.
    ae_weights = [(entry["term_verbatim"], entry["weight"]) for entry in AE_CATALOGUE]
    by_term = {entry["term_verbatim"]: entry for entry in AE_CATALOGUE}

    # Roughly a quarter of participants report at least one event.
    n_events = int(len(enrolled) * 0.27)
    for _ in range(n_events):
        subject = rng.choice(enrolled)
        template = by_term[_weighted_pick(rng, ae_weights)]
        counter += 1
        events.append(
            _make_ae(rng, reference_date, subject, template, counter, serious=False)
        )

    # --- The deliberate site-02 gastrointestinal cluster, so Phase 4's signal
    # --- detection has a genuine pattern to surface.
    cluster_pool = [s for s in enrolled if s["_site_code"] == SIGNAL_CLUSTER_SITE]
    if cluster_pool:
        template = by_term[SIGNAL_CLUSTER_TERM]
        for _ in range(SIGNAL_CLUSTER_EXTRA_EVENTS):
            subject = rng.choice(cluster_pool)
            counter += 1
            events.append(
                _make_ae(rng, reference_date, subject, template, counter, serious=False)
            )

    # --- Serious events: one each, on distinct participants.
    sae_subjects = rng.sample(enrolled, k=min(len(SAE_CATALOGUE), len(enrolled)))
    for template, subject in zip(SAE_CATALOGUE, sae_subjects):
        counter += 1
        events.append(
            _make_ae(rng, reference_date, subject, template, counter, serious=True)
        )

    events.sort(key=lambda event: event["onset_date"])
    # Renumber so AE-0001 is the earliest event, which is how a site log reads.
    for index, event in enumerate(events, start=1):
        event["ae_number"] = f"AE-{index:04d}"
        event["_reported_by_email"] = pi_by_site.get(event["_site_code"])

    return events


def _make_ae(
    rng: random.Random,
    reference_date: date,
    subject: dict,
    template: dict,
    counter: int,
    *,
    serious: bool,
) -> dict:
    """Build one adverse-event row anchored inside the participant's time on study."""
    enrollment_date = subject["enrollment_date"]

    # The last day this participant was under observation.
    last_day = subject["withdrawal_date"] or subject["completed_date"] or reference_date
    last_day = min(last_day, reference_date)

    days_available = max(1, (last_day - enrollment_date).days)
    onset = enrollment_date + timedelta(days=rng.randint(1, days_available))

    outcome = template["outcome"]
    if outcome in {AEOutcome.RECOVERED.value, AEOutcome.RECOVERED_WITH_SEQUELAE.value}:
        resolution = min(onset + timedelta(days=rng.randint(1, 21)), reference_date)
    else:
        resolution = None  # still ongoing or recovering

    # An event is reported the day it is noticed, or a day or two later.
    reported_date = min(onset + timedelta(days=rng.randint(0, 2)), reference_date)

    # Serious events must reach the ethics committee promptly. Most do; the seed
    # leaves a couple late on purpose so Phase 5's compliance checks have
    # something real to flag.
    if serious:
        reported_to_ec = True
        ec_delay = rng.choice([0, 1, 1, 2, 9])
        reported_to_ec_date = min(reported_date + timedelta(days=ec_delay), reference_date)
    else:
        reported_to_ec = False
        reported_to_ec_date = None

    return {
        "_subject_code": subject["subject_code"],
        "_site_code": subject["_site_code"],
        # Overwritten with a chronological number once all events exist.
        "ae_number": f"AE-{counter:04d}",
        "term_verbatim": template["term_verbatim"],
        "description": template["description"],
        "onset_date": onset,
        "resolution_date": resolution,
        "severity": template["severity"],
        "is_serious": serious,
        "seriousness_criteria": template.get("seriousness_criteria"),
        "causality": template["causality"],
        "outcome": outcome,
        "action_taken": template.get("action_taken"),
        # MedDRA coding is left empty on purpose - Phase 4's NLP fills it in.
        "meddra_pt_code": None,
        "meddra_pt_term": None,
        "meddra_soc": None,
        "coding_confidence": None,
        "reported_date": reported_date,
        "reported_to_ec": reported_to_ec,
        "reported_to_ec_date": reported_to_ec_date,
    }


def _build_audit_logs(
    rng: random.Random,
    reference_date: date,
    trial: dict,
    users: list[dict],
    subjects: list[dict],
    events: list[dict],
) -> list[dict]:
    """A starting audit trail.

    These are the entries the seed itself is responsible for. From Phase 2 on,
    the application writes its own as users act.

    Each entry is timestamped at the moment the thing it describes actually
    happened - the ethics approval on the approval date, a participant's creation
    on their screening date - rather than all at load time. An audit trail whose
    every row shares one timestamp is obviously machine-generated and tells a
    reviewer nothing about sequence.
    """
    admin = next(u for u in users if u["role"] == UserRole.ADMIN.value)
    sponsor = next(u for u in users if u["role"] == UserRole.SPONSOR.value)
    ethics = next(u for u in users if u["role"] == UserRole.ETHICS_COMMITTEE.value)

    def at(day: date | None, fallback: date) -> datetime:
        """Put an entry at a plausible working hour on the given day."""
        on = day or fallback
        return datetime(on.year, on.month, on.day, rng.randint(9, 17), rng.randint(0, 59))

    logs: list[dict] = [
        {
            "_user_email": admin["email"],
            # The record exists before the committee can approve it: a protocol is
            # submitted to the ethics committee weeks ahead of its meeting.
            "timestamp": at(
                (trial["ethics_approval_date"] or reference_date) - timedelta(days=31),
                reference_date,
            ),
            "action": AuditAction.CREATE.value,
            "entity_type": "trials",
            "entity_label": trial["protocol_number"],
            "reason": "Synthetic demonstration dataset loaded by seed script.",
        },
        {
            "_user_email": ethics["email"],
            "timestamp": at(trial["ethics_approval_date"], reference_date),
            "action": AuditAction.APPROVE.value,
            "entity_type": "trials",
            "entity_label": trial["protocol_number"],
            "reason": (
                f"Ethics approval {trial['ethics_approval_number']} granted on "
                f"{trial['ethics_approval_date']}."
            ),
        },
        {
            "_user_email": admin["email"],
            "timestamp": at(trial["ctri_registration_date"], reference_date),
            "action": AuditAction.UPDATE.value,
            "entity_type": "trials",
            "entity_label": trial["protocol_number"],
            "field_name": "ctri_number",
            "old_value": None,
            "new_value": trial["ctri_number"],
            "reason": "CTRI registration completed prior to first enrolment.",
        },
        {
            "_user_email": sponsor["email"],
            "timestamp": at(reference_date - timedelta(days=3), reference_date),
            "action": AuditAction.VIEW.value,
            "entity_type": "trials",
            "entity_label": trial["protocol_number"],
            "reason": "Monthly enrolment review.",
        },
    ]

    # A few record-level entries, so the audit view is not all trial-level rows.
    for subject in subjects[:6]:
        logs.append(
            {
                "_user_email": admin["email"],
                "timestamp": at(subject["screening_date"], reference_date),
                "action": AuditAction.CREATE.value,
                "entity_type": "subjects",
                "entity_label": subject["subject_code"],
                "reason": "Synthetic participant record created by seed script.",
            }
        )

    for event in events[:4]:
        logs.append(
            {
                "_user_email": admin["email"],
                "timestamp": at(event["reported_date"] or event["onset_date"], reference_date),
                "action": AuditAction.CREATE.value,
                "entity_type": "adverse_events",
                "entity_label": event["ae_number"],
                "reason": "Synthetic adverse-event record created by seed script.",
            }
        )

    # One realistic correction, showing what a tracked data change looks like.
    if events:
        first = events[0]
        corrected_on = min(
            (first["reported_date"] or first["onset_date"]) + timedelta(days=2),
            reference_date,
        )
        logs.append(
            {
                "_user_email": admin["email"],
                "timestamp": at(corrected_on, reference_date),
                "action": AuditAction.UPDATE.value,
                "entity_type": "adverse_events",
                "entity_label": first["ae_number"],
                "field_name": "severity",
                "old_value": AESeverity.MILD.value,
                "new_value": first["severity"],
                "reason": (
                    "Severity corrected after investigator review of the source "
                    "notes."
                ),
            }
        )

    # Where the action came from. Part 11 audit trails record this so a reviewer
    # can tell an entry made at the site from one made by a remote monitor.
    for entry in logs:
        entry["ip_address"] = f"10.20.{rng.randint(1, 4)}.{rng.randint(10, 240)}"
        entry["user_agent"] = "AIIA-CTMS/0.1 (seed script)"

    logs.sort(key=lambda entry: entry["timestamp"])
    return logs


def _build_patient_requests(
    rng: random.Random,
    reference_date: date,
    users: list[dict],
) -> list[dict]:
    patient_users = [u for u in users if u["role"] == UserRole.PATIENT.value]
    admin_users = [u for u in users if u["role"] == UserRole.INSTITUTION_ADMIN.value]

    p1 = patient_users[0] if patient_users else None
    p2 = patient_users[1] if len(patient_users) > 1 else p1
    a1 = admin_users[0] if admin_users else None

    if not p1:
        return []

    def at(day: date, hour: int = 10, minute: int = 30) -> datetime:
        return datetime(day.year, day.month, day.day, hour, minute)

    requests = [
        {
            "_patient_email": p1["email"],
            "_site_code": p1.get("_site_code", "01"),
            "_subject_code": p1.get("_subject_code", "AIIA-ASH-01-014"),
            "_assigned_admin_email": a1["email"] if a1 else None,
            "category": "medication_query",
            "subject_line": "Timing of morning dose with warm milk",
            "message": "Can the morning churna dose be taken 15 minutes before breakfast instead of after food? Taking it on an empty stomach feels slightly easier.",
            "status": "resolved",
            "admin_response": "As per protocol guidance approved by Dr. Meenakshi Sharma (PI), the churna must be taken after food with warm milk to ensure optimal absorption and prevent gastric discomfort.",
            "created_at": at(reference_date - timedelta(days=6), 10, 15),
            "updated_at": at(reference_date - timedelta(days=5), 14, 30),
            "resolved_at": at(reference_date - timedelta(days=5), 14, 30),
        },
        {
            "_patient_email": p1["email"],
            "_site_code": p1.get("_site_code", "01"),
            "_subject_code": p1.get("_subject_code", "AIIA-ASH-01-014"),
            "_assigned_admin_email": a1["email"] if a1 else None,
            "category": "appointment_reschedule",
            "subject_line": "Request to reschedule Week 8 visit",
            "message": "I have family commitments this Friday. Could my Week 8 follow-up appointment be moved to the following Monday morning?",
            "status": "in_review",
            "admin_response": "Coordinator Kavita Nair is checking the allowable protocol visit window (+/- 3 days) with the investigator.",
            "created_at": at(reference_date - timedelta(days=2), 11, 45),
            "updated_at": at(reference_date - timedelta(days=1), 16, 20),
            "resolved_at": None,
        },
        {
            "_patient_email": p1["email"],
            "_site_code": p1.get("_site_code", "01"),
            "_subject_code": p1.get("_subject_code", "AIIA-ASH-01-014"),
            "_assigned_admin_email": None,
            "category": "symptom_inquiry",
            "subject_line": "Mild dry mouth noticed in the evening",
            "message": "Noticed slight dryness of mouth for the last two days in the evening. Is this expected or related to the trial medicine?",
            "status": "submitted",
            "admin_response": None,
            "created_at": at(reference_date - timedelta(days=1), 9, 30),
            "updated_at": at(reference_date - timedelta(days=1), 9, 30),
            "resolved_at": None,
        },
    ]
    if p2 and p2 != p1:
        requests.append(
            {
                "_patient_email": p2["email"],
                "_site_code": p2.get("_site_code", "02"),
                "_subject_code": p2.get("_subject_code", "AIIA-ASH-02-005"),
                "_assigned_admin_email": None,
                "category": "general_inquiry",
                "subject_line": "Trial travel reimbursement query",
                "message": "Inquiring about the procedure for submitting travel reimbursement receipts for the baseline visit.",
                "status": "submitted",
                "admin_response": None,
                "created_at": at(reference_date - timedelta(days=3), 14, 0),
                "updated_at": at(reference_date - timedelta(days=3), 14, 0),
                "resolved_at": None,
            }
        )
    return requests


def _build_econsents(
    rng: random.Random,
    reference_date: date,
    subjects: list[dict],
    users: list[dict],
) -> list[dict]:
    """Seed digital e-Consent records for participants enrolled on study."""
    econsents: list[dict] = []
    sample_sig = (
        "data:image/svg+xml;base64,PHN2ZyB4bWxucz0iaHR0cDovL3d3dy53My5vcmcvMjAwMC9zdmciIHdpZHRoPSIxODAiIGhlaWdodD0iNjAiPjxwYXRoIGQ9Ik0xMCA0MCBRIDMwIDEwIDUwIDM1IFQgOTAgMjAgVCAxNDAgNDAgVCAxNzAgMjAiIHN0cm9rZT0iIzFkNGVkOCIgc3Ryb2tlLXdpZHRoPSIzIiBmaWxsPSJub25lIiBzdHJva2UtbGluZWNhcD0icm91bmQiLz48L3N2Zz4="
    )

    enrolled = [s for s in subjects if s.get("enrollment_date") is not None]
    for s in enrolled:
        # Keep the demo participant's consent pending so user can sign live during the presentation!
        if s["subject_code"] == "AIIA-ASH-01-014":
            continue
        enroll_d = s["enrollment_date"]
        signed_at = datetime(enroll_d.year, enroll_d.month, enroll_d.day, 10, 15)
        name_clean = f"Participant {s['subject_code']}"
        lang = "hi" if rng.random() < 0.4 else "en"
        abha = f"14-{rng.randint(1000, 9999)}-{rng.randint(1000, 9999)}-{rng.randint(1000, 9999)}"

        digest_source = (
            f"AIIA-CTMS-ECONSENT:trial=1:site={s['_site_code']}:subject={s['subject_code']}:"
            f"lang={lang}:time={signed_at.isoformat()}"
        )
        sha = hashlib.sha256(digest_source.encode("utf-8")).hexdigest()

        econsents.append(
            {
                "_subject_code": s["subject_code"],
                "_site_code": s["_site_code"],
                "language": lang,
                "abha_id": abha,
                "signer_name": name_clean,
                "signature_data_url": sample_sig,
                "sha256_hash": sha,
                "status": ConsentStatus.SIGNED.value,
                "signed_at": signed_at,
                "ip_address": f"10.20.{rng.randint(1, 4)}.{rng.randint(10, 240)}",
                "user_agent": "AIIA-CTMS-Portal/1.0 (Mobile Web)",
                "created_at": signed_at,
                "updated_at": signed_at,
            }
        )
    return econsents


def generate(
    reference_date: date | None = None, random_seed: int = DEFAULT_SEED
) -> dict:
    """Build the whole synthetic dataset.

    Args:
        reference_date: the date to treat as "today". Everything is generated
            backwards from here, so the trial always looks like it has been
            running for about eight months. Defaults to the real today.
        random_seed: fix this and the same reference date always yields byte-for-byte
            the same dataset, which makes the demo reproducible.

    Returns:
        A dict of lists keyed by entity name, plus a `summary` of counts.
    """
    reference_date = reference_date or date.today()
    rng = random.Random(random_seed)

    trial = _build_trial(reference_date)
    sites = _build_sites(reference_date)
    users = _build_users()
    trial["_activated_by_email"] = next(
        user["email"] for user in users if user["role"] == UserRole.SPONSOR.value
    )
    subjects = _build_subjects(rng, reference_date)
    visits = _build_visits(rng, reference_date, subjects, users)
    adverse_events = _build_adverse_events(rng, reference_date, subjects, users)
    audit_logs = _build_audit_logs(rng, reference_date, trial, users, subjects, adverse_events)
    patient_requests = _build_patient_requests(rng, reference_date, users)
    econsents = _build_econsents(rng, reference_date, subjects, users)

    return {
        "reference_date": reference_date,
        "trial": trial,
        "sites": sites,
        "users": users,
        "subjects": subjects,
        "visits": visits,
        "adverse_events": adverse_events,
        "patient_requests": patient_requests,
        "econsents": econsents,
        "audit_logs": audit_logs,
        "summary": {
            "sites": len(sites),
            "users": len(users),
            "subjects_screened": len(subjects),
            "subjects_enrolled": sum(
                1 for s in subjects if s["enrollment_date"] is not None
            ),
            "visits": len(visits),
            "adverse_events": len(adverse_events),
            "patient_requests": len(patient_requests),
            "econsents": len(econsents),
            "serious_adverse_events": sum(
                1 for e in adverse_events if e["is_serious"]
            ),
            "protocol_deviations": sum(
                1 for v in visits if v["is_protocol_deviation"]
            ),
            "audit_logs": len(audit_logs),
        },
    }
