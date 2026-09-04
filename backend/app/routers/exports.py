"""Universal Data Export Router: CDISC SDTM Dataset-JSON & HL7 FHIR R4 Bundles."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlmodel import Session

from app.db import get_session
from app.models import Subject, Trial
from app.rbac import (
    CurrentUser,
    Permission,
    assert_site_visible,
    require,
)
from app.services import cdisc, fhir

router = APIRouter(prefix="/api", tags=["exports"])


@router.get("/trials/{trial_id}/export/cdisc-json")
def export_trial_cdisc_json(
    trial_id: int,
    session: Session = Depends(get_session),
    user: CurrentUser = Depends(require(Permission.EXPORT)),
) -> dict:
    """Export clinical trial tabulated study data conforming to official CDISC Dataset-JSON v1.1."""
    trial = session.get(Trial, trial_id)
    if not trial:
        raise HTTPException(status_code=404, detail=f"trial {trial_id} not found")

    return cdisc.generate_cdisc_dataset_json(session, trial_id)


@router.get("/trials/{trial_id}/export/cdisc-sdtm.zip")
def export_trial_cdisc_sdtm_zip(
    trial_id: int,
    session: Session = Depends(get_session),
    user: CurrentUser = Depends(require(Permission.EXPORT)),
) -> Response:
    """Download standard CDISC SDTM IG 3.3 package containing domain CSVs (DM, AE, SV, DV, TS) & define manifest."""
    trial = session.get(Trial, trial_id)
    if not trial:
        raise HTTPException(status_code=404, detail=f"trial {trial_id} not found")

    zip_bytes = cdisc.generate_cdisc_csv_zip(session, trial_id)
    filename = f"CDISC_SDTM_{trial.protocol_number}.zip"

    return Response(
        content=zip_bytes,
        media_type="application/zip",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.get("/trials/{trial_id}/export/fhir-bundle")
def export_trial_fhir_bundle(
    trial_id: int,
    session: Session = Depends(get_session),
    user: CurrentUser = Depends(require(Permission.EXPORT)),
) -> dict:
    """Export complete trial clinical research graph as an HL7 FHIR R4 Collection Bundle."""
    trial = session.get(Trial, trial_id)
    if not trial:
        raise HTTPException(status_code=404, detail=f"trial {trial_id} not found")

    return fhir.build_fhir_trial_bundle(session, trial_id, user)


@router.get("/subjects/{subject_id}/export/fhir")
def export_subject_fhir_bundle(
    subject_id: str,
    session: Session = Depends(get_session),
    user: CurrentUser = Depends(require(Permission.SUBJECT_READ)),
) -> dict:
    """Export one participant's complete clinical trial timeline as an HL7 FHIR R4 Bundle."""
    subject = None
    if str(subject_id).isdigit():
        subject = session.get(Subject, int(subject_id))
    if not subject:
        subject = session.exec(select(Subject).where(Subject.subject_code == str(subject_id))).first()
    if not subject:
        raise HTTPException(status_code=404, detail=f"subject {subject_id} not found")

    if user.is_site_scoped:
        assert_site_visible(user, subject.site_id)

    return fhir.build_fhir_subject_bundle(session, subject.id, user)
