"""Tests for the synthetic data generator.

These run without a database, because `app.synthetic` is pure Python. They are
the safety net for the fiddly parts: date ordering, the enrolment funnel adding
up, and every cross-reference pointing at something real.

Run with:  docker compose exec backend pytest
"""

from collections import Counter
from datetime import date, timedelta

import pytest

from app import synthetic
from app.enums import (
    AESeverity,
    Prakriti,
    Sex,
    StudyArm,
    SubjectStatus,
    TrialStatus,
    VisitStatus,
    values,
)

REFERENCE = date(2026, 8, 25)


@pytest.fixture(scope="module")
def data() -> dict:
    """Generate once and share it - the tests only read."""
    return synthetic.generate(reference_date=REFERENCE)


# ---------------------------------------------------------------------------
# Reproducibility
# ---------------------------------------------------------------------------


def test_same_inputs_produce_identical_data():
    """A fixed reference date and seed must give the same dataset every time,
    otherwise a demo cannot be rehearsed."""
    first = synthetic.generate(reference_date=REFERENCE)
    second = synthetic.generate(reference_date=REFERENCE)
    assert first == second


def test_different_seed_produces_different_data():
    first = synthetic.generate(reference_date=REFERENCE, random_seed=1)
    second = synthetic.generate(reference_date=REFERENCE, random_seed=2)
    assert first["subjects"] != second["subjects"]


# ---------------------------------------------------------------------------
# Trial and sites
# ---------------------------------------------------------------------------


def test_trial_has_the_registration_fields_compliance_needs(data):
    trial = data["trial"]
    assert trial["ctri_number"]
    assert trial["ethics_approval_number"]
    assert trial["regulatory_approval_number"]
    assert trial["status"] in values(TrialStatus)


def test_trial_approvals_precede_the_first_enrolment(data):
    """Ethics and regulatory approval must predate the study start, and CTRI
    registration must predate the first participant. That ordering is the whole
    point of the NDCT gates in Phase 5, so the seed data has to respect it."""
    trial = data["trial"]
    assert trial["ethics_approval_date"] < trial["start_date"]
    assert trial["regulatory_approval_date"] < trial["start_date"]

    first_enrollment = min(
        s["enrollment_date"]
        for s in data["subjects"]
        if s["enrollment_date"] is not None
    )
    assert trial["ctri_registration_date"] < first_enrollment


def test_site_targets_add_up_to_the_trial_target(data):
    total = sum(site["target_enrollment"] for site in data["sites"])
    assert total == data["trial"]["target_enrollment"]


def test_sites_were_activated_before_the_reference_date(data):
    for site in data["sites"]:
        assert site["activation_date"] < REFERENCE


# ---------------------------------------------------------------------------
# Users
# ---------------------------------------------------------------------------


def test_all_five_personas_have_at_least_one_account(data):
    roles = {user["role"] for user in data["users"]}
    for required in (
        "principal_investigator",
        "sponsor",
        "ethics_committee",
        "regulator",
        "coordinator",
    ):
        assert required in roles, f"no demo account for {required}"


def test_emails_are_unique_and_obviously_synthetic(data):
    emails = [user["email"] for user in data["users"]]
    assert len(emails) == len(set(emails))
    assert all(email.endswith(synthetic.EMAIL_DOMAIN) for email in emails)


def test_site_staff_are_tied_to_a_site_and_oversight_roles_are_not(data):
    for user in data["users"]:
        if user["role"] in {"principal_investigator", "coordinator"}:
            assert user["_site_code"] is not None, user["email"]
        elif user["role"] in {"sponsor", "ethics_committee", "regulator"}:
            assert user["_site_code"] is None, user["email"]


def test_seed_sets_no_passwords(data):
    """Authentication is Phase 2. Until then no account should carry a
    credential, so nothing can silently log in."""
    assert all("hashed_password" not in user for user in data["users"])


# ---------------------------------------------------------------------------
# Subjects and the enrolment funnel
# ---------------------------------------------------------------------------


def test_subject_codes_are_unique(data):
    codes = [s["subject_code"] for s in data["subjects"]]
    assert len(codes) == len(set(codes))


def test_subject_codes_encode_their_site(data):
    for subject in data["subjects"]:
        assert f"-{subject['_site_code']}-" in subject["subject_code"]


def test_funnel_counts_reconcile(data):
    """Screened = enrolled + screen failures + still-in-screening. If this does
    not hold, the enrolment funnel on the dashboard is lying."""
    counts = Counter(s["status"] for s in data["subjects"])
    enrolled_statuses = {
        SubjectStatus.ENROLLED.value,
        SubjectStatus.ACTIVE.value,
        SubjectStatus.COMPLETED.value,
        SubjectStatus.WITHDRAWN.value,
        SubjectStatus.LOST_TO_FOLLOW_UP.value,
    }
    enrolled = sum(count for status, count in counts.items() if status in enrolled_statuses)

    assert enrolled == data["summary"]["subjects_enrolled"]
    assert (
        enrolled
        + counts[SubjectStatus.SCREEN_FAILED.value]
        + counts[SubjectStatus.SCREENING.value]
        == data["summary"]["subjects_screened"]
    )


def test_enrolment_stays_within_the_trial_target(data):
    assert (
        data["summary"]["subjects_enrolled"] <= data["trial"]["target_enrollment"]
    )


def test_per_site_enrolment_respects_each_site_target(data):
    by_site = Counter(
        s["_site_code"] for s in data["subjects"] if s["enrollment_date"] is not None
    )
    targets = {site["site_code"]: site["target_enrollment"] for site in data["sites"]}
    for site_code, enrolled in by_site.items():
        assert enrolled <= targets[site_code], site_code


def test_screening_always_precedes_enrolment(data):
    for subject in data["subjects"]:
        if subject["enrollment_date"] is not None:
            assert subject["screening_date"] < subject["enrollment_date"], (
                subject["subject_code"]
            )


def test_no_subject_date_is_in_the_future(data):
    """A dataset that claims things happened tomorrow is instantly not credible."""
    date_fields = (
        "screening_date",
        "enrollment_date",
        "randomization_date",
        "completed_date",
        "withdrawal_date",
    )
    for subject in data["subjects"]:
        for field in date_fields:
            value = subject[field]
            if value is not None:
                assert value <= REFERENCE, f"{subject['subject_code']}.{field}={value}"


def test_enrolment_never_precedes_site_activation(data):
    activation = {s["site_code"]: s["activation_date"] for s in data["sites"]}
    for subject in data["subjects"]:
        if subject["enrollment_date"] is not None:
            assert subject["enrollment_date"] >= activation[subject["_site_code"]], (
                subject["subject_code"]
            )


def test_completed_subjects_finished_the_full_course(data):
    completed = [
        s for s in data["subjects"] if s["status"] == SubjectStatus.COMPLETED.value
    ]
    assert completed
    for subject in completed:
        assert subject["completed_date"] is not None
        assert subject["withdrawal_date"] is None
        days_on_study = (subject["completed_date"] - subject["enrollment_date"]).days
        assert days_on_study >= synthetic.TREATMENT_DURATION_DAYS


def test_active_subjects_are_still_inside_the_treatment_window(data):
    active = [s for s in data["subjects"] if s["status"] == SubjectStatus.ACTIVE.value]
    assert active
    for subject in active:
        assert subject["completed_date"] is None
        assert subject["withdrawal_date"] is None
        elapsed = (REFERENCE - subject["enrollment_date"]).days
        assert elapsed < synthetic.TREATMENT_DURATION_DAYS, subject["subject_code"]


def test_withdrawn_subjects_have_a_date_and_a_documented_reason(data):
    withdrawn = [
        s
        for s in data["subjects"]
        if s["status"]
        in {SubjectStatus.WITHDRAWN.value, SubjectStatus.LOST_TO_FOLLOW_UP.value}
    ]
    assert withdrawn
    for subject in withdrawn:
        assert subject["withdrawal_date"] is not None
        assert subject["withdrawal_reason"], subject["subject_code"]
        assert subject["withdrawal_date"] > subject["enrollment_date"]
        assert subject["completed_date"] is None


def test_screen_failures_were_never_enrolled_or_randomised(data):
    failures = [
        s for s in data["subjects"] if s["status"] == SubjectStatus.SCREEN_FAILED.value
    ]
    assert failures
    for subject in failures:
        assert subject["enrollment_date"] is None
        assert subject["randomization_date"] is None
        assert subject["arm"] == StudyArm.NOT_RANDOMIZED.value
        assert subject["screen_failure_reason"]
        # No prakriti either: it is assessed at baseline, which they never reached.
        assert subject["prakriti"] is None


def test_randomised_subjects_are_split_between_the_two_arms(data):
    arms = Counter(
        s["arm"] for s in data["subjects"] if s["enrollment_date"] is not None
    )
    assert set(arms) == {StudyArm.TREATMENT.value, StudyArm.PLACEBO.value}
    # 1:1 allocation, so neither arm should run away with it.
    smaller, larger = sorted(arms.values())
    assert larger / smaller < 1.4, arms


def test_demographic_values_come_from_the_controlled_vocabularies(data):
    for subject in data["subjects"]:
        assert subject["sex"] in values(Sex)
        assert subject["status"] in values(SubjectStatus)
        assert subject["arm"] in values(StudyArm)
        if subject["prakriti"] is not None:
            assert subject["prakriti"] in values(Prakriti)


def test_ages_are_adult_and_plausible(data):
    for subject in data["subjects"]:
        if subject["age_at_enrollment"] is not None:
            assert 18 <= subject["age_at_enrollment"] <= 64


# ---------------------------------------------------------------------------
# Visits
# ---------------------------------------------------------------------------


def test_only_enrolled_subjects_have_visits(data):
    enrolled_codes = {
        s["subject_code"] for s in data["subjects"] if s["enrollment_date"] is not None
    }
    visit_codes = {v["_subject_code"] for v in data["visits"]}
    assert visit_codes <= enrolled_codes


def test_every_enrolled_subject_gets_the_full_schedule(data):
    per_subject = Counter(v["_subject_code"] for v in data["visits"])
    expected = len(synthetic.VISIT_SCHEDULE)
    assert per_subject
    assert set(per_subject.values()) == {expected}


def test_visit_numbers_are_sequential_per_subject(data):
    by_subject: dict[str, list[int]] = {}
    for visit in data["visits"]:
        by_subject.setdefault(visit["_subject_code"], []).append(visit["visit_number"])
    for code, numbers in by_subject.items():
        assert sorted(numbers) == list(range(1, len(synthetic.VISIT_SCHEDULE) + 1)), code


def test_completed_visits_have_an_actual_date_and_future_ones_do_not(data):
    for visit in data["visits"]:
        if visit["status"] == VisitStatus.COMPLETED.value:
            assert visit["actual_date"] is not None
            assert visit["actual_date"] <= REFERENCE
        elif visit["status"] == VisitStatus.SCHEDULED.value:
            assert visit["actual_date"] is None
            assert visit["scheduled_date"] > REFERENCE


def test_visits_after_withdrawal_are_cancelled_not_completed(data):
    exits = {
        s["subject_code"]: s["withdrawal_date"]
        for s in data["subjects"]
        if s["withdrawal_date"] is not None
    }
    checked = 0
    for visit in data["visits"]:
        exit_date = exits.get(visit["_subject_code"])
        if exit_date is not None and visit["scheduled_date"] > exit_date:
            assert visit["status"] == VisitStatus.CANCELLED.value
            assert visit["actual_date"] is None
            checked += 1
    assert checked > 0, "no post-withdrawal visits generated to check"


def test_every_deviation_is_documented(data):
    """A flagged deviation with no description is exactly what an auditor would
    pull you up on."""
    deviations = [v for v in data["visits"] if v["is_protocol_deviation"]]
    assert deviations
    for visit in deviations:
        assert visit["deviation_description"], visit


def test_deviation_rate_is_realistic(data):
    """Somewhere around 10%. Far higher looks like a broken site; far lower looks
    like nobody is recording them."""
    due = [
        v
        for v in data["visits"]
        if v["status"] in {VisitStatus.COMPLETED.value, VisitStatus.MISSED.value}
    ]
    rate = sum(1 for v in due if v["is_protocol_deviation"]) / len(due)
    assert 0.04 <= rate <= 0.16, f"deviation rate {rate:.1%}"


# ---------------------------------------------------------------------------
# Adverse events
# ---------------------------------------------------------------------------


def test_adverse_events_belong_to_enrolled_subjects_only(data):
    """Someone who never took the study drug cannot have a treatment-emergent
    adverse event."""
    enrolled_codes = {
        s["subject_code"] for s in data["subjects"] if s["enrollment_date"] is not None
    }
    for event in data["adverse_events"]:
        assert event["_subject_code"] in enrolled_codes


def test_ae_numbers_are_unique_and_chronological(data):
    events = data["adverse_events"]
    numbers = [e["ae_number"] for e in events]
    assert len(numbers) == len(set(numbers))
    assert numbers == sorted(numbers)
    onsets = [e["onset_date"] for e in events]
    assert onsets == sorted(onsets)


def test_ae_onset_falls_within_time_on_study(data):
    enrolment = {s["subject_code"]: s["enrollment_date"] for s in data["subjects"]}
    for event in data["adverse_events"]:
        assert event["onset_date"] > enrolment[event["_subject_code"]]
        assert event["onset_date"] <= REFERENCE


def test_ae_resolution_never_precedes_onset(data):
    for event in data["adverse_events"]:
        if event["resolution_date"] is not None:
            assert event["resolution_date"] >= event["onset_date"]
            assert event["resolution_date"] <= REFERENCE


def test_ongoing_events_have_no_resolution_date(data):
    for event in data["adverse_events"]:
        if event["outcome"] in {"ongoing", "recovering"}:
            assert event["resolution_date"] is None, event["ae_number"]


def test_serious_events_are_flagged_with_a_criterion_and_reported(data):
    serious = [e for e in data["adverse_events"] if e["is_serious"]]
    assert serious, "the demo needs at least one SAE to show the safety workflow"
    for event in serious:
        assert event["seriousness_criteria"], event["ae_number"]
        assert event["severity"] == AESeverity.SEVERE.value
        assert event["reported_to_ec"] is True
        assert event["reported_to_ec_date"] is not None


def test_non_serious_events_are_not_marked_as_ec_reported(data):
    for event in data["adverse_events"]:
        if not event["is_serious"]:
            assert event["reported_to_ec"] is False
            assert event["reported_to_ec_date"] is None


def test_meddra_coding_is_left_for_phase_4(data):
    """Phase 4's NLP fills these in. If the seed pre-filled them, that feature
    would appear to work when it had done nothing."""
    for event in data["adverse_events"]:
        assert event["meddra_pt_code"] is None
        assert event["meddra_pt_term"] is None
        assert event["meddra_soc"] is None
        assert event["coding_confidence"] is None


def test_descriptions_are_free_text_narratives(data):
    """Phase 4 needs something substantial to parse, not a one-word label."""
    for event in data["adverse_events"]:
        assert len(event["description"]) > 60, event["ae_number"]
        assert event["description"] != event["term_verbatim"]


def test_a_safety_signal_is_planted_for_phase_4_to_find(data):
    """One term is deliberately over-represented at one site. Signal detection
    that cannot find this has nothing to find at all."""
    cluster = [
        e
        for e in data["adverse_events"]
        if e["term_verbatim"] == synthetic.SIGNAL_CLUSTER_TERM
    ]
    at_cluster_site = [
        e for e in cluster if e["_site_code"] == synthetic.SIGNAL_CLUSTER_SITE
    ]
    elsewhere = [
        e for e in cluster if e["_site_code"] != synthetic.SIGNAL_CLUSTER_SITE
    ]
    assert len(at_cluster_site) > len(elsewhere), (
        f"cluster site has {len(at_cluster_site)}, rest have {len(elsewhere)}"
    )


def test_severity_is_mostly_mild(data):
    """Most adverse events in a real trial are minor. A dataset where everything
    is severe would make the safety dashboard meaningless."""
    counts = Counter(e["severity"] for e in data["adverse_events"])
    assert counts[AESeverity.MILD.value] > counts[AESeverity.SEVERE.value]


# ---------------------------------------------------------------------------
# Audit trail
# ---------------------------------------------------------------------------


def test_audit_entries_reference_real_users(data):
    emails = {user["email"] for user in data["users"]}
    for entry in data["audit_logs"]:
        assert entry["_user_email"] in emails


def test_audit_entries_always_say_why(data):
    """GCP expects a reason recorded against a change, not just the change."""
    for entry in data["audit_logs"]:
        assert entry.get("reason"), entry


def test_update_entries_record_what_changed(data):
    updates = [e for e in data["audit_logs"] if e["action"] == "update"]
    assert updates
    for entry in updates:
        assert entry["field_name"]
        assert entry["new_value"] is not None


# ---------------------------------------------------------------------------
# Cross-cutting
# ---------------------------------------------------------------------------


def test_every_reference_resolves(data):
    """No dangling pointers anywhere in the dataset."""
    site_codes = {site["site_code"] for site in data["sites"]}
    subject_codes = {s["subject_code"] for s in data["subjects"]}
    emails = {u["email"] for u in data["users"]}

    for subject in data["subjects"]:
        assert subject["_site_code"] in site_codes
    for user in data["users"]:
        assert user["_site_code"] is None or user["_site_code"] in site_codes
    for visit in data["visits"]:
        assert visit["_subject_code"] in subject_codes
    for event in data["adverse_events"]:
        assert event["_subject_code"] in subject_codes
        assert event["_site_code"] in site_codes
    for entry in data["audit_logs"]:
        assert entry["_user_email"] in emails


def test_summary_matches_the_actual_rows(data):
    summary = data["summary"]
    assert summary["sites"] == len(data["sites"])
    assert summary["users"] == len(data["users"])
    assert summary["subjects_screened"] == len(data["subjects"])
    assert summary["visits"] == len(data["visits"])
    assert summary["adverse_events"] == len(data["adverse_events"])
    assert summary["audit_logs"] == len(data["audit_logs"])
    assert summary["serious_adverse_events"] == sum(
        1 for e in data["adverse_events"] if e["is_serious"]
    )
    assert summary["protocol_deviations"] == sum(
        1 for v in data["visits"] if v["is_protocol_deviation"]
    )


def test_dataset_is_big_enough_to_demo(data):
    """A dashboard with four rows in it does not look like a working system."""
    summary = data["summary"]
    assert summary["subjects_enrolled"] >= 100
    assert summary["visits"] >= 500
    assert summary["adverse_events"] >= 30


def test_generator_works_for_any_reference_date():
    """Guards against date logic that only holds for one particular today."""
    for reference in (date(2026, 1, 15), date(2026, 8, 25), date(2027, 3, 2)):
        result = synthetic.generate(reference_date=reference)
        assert result["summary"]["subjects_enrolled"] > 100
        for subject in result["subjects"]:
            for field in ("enrollment_date", "completed_date", "withdrawal_date"):
                if subject[field] is not None:
                    assert subject[field] <= reference, (reference, field)


def test_defaults_to_today_when_no_reference_date_given():
    result = synthetic.generate()
    assert result["reference_date"] == date.today()
    latest = max(
        s["enrollment_date"]
        for s in result["subjects"]
        if s["enrollment_date"] is not None
    )
    assert latest <= date.today()
    assert latest > date.today() - timedelta(days=120)


# ---------------------------------------------------------------------------
# Attribution: every recorded action names a real person
# ---------------------------------------------------------------------------


def test_completed_visits_name_the_coordinator_who_recorded_them(data):
    """GCP expects to be able to ask "who wrote this down?" of any record."""
    emails_by_site = {
        user["_site_code"]: user["email"]
        for user in data["users"]
        if user["role"] == "coordinator"
    }
    site_by_subject = {s["subject_code"]: s["_site_code"] for s in data["subjects"]}

    completed = [v for v in data["visits"] if v["status"] == VisitStatus.COMPLETED.value]
    assert completed, "expected some completed visits"

    for visit in completed:
        site_code = site_by_subject[visit["_subject_code"]]
        assert visit["_performed_by_email"] == emails_by_site[site_code], visit


def test_visits_that_never_happened_name_nobody(data):
    """A missed or cancelled visit with a performer would be a fabricated record."""
    for visit in data["visits"]:
        if visit["status"] != VisitStatus.COMPLETED.value:
            assert visit["_performed_by_email"] is None, visit


def test_adverse_events_are_reported_by_the_site_investigator(data):
    """The Principal Investigator is accountable for safety reporting at a site."""
    pi_by_site = {
        user["_site_code"]: user["email"]
        for user in data["users"]
        if user["role"] == "principal_investigator"
    }
    for event in data["adverse_events"]:
        assert event["_reported_by_email"] == pi_by_site[event["_site_code"]], event


def test_every_attribution_email_matches_a_real_user(data):
    """No dangling reference: the seed has to resolve these to real user rows."""
    known = {user["email"] for user in data["users"]}
    referenced = {v["_performed_by_email"] for v in data["visits"]}
    referenced |= {e["_reported_by_email"] for e in data["adverse_events"]}
    referenced |= {log["_user_email"] for log in data["audit_logs"]}
    referenced.discard(None)
    assert referenced <= known


# ---------------------------------------------------------------------------
# Audit trail
# ---------------------------------------------------------------------------


def test_audit_entries_are_in_chronological_order(data):
    stamps = [log["timestamp"] for log in data["audit_logs"]]
    assert stamps == sorted(stamps)


def test_no_audit_entry_is_dated_in_the_future(data):
    for log in data["audit_logs"]:
        assert log["timestamp"].date() <= REFERENCE, log


def test_audit_timestamps_are_spread_out_not_all_identical(data):
    """One shared timestamp on every row is the tell-tale of a fabricated log."""
    distinct_days = {log["timestamp"].date() for log in data["audit_logs"]}
    assert len(distinct_days) >= 4


def test_audit_entries_fall_in_working_hours(data):
    for log in data["audit_logs"]:
        assert 9 <= log["timestamp"].hour <= 17, log


def test_ethics_approval_entry_is_dated_on_the_approval_date(data):
    entry = next(
        log
        for log in data["audit_logs"]
        if log["action"] == "approve" and log["entity_type"] == "trials"
    )
    assert entry["timestamp"].date() == data["trial"]["ethics_approval_date"]


def test_every_audit_entry_records_where_it_came_from(data):
    """Part 11 trails record the origin, so a site entry can be told from a
    remote monitor's."""
    for log in data["audit_logs"]:
        assert log["ip_address"].startswith("10.20.")
        assert log["user_agent"]


def test_trial_record_is_created_before_ethics_approves_it(data):
    """A protocol is submitted to the committee weeks before its meeting, so the
    record must exist before the approval entry - not after it."""
    trial_logs = [log for log in data["audit_logs"] if log["entity_type"] == "trials"]
    created = next(log for log in trial_logs if log["action"] == "create")
    approved = next(log for log in trial_logs if log["action"] == "approve")
    assert created["timestamp"] < approved["timestamp"]


def test_ctri_registration_is_logged_before_the_first_enrolment(data):
    """Registering the trial publicly is a legal precondition for enrolling the
    first participant, so the audit trail has to show it happening first."""
    ctri = next(
        log
        for log in data["audit_logs"]
        if log.get("field_name") == "ctri_number"
    )
    first_enrolment = min(
        s["enrollment_date"] for s in data["subjects"] if s["enrollment_date"]
    )
    assert ctri["timestamp"].date() <= first_enrolment
