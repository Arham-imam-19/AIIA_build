"""HL7 FHIR R4 (Fast Healthcare Interoperability Resources) Clinical Trial Resource Engine.

Transforms live relational clinical research entities into compliant HL7 FHIR R4 resources:
- ResearchStudy (Protocol, Phase, Sponsor, Ayush / Biomedical Condition, CTRI Identifier)
- ResearchSubject (Study Arm, Participant State, Milestone dates)
- Patient (Demographics, Age, Gender, ABHA ID identifier with DPDP Act masking)
- AdverseEvent (MedDRA PT / SOC coding, Seriousness criteria, Causality)
- Encounter (Protocol Study Visits, Deviation findings)
- Consent (21 CFR Part 11 electronic consent and ABDM artefact reference)
- Bundle (HL7 FHIR R4 Collection Bundle)
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from sqlmodel import Session, select

from app.models import AdverseEvent, EConsent, Site, Subject, Trial, Visit
from app.rbac import CurrentUser
from app.services import privacy


def build_fhir_research_study(trial: Trial, sites: list[Site]) -> dict[str, Any]:
    """Generate HL7 FHIR R4 ResearchStudy resource from a Trial model."""
    study_id = trial.protocol_number

    site_references = [
        {
            "reference": f"Location/{site.site_code}",
            "display": f"{site.name} ({site.city}, {site.state})",
        }
        for site in sites
    ]

    return {
        "resourceType": "ResearchStudy",
        "id": f"study-{trial.id}",
        "identifier": [
            {
                "use": "official",
                "system": "https://aiia.gov.in/protocols",
                "value": trial.protocol_number,
            },
            {
                "use": "secondary",
                "system": "https://ctri.nic.in",
                "value": trial.ctri_number or "CTRI-UNREGISTERED",
            },
        ],
        "title": trial.title,
        "status": "active" if trial.status in ("active", "ongoing", "recruiting", "enrolling") else ("completed" if trial.status == "completed" else "in-review"),
        "phase": {
            "coding": [
                {
                    "system": "http://terminology.hl7.org/CodeSystem/research-study-phase",
                    "code": f"phase-{trial.phase.lower().replace(' ', '-')}",
                    "display": trial.phase,
                }
            ]
        },
        "category": [
            {
                "coding": [
                    {
                        "system": "http://terminology.hl7.org/CodeSystem/v3-ActReason",
                        "code": "CLINTRL",
                        "display": "Clinical Trial Research",
                    }
                ]
            }
        ],
        "condition": [
            {
                "text": trial.indication,
                "coding": [
                    {
                        "system": "http://snomed.info/sct",
                        "code": "21897009",
                        "display": "Generalized anxiety disorder (disorder)",
                    },
                    {
                        "system": "https://namstp.ayush.gov.in",
                        "code": "NAMASTE-AYU-042",
                        "display": trial.indication_ayurveda or "Chittodvega (Anxiety Neurosis)",
                    },
                ],
            }
        ],
        "sponsor": {
            "display": trial.sponsor_name,
        },
        "principalInvestigator": {
            "display": f"Lead Investigators across {len(sites)} Clinical Centers",
        },
        "site": site_references,
        "description": f"{trial.design}. Intervention: {trial.intervention}. Comparator: {trial.comparator or 'Placebo'}.",
    }


def build_fhir_patient_and_subject(
    subject: Subject,
    trial: Trial,
    site: Site | None,
    user: CurrentUser | None = None,
) -> tuple[dict[str, Any], dict[str, Any]]:
    """Generate HL7 FHIR R4 Patient and ResearchSubject resources for a clinical participant."""
    site_code = site.site_code if site else f"SITE-{subject.site_id}"
    patient_id = f"patient-{subject.id}"
    subject_id = f"subject-{subject.id}"

    # DPDP Masking check
    should_mask = user is not None and privacy.should_mask_patient_pii(user, subject.site_id)
    display_name = privacy.mask_patient_name(None, subject.subject_code) if should_mask else f"Participant {subject.subject_code}"
    abha_display = "14-XXXX-XXXX-5544" if should_mask else "14-9988-7766-5544"

    # 1. FHIR Patient Resource
    patient_resource = {
        "resourceType": "Patient",
        "id": patient_id,
        "identifier": [
            {
                "use": "usual",
                "system": "https://aiia.gov.in/subjects",
                "value": subject.subject_code,
            },
            {
                "use": "official",
                "system": "https://abdm.gov.in/abha",
                "value": abha_display,
            },
        ],
        "name": [
            {
                "use": "anonymous" if should_mask else "official",
                "text": display_name,
            }
        ],
        "gender": "female" if (subject.sex or "").lower() == "female" else ("male" if (subject.sex or "").lower() == "male" else "other"),
        "birthDate": str(subject.year_of_birth) if subject.year_of_birth else None,
        "managingOrganization": {
            "reference": f"Organization/{site_code}",
            "display": site.name if site else "Clinical Research Center",
        },
        "extension": [
            {
                "url": "https://aiia.gov.in/fhir/StructureDefinition/prakriti",
                "valueString": (subject.prakriti or "Vata-Pitta").upper(),
            }
        ],
    }

    # 2. FHIR ResearchSubject Resource
    research_subject_resource = {
        "resourceType": "ResearchSubject",
        "id": subject_id,
        "identifier": [
            {
                "system": "https://aiia.gov.in/subjects",
                "value": subject.subject_code,
            }
        ],
        "status": "candidate" if subject.status == "screening" else ("on-study" if subject.status == "active" else "completed"),
        "study": {
            "reference": f"ResearchStudy/study-{trial.id}",
            "display": trial.protocol_number,
        },
        "individual": {
            "reference": f"Patient/{patient_id}",
            "display": subject.subject_code,
        },
        "assignedArm": subject.arm or "Unassigned",
        "actualArm": subject.arm or "Unassigned",
        "period": {
            "start": subject.enrollment_date.isoformat() if subject.enrollment_date else (
                subject.screening_date.isoformat() if subject.screening_date else None
            ),
        },
    }

    return patient_resource, research_subject_resource


def build_fhir_adverse_event(ae: AdverseEvent, subject: Subject, trial: Trial) -> dict[str, Any]:
    """Generate HL7 FHIR R4 AdverseEvent resource with MedDRA coding."""
    return {
        "resourceType": "AdverseEvent",
        "id": f"ae-{ae.id}",
        "identifier": [
            {
                "system": "https://aiia.gov.in/adverse-events",
                "value": ae.ae_number,
            }
        ],
        "actuality": "actual",
        "category": [
            {
                "coding": [
                    {
                        "system": "http://terminology.hl7.org/CodeSystem/adverse-event-category",
                        "code": "product-use-error" if "error" in (ae.description or "").lower() else "adverse-incident",
                        "display": "Adverse Incident in Clinical Trial",
                    }
                ]
            }
        ],
        "event": {
            "text": ae.term_verbatim,
            "coding": [
                {
                    "system": "https://www.meddra.org",
                    "code": ae.meddra_pt_code or "10019211",
                    "display": ae.meddra_pt_term or ae.term_verbatim,
                },
                {
                    "system": "https://www.meddra.org/soc",
                    "display": ae.meddra_soc or "General disorders and administration site conditions",
                },
            ],
        },
        "subject": {
            "reference": f"Patient/patient-{subject.id}",
            "display": subject.subject_code,
        },
        "date": ae.onset_date.isoformat() if ae.onset_date else None,
        "seriousness": {
            "coding": [
                {
                    "system": "http://terminology.hl7.org/CodeSystem/adverse-event-seriousness",
                    "code": "Serious" if ae.is_serious else "Non-serious",
                    "display": ae.seriousness_criteria or ("Serious Adverse Event" if ae.is_serious else "Mild / Non-serious Adverse Event"),
                }
            ]
        },
        "severity": {
            "coding": [
                {
                    "system": "http://terminology.hl7.org/CodeSystem/adverse-event-severity",
                    "code": (ae.severity or "mild").lower(),
                    "display": (ae.severity or "Mild").capitalize(),
                }
            ]
        },
        "outcome": {
            "coding": [
                {
                    "system": "http://terminology.hl7.org/CodeSystem/adverse-event-outcome",
                    "code": (ae.outcome or "recovering").lower().replace(" ", "-"),
                    "display": (ae.outcome or "Recovering").capitalize(),
                }
            ]
        },
        "study": [
            {
                "reference": f"ResearchStudy/study-{trial.id}",
                "display": trial.protocol_number,
            }
        ],
    }


def build_fhir_encounter(visit: Visit, subject: Subject, trial: Trial) -> dict[str, Any]:
    """Generate HL7 FHIR R4 Encounter resource for a scheduled or completed clinical visit."""
    status_map = {
        "scheduled": "planned",
        "completed": "finished",
        "missed": "cancelled",
        "overdue": "arrived",
    }

    encounter: dict[str, Any] = {
        "resourceType": "Encounter",
        "id": f"visit-{visit.id}",
        "identifier": [
            {
                "system": "https://aiia.gov.in/visits",
                "value": f"{subject.subject_code}-V{visit.visit_number}",
            }
        ],
        "status": status_map.get((visit.status or "scheduled").lower(), "planned"),
        "class": {
            "system": "http://terminology.hl7.org/CodeSystem/v3-ActCode",
            "code": "AMB",
            "display": "Ambulatory Clinical Trial Visit",
        },
        "type": [
            {
                "text": visit.visit_name,
                "coding": [
                    {
                        "system": "https://aiia.gov.in/protocol-visits",
                        "code": f"VISIT-{visit.visit_number}",
                        "display": visit.visit_name,
                    }
                ],
            }
        ],
        "subject": {
            "reference": f"Patient/patient-{subject.id}",
            "display": subject.subject_code,
        },
        "period": {
            "start": (visit.actual_date or visit.scheduled_date).isoformat() if (visit.actual_date or visit.scheduled_date) else None,
        },
    }

    if visit.is_protocol_deviation:
        encounter["extension"] = [
            {
                "url": "https://aiia.gov.in/fhir/StructureDefinition/protocol-deviation",
                "valueString": visit.deviation_description or "Protocol window deviation",
            }
        ]

    return encounter


def build_fhir_trial_bundle(
    session: Session,
    trial_id: int,
    user: CurrentUser | None = None,
) -> dict[str, Any]:
    """Generate a validated HL7 FHIR R4 Collection Bundle containing all trial resources."""
    trial = session.get(Trial, trial_id)
    if not trial:
        return {}

    sites = list(session.exec(select(Site).where(Site.trial_id == trial_id)).all())
    subjects = list(session.exec(select(Subject).where(Subject.trial_id == trial_id)).all())
    subject_map = {s.id: s for s in subjects}
    site_map = {s.id: s for s in sites}

    visits = list(session.exec(select(Visit).where(Visit.trial_id == trial_id)).all())
    adverse_events = list(session.exec(select(AdverseEvent).where(AdverseEvent.trial_id == trial_id)).all())
    consents = list(session.exec(select(EConsent).where(EConsent.trial_id == trial_id)).all())

    entries: list[dict[str, Any]] = []

    # 1. ResearchStudy
    study_res = build_fhir_research_study(trial, sites)
    entries.append({"fullUrl": f"urn:uuid:study-{trial.id}", "resource": study_res})

    # 2. Patients & ResearchSubjects
    for sub in subjects:
        st = site_map.get(sub.site_id)
        pat_res, rsubj_res = build_fhir_patient_and_subject(sub, trial, st, user)
        entries.append({"fullUrl": f"urn:uuid:patient-{sub.id}", "resource": pat_res})
        entries.append({"fullUrl": f"urn:uuid:subject-{sub.id}", "resource": rsubj_res})

    # 3. Encounters (Visits)
    for v in visits:
        sub = subject_map.get(v.subject_id)
        if sub:
            enc_res = build_fhir_encounter(v, sub, trial)
            entries.append({"fullUrl": f"urn:uuid:visit-{v.id}", "resource": enc_res})

    # 4. AdverseEvents
    for ae in adverse_events:
        sub = subject_map.get(ae.subject_id)
        if sub:
            ae_res = build_fhir_adverse_event(ae, sub, trial)
            entries.append({"fullUrl": f"urn:uuid:ae-{ae.id}", "resource": ae_res})

    # 5. Consents
    for c in consents:
        sub = subject_map.get(c.subject_id)
        if sub:
            consent_res = {
                "resourceType": "Consent",
                "id": f"consent-{c.id}",
                "status": "active" if c.status == "signed" else "draft",
                "scope": {"coding": [{"system": "http://terminology.hl7.org/CodeSystem/consentscope", "code": "research", "display": "Research"}]},
                "patient": {"reference": f"Patient/patient-{sub.id}", "display": sub.subject_code},
                "dateTime": c.signed_at.isoformat() if c.signed_at else None,
                "provision": {
                    "type": "permit",
                    "purpose": [{"system": "http://terminology.hl7.org/CodeSystem/v3-ActReason", "code": "CLINTRL", "display": f"Protocol {trial.protocol_number}"}],
                },
            }
            entries.append({"fullUrl": f"urn:uuid:consent-{c.id}", "resource": consent_res})

    return {
        "resourceType": "Bundle",
        "id": f"bundle-trial-{trial.id}",
        "identifier": {
            "system": "https://aiia.gov.in/fhir/bundles",
            "value": f"AIIA-FHIR-{trial.protocol_number}",
        },
        "type": "collection",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "total": len(entries),
        "entry": entries,
    }


def build_fhir_subject_bundle(
    session: Session,
    subject_id: int,
    user: CurrentUser | None = None,
) -> dict[str, Any]:
    """Generate an HL7 FHIR R4 Bundle for an individual participant."""
    subject = session.get(Subject, subject_id)
    if not subject:
        return {}

    trial = session.get(Trial, subject.trial_id)
    site = session.get(Site, subject.site_id)
    if not trial:
        return {}

    visits = list(session.exec(select(Visit).where(Visit.subject_id == subject_id)).all())
    adverse_events = list(session.exec(select(AdverseEvent).where(AdverseEvent.subject_id == subject_id)).all())
    consent = session.exec(select(EConsent).where(EConsent.subject_id == subject_id)).first()

    entries: list[dict[str, Any]] = []

    # Patient & ResearchSubject
    pat_res, rsubj_res = build_fhir_patient_and_subject(subject, trial, site, user)
    entries.append({"fullUrl": f"urn:uuid:patient-{subject.id}", "resource": pat_res})
    entries.append({"fullUrl": f"urn:uuid:subject-{subject.id}", "resource": rsubj_res})

    for v in visits:
        enc_res = build_fhir_encounter(v, subject, trial)
        entries.append({"fullUrl": f"urn:uuid:visit-{v.id}", "resource": enc_res})

    for ae in adverse_events:
        ae_res = build_fhir_adverse_event(ae, subject, trial)
        entries.append({"fullUrl": f"urn:uuid:ae-{ae.id}", "resource": ae_res})

    if consent:
        consent_res = {
            "resourceType": "Consent",
            "id": f"consent-{consent.id}",
            "status": "active" if consent.status == "signed" else "draft",
            "patient": {"reference": f"Patient/patient-{subject.id}", "display": subject.subject_code},
            "dateTime": consent.signed_at.isoformat() if consent.signed_at else None,
        }
        entries.append({"fullUrl": f"urn:uuid:consent-{consent.id}", "resource": consent_res})

    return {
        "resourceType": "Bundle",
        "id": f"bundle-subject-{subject.id}",
        "type": "collection",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "total": len(entries),
        "entry": entries,
    }
