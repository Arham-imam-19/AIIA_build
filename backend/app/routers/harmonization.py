from fastapi import APIRouter, UploadFile, File, Depends, HTTPException
from sqlmodel import Session, select
import csv
import io
import json
from rapidfuzz import process, fuzz

from app.db import get_session
from app.models.subject import Subject
from app.models.adverse_event import AdverseEvent
from app.rbac import CurrentUser, require, Permission
from app.enums import AuditAction
from app.cdisc_dictionary import CDISC_MAPPINGS, DPDP_DROP
from app import audit
import app.events as bus
from datetime import date

router = APIRouter(prefix="/api/harmonization", tags=["harmonization"])

def get_best_match(header: str) -> dict:
    header_lower = header.lower().strip()
    
    # 1. DPDP Act Filter
    if any(pii in header_lower for pii in DPDP_DROP):
        return {"target": "DPDP_DROP", "confidence": 100, "reason": "PII Detection"}
    
    # 2. Fuzzy Match against CDISC definitions
    best_target = "IGNORE"
    best_score = 0
    
    for entity, mappings in CDISC_MAPPINGS.items():
        for target, synonyms in mappings.items():
            match = process.extractOne(header_lower, synonyms, scorer=fuzz.token_sort_ratio)
            if match and match[1] > best_score:
                best_score = match[1]
                best_target = target
                
    if best_score < 40:
        return {"target": "IGNORE", "confidence": 0, "reason": "No Match"}
        
    return {"target": best_target, "confidence": round(best_score), "reason": "Fuzzy Match"}


@router.post("/preview")
async def preview_csv(file: UploadFile = File(...), user: CurrentUser = Depends(require(Permission.TRIAL_READ))):
    """Parses a CSV file in memory, extracts a sample, and runs the RapidFuzz ML engine."""
    content = await file.read()
    try:
        decoded = content.decode('utf-8')
        reader = csv.reader(io.StringIO(decoded))
        headers = next(reader, [])
    except Exception as e:
        raise HTTPException(status_code=400, detail="Invalid CSV format")

    sample_data = []
    for _ in range(3):
        try:
            sample_data.append(next(reader))
        except StopIteration:
            break

    mappings = []
    for i, header in enumerate(headers):
        match_info = get_best_match(header)
        mappings.append({
            "original_header": header,
            "sample_values": [row[i] for row in sample_data if i < len(row)],
            "suggested_target": match_info["target"],
            "confidence": match_info["confidence"]
        })

    return {"filename": file.filename, "mappings": mappings}


@router.post("/commit")
async def commit_harmonized_data(
    file: UploadFile = File(...), 
    mapping_config: str = "", # JSON string of mappings from UI
    site_id: int = 1,
    trial_id: int = 1,
    session: Session = Depends(get_session),
    user: CurrentUser = Depends(require(Permission.TRIAL_READ))
):
    """Commits the harmonized data, stripping PII and splitting entities."""
    try:
        mappings = json.loads(mapping_config)
    except:
        raise HTTPException(status_code=400, detail="Invalid mapping configuration")
        
    content = await file.read()
    decoded = content.decode('utf-8')
    reader = csv.DictReader(io.StringIO(decoded))
    
    inserted_subjects = 0
    inserted_aes = 0
    
    for row in reader:
        subject_data = {}
        suppqual_data = {}
        ae_data = {}
        
        for key, val in row.items():
            if not val or not val.strip():
                continue
            
            target = mappings.get(key, "IGNORE")
            if target == "IGNORE" or target == "DPDP_DROP":
                continue
                
            if target.startswith("DM."):
                field = target.split(".")[1].lower()
                if field == "usubjid":
                    subject_data["subject_code"] = val
                elif field == "age":
                    try: subject_data["age_at_enrollment"] = int(val)
                    except: pass
                elif field == "sex":
                    subject_data["sex"] = val.lower()
                    
            elif target.startswith("SUPPQUAL."):
                field = target.split(".")[1].lower()
                suppqual_data[field] = val
                
            elif target.startswith("AE."):
                field = target.split(".")[1].lower()
                if field == "aeterm":
                    ae_data["term_verbatim"] = val
                elif field == "aesev":
                    ae_data["severity"] = val.lower()
                    
        # 1. Upsert Subject
        if "subject_code" in subject_data:
            subject = session.exec(
                select(Subject).where(Subject.subject_code == subject_data["subject_code"])
            ).one_or_none()
            
            if not subject:
                subject = Subject(
                    trial_id=trial_id,
                    site_id=site_id,
                    status="enrolled",
                    arm="unassigned",
                    enrollment_date=date.today(),
                    sex=subject_data.get("sex", "unknown"),
                    **subject_data
                )
                session.add(subject)
                session.flush() # get ID
                inserted_subjects += 1
                
            # Update suppqual
            if suppqual_data:
                current_sq = dict(subject.suppqual) if subject.suppqual else {}
                current_sq.update(suppqual_data)
                subject.suppqual = current_sq
                session.add(subject)
                
            # 2. Add Adverse Event (if present)
            if "term_verbatim" in ae_data:
                ae = AdverseEvent(
                    subject_id=subject.id,
                    trial_id=trial_id,
                    site_id=site_id,
                    term_verbatim=ae_data["term_verbatim"],
                    severity=ae_data.get("severity", "mild"),
                    onset_date=date.today()
                )
                session.add(ae)
                inserted_aes += 1
                
    # Audit Log
    audit.record(
        session, user, AuditAction.CREATE,
        entity_type="harmonization_batch", entity_id=0, entity_label=file.filename,
        field_name="batch_ingest", old_value=None, new_value=f"Ingested {inserted_subjects} subjects, {inserted_aes} AEs",
        reason="Automated CDISC Harmonization Pipeline", trial_id=trial_id
    )
    
    session.commit()
    
    # Broadcast to update live dashboards
    try:
        await bus.publish({
            "type": "dashboard_update",
            "message": f"Harmonization complete. Added {inserted_subjects} patients and {inserted_aes} AEs."
        })
    except: pass
    
    return {"message": "Success", "subjects_inserted": inserted_subjects, "aes_inserted": inserted_aes}
