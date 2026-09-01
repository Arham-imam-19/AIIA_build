"""CDISC SDTM (Study Data Tabulation Model) & Dataset-JSON v1.1 Generator.

Transforms relational clinical trial databases into standard CDISC SDTM domains:
- DM: Demographics Domain (USUBJID, AGE, SEX, ARM, SITEID, RFSTDTC)
- AE: Adverse Events Domain (AETERM, AEDECOD, AEBODSYS, AESEV, AESER, AEREL, AESTDTC)
- SV: Subject Visits Domain (VISITNUM, VISIT, SVSTDTC, SVENDTC, EPOCH)
- DV: Protocol Deviations Domain (DVTERM, DVDECOD, DVEVAL, DVDTC)
- TS: Trial Summary Domain (TSPARMCD, TSPARM, TSVAL)
"""

from __future__ import annotations

import csv
import io
import json
import zipfile
from datetime import date, datetime, timezone
from typing import Any

from sqlmodel import Session, select

from app.models import AdverseEvent, Site, Subject, Trial, Visit


def build_cdisc_sdtm_datasets(session: Session, trial_id: int) -> dict[str, list[dict[str, Any]]]:
    """Extract and transform live database entities into CDISC SDTM IG 3.3 tabulated domains."""
    trial = session.get(Trial, trial_id)
    if not trial:
        return {}

    study_id = trial.protocol_number

    # 1. Fetch related entities
    sites = {s.id: s for s in session.exec(select(Site).where(Site.trial_id == trial_id)).all()}
    subjects = list(session.exec(select(Subject).where(Subject.trial_id == trial_id).order_by(Subject.id)).all())
    subject_map = {s.id: s for s in subjects}

    visits = list(
        session.exec(
            select(Visit)
            .where(Visit.trial_id == trial_id)
            .order_by(Visit.subject_id, Visit.visit_number)
        ).all()
    )

    adverse_events = list(
        session.exec(
            select(AdverseEvent)
            .where(AdverseEvent.trial_id == trial_id)
            .order_by(AdverseEvent.subject_id, AdverseEvent.id)
        ).all()
    )

    # ----------------------------------------------------------------- DM (Demographics)
    dm_records: list[dict[str, Any]] = []
    for sub in subjects:
        site = sites.get(sub.site_id)
        site_code = site.site_code if site else f"SITE-{sub.site_id}"
        rfstdtc = sub.enrollment_date.isoformat() if sub.enrollment_date else (
            sub.screening_date.isoformat() if sub.screening_date else ""
        )

        dm_records.append(
            {
                "STUDYID": study_id,
                "DOMAIN": "DM",
                "USUBJID": sub.subject_code,
                "SUBJID": sub.subject_code.split("-")[-1] if "-" in sub.subject_code else sub.subject_code,
                "SITEID": site_code,
                "BRTHYR": sub.year_of_birth or "",
                "AGE": sub.age_at_enrollment or "",
                "AGEU": "YEARS" if sub.age_at_enrollment else "",
                "SEX": (sub.sex or "U").upper(),
                "ARMCD": (sub.arm or "UNASSIGNED").upper().replace(" ", "_"),
                "ARM": sub.arm or "Not Assigned",
                "ACTARMCD": (sub.arm or "UNASSIGNED").upper().replace(" ", "_"),
                "ACTARM": sub.arm or "Not Assigned",
                "COUNTRY": "IND",
                "RFSTDTC": rfstdtc,
                "PRAKRITI": (sub.prakriti or "").upper(),
                "HGHT": sub.height_cm or "",
                "WGHT": sub.weight_kg or "",
            }
        )

    # ----------------------------------------------------------------- AE (Adverse Events)
    ae_records: list[dict[str, Any]] = []
    ae_seq_tracker: dict[int, int] = {}
    for ae in adverse_events:
        sub = subject_map.get(ae.subject_id)
        usubjid = sub.subject_code if sub else f"SUBJ-{ae.subject_id}"
        seq = ae_seq_tracker.get(ae.subject_id, 0) + 1
        ae_seq_tracker[ae.subject_id] = seq

        ae_records.append(
            {
                "STUDYID": study_id,
                "DOMAIN": "AE",
                "USUBJID": usubjid,
                "AESEQ": seq,
                "AESPID": ae.ae_number,
                "AETERM": ae.term_verbatim,
                "AEDECOD": ae.meddra_pt_term or ae.term_verbatim,
                "AEPTCD": ae.meddra_pt_code or "",
                "AEBODSYS": ae.meddra_soc or "UNASSIGNED",
                "AESEV": (ae.severity or "MILD").upper(),
                "AESER": "Y" if ae.is_serious else "N",
                "AESCONG": "Y" if ae.is_serious and "birth" in (ae.seriousness_criteria or "").lower() else "N",
                "AESDISAB": "Y" if ae.is_serious and "disability" in (ae.seriousness_criteria or "").lower() else "N",
                "AESHOSP": "Y" if ae.is_serious and "hospital" in (ae.seriousness_criteria or "").lower() else "N",
                "AESLIFE": "Y" if ae.is_serious and "life" in (ae.seriousness_criteria or "").lower() else "N",
                "AESDTH": "Y" if ae.is_serious and "death" in (ae.seriousness_criteria or "").lower() else "N",
                "AEREL": (ae.causality or "UNRELATED").upper(),
                "AEOUT": (ae.outcome or "UNKNOWN").upper(),
                "AESTDTC": ae.onset_date.isoformat() if ae.onset_date else "",
                "AEENDTC": ae.resolution_date.isoformat() if ae.resolution_date else "",
                "AETOXGR": (ae.severity or "MILD").upper(),
            }
        )

    # ----------------------------------------------------------------- SV (Subject Visits)
    sv_records: list[dict[str, Any]] = []
    for v in visits:
        sub = subject_map.get(v.subject_id)
        usubjid = sub.subject_code if sub else f"SUBJ-{v.subject_id}"

        sv_records.append(
            {
                "STUDYID": study_id,
                "DOMAIN": "SV",
                "USUBJID": usubjid,
                "VISITNUM": v.visit_number,
                "VISIT": v.visit_name,
                "SVSTDTC": v.scheduled_date.isoformat() if v.scheduled_date else "",
                "SVENDTC": v.actual_date.isoformat() if v.actual_date else "",
                "SVUPDES": v.deviation_description or "",
                "EPOCH": "TREATMENT" if v.visit_number > 1 else "SCREENING",
                "SVSTATUS": (v.status or "SCHEDULED").upper(),
            }
        )

    # ----------------------------------------------------------------- DV (Protocol Deviations)
    dv_records: list[dict[str, Any]] = []
    dv_seq = 1
    for v in visits:
        if v.is_protocol_deviation:
            sub = subject_map.get(v.subject_id)
            usubjid = sub.subject_code if sub else f"SUBJ-{v.subject_id}"

            dv_records.append(
                {
                    "STUDYID": study_id,
                    "DOMAIN": "DV",
                    "USUBJID": usubjid,
                    "DVSEQ": dv_seq,
                    "DVTERM": v.deviation_description or f"Protocol deviation at {v.visit_name}",
                    "DVDECOD": "VISIT SCHEDULE DEVIATION" if "visit" in (v.deviation_description or "").lower() else "PROTOCOL DEVIATION",
                    "DVCAT": "VISIT WINDOW",
                    "DVEVAL": "INVESTIGATOR",
                    "DVDTC": v.actual_date.isoformat() if v.actual_date else (v.scheduled_date.isoformat() if v.scheduled_date else ""),
                }
            )
            dv_seq += 1

    # ----------------------------------------------------------------- TS (Trial Summary)
    ts_records: list[dict[str, Any]] = [
        {"STUDYID": study_id, "DOMAIN": "TS", "TSSEQ": 1, "TSPARMCD": "TITLE", "TSPARM": "Trial Title", "TSVAL": trial.title},
        {"STUDYID": study_id, "DOMAIN": "TS", "TSSEQ": 2, "TSPARMCD": "SHTITLE", "TSPARM": "Short Title", "TSVAL": trial.short_title},
        {"STUDYID": study_id, "DOMAIN": "TS", "TSSEQ": 3, "TSPARMCD": "SPONSOR", "TSPARM": "Sponsor Name", "TSVAL": trial.sponsor_name},
        {"STUDYID": study_id, "DOMAIN": "TS", "TSSEQ": 4, "TSPARMCD": "REGID", "TSPARM": "CTRI Identifier", "TSVAL": trial.ctri_number or "Not Registered"},
        {"STUDYID": study_id, "DOMAIN": "TS", "TSSEQ": 5, "TSPARMCD": "PHASE", "TSPARM": "Trial Phase", "TSVAL": trial.phase},
        {"STUDYID": study_id, "DOMAIN": "TS", "TSSEQ": 6, "TSPARMCD": "IND", "TSPARM": "Indication", "TSVAL": trial.indication},
        {"STUDYID": study_id, "DOMAIN": "TS", "TSSEQ": 7, "TSPARMCD": "AYUSHIND", "TSPARM": "Ayurveda Indication", "TSVAL": trial.indication_ayurveda or "Chittodvega"},
        {"STUDYID": study_id, "DOMAIN": "TS", "TSSEQ": 8, "TSPARMCD": "TRT", "TSPARM": "Investigational Intervention", "TSVAL": trial.intervention},
        {"STUDYID": study_id, "DOMAIN": "TS", "TSSEQ": 9, "TSPARMCD": "COMP", "TSPARM": "Comparator", "TSVAL": trial.comparator or "Placebo"},
        {"STUDYID": study_id, "DOMAIN": "TS", "TSSEQ": 10, "TSPARMCD": "DESIGN", "TSPARM": "Study Design", "TSVAL": trial.design},
    ]

    return {
        "DM": dm_records,
        "AE": ae_records,
        "SV": sv_records,
        "DV": dv_records,
        "TS": ts_records,
    }


def generate_cdisc_dataset_json(session: Session, trial_id: int) -> dict[str, Any]:
    """Generate official CDISC Dataset-JSON v1.1 structure containing all SDTM domains."""
    trial = session.get(Trial, trial_id)
    if not trial:
        return {}

    datasets = build_cdisc_sdtm_datasets(session, trial_id)
    now_str = datetime.now(timezone.utc).isoformat()

    items_data: dict[str, Any] = {}
    for domain_name, records in datasets.items():
        if not records:
            headers: list[str] = []
            rows: list[list[Any]] = []
        else:
            headers = list(records[0].keys())
            rows = [[row.get(h, "") for h in headers] for row in records]

        item_defs = [
            {
                "name": h,
                "type": "integer" if h.endswith("SEQ") or h in ("AGE", "BRTHYR", "VISITNUM") else "string",
                "label": h,
            }
            for h in headers
        ]

        items_data[domain_name] = {
            "name": domain_name,
            "label": f"SDTM {domain_name} Domain Dataset",
            "records": len(rows),
            "itemGroupData": {
                f"IG.{domain_name}": {
                    "records": len(rows),
                    "items": item_defs,
                    "itemData": rows,
                }
            },
        }

    return {
        "creationDateTime": now_str,
        "datasetJSONVersion": "1.1.0",
        "fileOID": f"AIIA.CTMS.SDTM.{trial.protocol_number}",
        "originator": "All India Institute of Ayurveda (AIIA) - NPvCC",
        "sourceSystem": "AIIA Clinical Trial Management System",
        "studyOID": trial.protocol_number,
        "metaDataVersionOID": "SDTM-IG-3.3",
        "clinicalData": {
            "studyOID": trial.protocol_number,
            "metaDataVersionOID": "SDTM-IG-3.3",
            "itemGroupData": items_data,
        },
    }


def generate_cdisc_csv_zip(session: Session, trial_id: int) -> bytes:
    """Generate a downloadable ZIP archive containing all CDISC SDTM domain CSVs and define.json manifest."""
    trial = session.get(Trial, trial_id)
    if not trial:
        return b""

    datasets = build_cdisc_sdtm_datasets(session, trial_id)
    zip_buffer = io.BytesIO()

    with zipfile.ZipFile(zip_buffer, "w", zipfile.ZIP_DEFLATED) as zip_file:
        for domain_name, records in datasets.items():
            csv_buffer = io.StringIO()
            if records:
                fieldnames = list(records[0].keys())
                writer = csv.DictWriter(csv_buffer, fieldnames=fieldnames)
                writer.writeheader()
                writer.writerows(records)
            else:
                writer = csv.writer(csv_buffer)
                writer.writerow(["STUDYID", "DOMAIN", "USUBJID"])

            zip_file.writestr(f"SDTM_{domain_name}.csv", csv_buffer.getvalue())

        # Include define metadata descriptor
        define_meta = {
            "protocol_number": trial.protocol_number,
            "title": trial.title,
            "ctri_number": trial.ctri_number,
            "phase": trial.phase,
            "domains": list(datasets.keys()),
            "standard": "CDISC SDTM v1.7 / SDTM-IG v3.3",
            "export_date": datetime.now(timezone.utc).isoformat(),
            "institution": "All India Institute of Ayurveda (AIIA)",
        }
        zip_file.writestr("define.json", json.dumps(define_meta, indent=2))

    zip_buffer.seek(0)
    return zip_buffer.getvalue()
