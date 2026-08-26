"""Harmonization and Data Ingestion API."""

import csv
import io
from typing import Any, Dict, List

from fastapi import APIRouter, Depends, HTTPException, UploadFile, File
from pydantic import BaseModel
from sqlmodel import Session, select

from app.db import get_session
from app.events import bus
from app.audit import record
from app.enums import AuditAction, SubjectStatus
from app.models import Subject, AdverseEvent, Trial, Site
from app.rbac import CurrentUser, get_current_user
from app.harmonization.engine import analyze_headers, MappingProposal

router = APIRouter(prefix="/api/harmonization", tags=["harmonization"])

class HarmonizationPreviewResponse(BaseModel):
    headers: List[str]
    proposals: List[MappingProposal]
    preview_rows: List[Dict[str, str]]

class ColumnMapping(BaseModel):
    original_header: str
    action: str  # MAP_CORE, MAP_SUPPLEMENTAL, DROP_PII, UNRESOLVED
    target: str | None

class HarmonizationCommitRequest(BaseModel):
    trial_id: int
    site_id: int | None = None
    mappings: List[ColumnMapping]
    data: List[Dict[str, str]]

@router.post("/preview", response_model=HarmonizationPreviewResponse)
async def preview_csv(file: UploadFile = File(...), user: CurrentUser = Depends(get_current_user)):
    """Parse uploaded CSV and return mapping proposals."""
    if not file.filename.endswith(".csv"):
        raise HTTPException(status_code=400, detail="Only CSV files are supported")
        
    contents = await file.read()
    decoded = contents.decode("utf-8")
    
    # Read CSV
    reader = csv.DictReader(io.StringIO(decoded))
    rows = []
    for _ in range(5):  # Grab up to 5 rows for sample extraction
        try:
            row = next(reader)
            rows.append(row)
        except StopIteration:
            break
            
    if not reader.fieldnames:
        raise HTTPException(status_code=400, detail="Empty CSV file")
        
    headers = list(reader.fieldnames)
    proposals = analyze_headers(headers, rows)
    
    # Send up to 10 rows for UI preview table
    preview_rows = rows.copy()
    try:
        for _ in range(5):
            preview_rows.append(next(reader))
    except StopIteration:
        pass
        
    return HarmonizationPreviewResponse(
        headers=headers,
        proposals=proposals,
        preview_rows=preview_rows
    )

@router.post("/commit")
async def commit_harmonized_data(
    payload: HarmonizationCommitRequest,
    user: CurrentUser = Depends(get_current_user),
    session: Session = Depends(get_session)
):
    """Ingest mapped data into the DB."""
    # 1. Enforce Site Scope context
    effective_site_id = payload.site_id
    if user.is_site_scoped:
        effective_site_id = user.site_id
    
    if not effective_site_id:
        raise HTTPException(status_code=400, detail="Target site must be provided")

    # Verify trial and site exist
    trial = session.get(Trial, payload.trial_id)
    site = session.get(Site, effective_site_id)
    if not trial or not site:
        raise HTTPException(status_code=404, detail="Trial or Site not found")

    mapping_dict = {m.original_header: m for m in payload.mappings}
    
    ingested_subjects = 0
    ingested_aes = 0
    
    for row in payload.data:
        # Extract demographic/subject fields and supplemental metadata
        subject_data = {}
        metadata = {}
        ae_data = {}
        has_ae = False
        
        for header, value in row.items():
            if not value:
                continue
                
            mapping = mapping_dict.get(header)
            if not mapping or mapping.action in ["DROP_PII", "UNRESOLVED"]:
                continue
                
            if mapping.action == "MAP_SUPPLEMENTAL":
                # target is like "SUPPQUAL.prakriti_dominant" -> store as "prakriti_dominant"
                key = mapping.target.split(".")[-1] if mapping.target else header
                metadata[key] = value
                
            elif mapping.action == "MAP_CORE" and mapping.target:
                # Assign to Subject or AE based on domain prefix
                if mapping.target.startswith("DM.") or mapping.target.startswith("VS."):
                    field_name = mapping.target.split(".")[1]
                    subject_data[field_name] = value
                elif mapping.target.startswith("AE."):
                    field_name = mapping.target.split(".")[1]
                    ae_data[field_name] = value
                    has_ae = True
                    
        # Find or Create Subject (Upsert logic)
        subject_code = subject_data.get("USUBJID")
        if not subject_code:
            continue  # Must have a subject ID to ingest relational data
            
        subject = session.exec(
            select(Subject).where(
                Subject.trial_id == payload.trial_id,
                Subject.site_id == effective_site_id,
                Subject.subject_code == subject_code
            )
        ).first()
        
        if not subject:
            # Create new subject
            subject = Subject(
                trial_id=payload.trial_id,
                site_id=effective_site_id,
                subject_code=subject_code,
                status=SubjectStatus.ENROLLED.value,
                arm=subject_data.get("ARM", "Unknown"),
                sex=subject_data.get("SEX", "Unknown"),
                prakriti=metadata.get("prakriti") or metadata.get("prakriti_dominant"),
                suppqual=metadata
            )
            # Basic parsing mapping
            if "AGE" in subject_data:
                try: subject.age_at_enrollment = int(float(subject_data["AGE"]))
                except ValueError: pass
            if "SYSBP" in subject_data:
                try: subject.height_cm = float(subject_data["SYSBP"]) # Mapped just for demo structure
                except ValueError: pass
            
            session.add(subject)
            session.flush() # get ID
            ingested_subjects += 1
        else:
            # Upsert / Merge metadata
            if subject.suppqual:
                subject.suppqual.update(metadata)
            else:
                subject.suppqual = metadata
            session.add(subject)
            
        # Append Adverse Event if data present
        if has_ae and "AETERM" in ae_data:
            ae = AdverseEvent(
                trial_id=payload.trial_id,
                site_id=effective_site_id,
                subject_id=subject.id,
                ae_number=f"AE-{subject_code}-{ingested_aes+1}",
                reported_term=ae_data["AETERM"],
                severity=ae_data.get("AESEV", "MILD").upper(),
                is_serious=False,
                status="REPORTED"
            )
            session.add(ae)
            ingested_aes += 1
            
    # Audit log
    record(
        session,
        user=user,
        action=AuditAction.DATA_INGESTION_HARMONIZATION if hasattr(AuditAction, "DATA_INGESTION_HARMONIZATION") else AuditAction.CREATE,
        entity_type="harmonization",
        entity_label=f"Ingested {len(payload.data)} records via AI Harmonizer",
        reason="Automated SDTM mapping and ingestion",
        trial_id=payload.trial_id,
    )
    
    session.commit()
    
    # Broadcast to update live KPIs
    await bus.publish({
        "type": "harmonization_ingest",
        "message": f"New CDISC standard batch ingested by {user.full_name}",
        "site_id": effective_site_id
    })
    
    return {
        "status": "success",
        "ingested_subjects": ingested_subjects,
        "ingested_aes": ingested_aes,
        "message": f"Successfully harmonized {ingested_subjects} subjects and {ingested_aes} adverse events."
    }
