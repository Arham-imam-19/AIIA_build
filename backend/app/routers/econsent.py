"""Electronic Informed Consent (e-Consent) endpoints under NDCT Rules 2019 & 21 CFR Part 11."""

from __future__ import annotations

import hashlib
from datetime import datetime, timezone
from pydantic import BaseModel, Field
from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlmodel import Session, select

from app import audit
from app.db import get_session
from app.enums import AuditAction, ConsentStatus, UserRole
from app.events import bus, now_iso
from app.models import EConsent, Site, Subject, Trial, User
from app.rbac import (
    CurrentUser,
    Permission,
    assert_site_visible,
    get_current_user,
    require,
    scoped,
)
from app.services import privacy

router = APIRouter(prefix="/api/econsent", tags=["econsent"])


# ---------------------------------------------------------------- schemas

class SignConsentRequest(BaseModel):
    signer_name: str = Field(min_length=2, max_length=200)
    language: str = Field(default="en", max_length=10)
    abha_id: str | None = Field(default=None, max_length=50)
    signature_data_url: str = Field(min_length=20, description="Base64 PNG signature drawing")


class EConsentPublic(BaseModel):
    id: int
    trial_id: int
    site_id: int
    site_name: str
    subject_id: int
    subject_code: str
    user_id: int
    signer_name: str
    language: str
    abha_id: str | None
    signature_data_url: str
    sha256_hash: str
    status: str
    signed_at: str
    ip_address: str | None


class ProtocolInfoSheet(BaseModel):
    trial_title_en: str
    trial_title_hi: str
    indication_en: str
    indication_hi: str
    investigation_product: str
    duration: str
    schedule_summary_en: str
    schedule_summary_hi: str
    key_points_en: list[str]
    key_points_hi: list[str]


class MyConsentResponse(BaseModel):
    subject_code: str
    has_signed: bool
    consent: EConsentPublic | None = None
    info_sheet: ProtocolInfoSheet


# ----------------------------------------------------------- bilingual texts

PROTOCOL_INFO_SHEET = ProtocolInfoSheet(
    trial_title_en="A Multicentre, Randomised, Double-Blind, Placebo-Controlled Trial to Evaluate the Efficacy and Safety of Ashwagandha (Withania somnifera) Root Churna in Adults with Generalised Anxiety Disorder",
    trial_title_hi="सामान्यीकृत चिंता विकार (चित्तोद्वेग) से पीड़ित वयस्कों में अश्वगंधा (विथानिया सोम्निफेरा) मूल चूर्ण की प्रभावकारिता और सुरक्षा का बहु-केंद्रीकृत, यादृच्छिक, दोहरा-अंधा, प्लेसीबो-नियंत्रित नैदानिक परीक्षण",
    indication_en="Generalised Anxiety Disorder (Chittodvega)",
    indication_hi="सामान्यीकृत चिंता विकार (चित्तोद्वेग)",
    investigation_product="Ashwagandha (Withania somnifera) Root Churna / Placebo 3g twice daily with warm milk",
    duration="84 Days (12 Weeks) with 6 scheduled clinical visits",
    schedule_summary_en="Screening (Day -14) -> Baseline (Day 0) -> Week 2 -> Week 4 -> Week 8 -> End of Study (Day 84)",
    schedule_summary_hi="स्क्रीनिंग (दिन -14) -> बेसलाइन (दिन 0) -> सप्ताह 2 -> सप्ताह 4 -> सप्ताह 8 -> अध्ययन समाप्ति (दिन 84)",
    key_points_en=[
        "Participation is completely voluntary. You may withdraw at any time without loss of medical care.",
        "Your health data is de-identified under CDISC international data protection guidelines.",
        "You will receive trial medication and protocol safety laboratory assessments at zero personal cost.",
        "All study visits and any adverse symptoms will be closely monitored by institutional Ayurvedic physicians.",
        "In compliance with NDCT Rules 2019, your digital signature is legally binding and cryptographically sealed.",
    ],
    key_points_hi=[
        "परीक्षण में भागीदारी पूरी तरह से स्वैच्छिक है। आप बिना किसी नुकसान के किसी भी समय अपना नाम वापस ले सकते हैं।",
        "सीडीआईएससी अंतरराष्ट्रीय डेटा सुरक्षा दिशानिर्देशों के तहत आपकी पहचान पूरी तरह से गोपनीय रखी जाएगी।",
        "परीक्षण दवा और सुरक्षा प्रयोगशाला जांच आपको बिना किसी शुल्क के उपलब्ध कराई जाएगी।",
        "सभी अध्ययन दौरों और किसी भी स्वास्थ्य लक्षण की संस्थान के विशेषज्ञ आयुर्वेदिक चिकित्सकों द्वारा नियमित निगरानी की जाएगी।",
        "एनडीसीटी नियम 2019 के अनुपालन में, आपका डिजिटल हस्ताक्षर कानूनी रूप से मान्य और इलेक्ट्रॉनिक रूप से सुरक्षित है।",
    ],
)


def _hydrate_consent(session: Session, consent: EConsent, user: CurrentUser | None = None) -> EConsentPublic:
    site = session.get(Site, consent.site_id)
    subject = session.get(Subject, consent.subject_id)
    subject_code = subject.subject_code if subject else f"SUBJ-{consent.subject_id}"

    signer_name = consent.signer_name
    abha_id = consent.abha_id

    # Apply DPDP Act 2023 Data Minimization if viewing user is an oversight/admin/regulatory role
    if user is not None and privacy.should_mask_patient_pii(user, consent.site_id):
        signer_name = privacy.mask_patient_name(consent.signer_name, subject_code)
        abha_id = privacy.mask_abha_id(consent.abha_id)

    return EConsentPublic(
        id=consent.id,  # type: ignore[arg-type]
        trial_id=consent.trial_id,
        site_id=consent.site_id,
        site_name=site.name if site else f"Site {consent.site_id}",
        subject_id=consent.subject_id,
        subject_code=subject_code,
        user_id=consent.user_id,
        signer_name=signer_name,
        language=consent.language,
        abha_id=abha_id,
        signature_data_url=consent.signature_data_url,
        sha256_hash=consent.sha256_hash,
        status=consent.status,
        signed_at=consent.signed_at.isoformat() if consent.signed_at else "",
        ip_address=consent.ip_address,
    )


# ---------------------------------------------------------------- endpoints

@router.get("/my", response_model=MyConsentResponse)
def get_my_consent(
    session: Session = Depends(get_session),
    user: CurrentUser = Depends(require(Permission.ECONSENT_READ)),
) -> MyConsentResponse:
    """Retrieve the logged-in participant's e-consent status and bilingual info sheet."""
    subject: Subject | None = None
    consent: EConsent | None = None
    if user.subject_id:
        subject = session.get(Subject, user.subject_id)
        if subject:
            consent = session.exec(select(EConsent).where(EConsent.subject_id == subject.id)).first()

    return MyConsentResponse(
        subject_code=subject.subject_code if subject else "UNLINKED",
        has_signed=consent is not None and consent.status == ConsentStatus.SIGNED.value,
        consent=_hydrate_consent(session, consent, user) if consent else None,
        info_sheet=PROTOCOL_INFO_SHEET,
    )


@router.post("/sign", response_model=EConsentPublic)
async def sign_econsent(
    body: SignConsentRequest,
    request: Request,
    session: Session = Depends(get_session),
    user: CurrentUser = Depends(require(Permission.ECONSENT_SIGN)),
) -> EConsentPublic:
    """Digitally sign informed consent with canvas signature drawing, SHA-256 seal & atomic 21 CFR Part 11 audit."""
    if not user.subject_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="no participant subject record linked to this account",
        )
    subject = session.get(Subject, user.subject_id)
    if not subject:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="linked participant subject not found",
        )

    now = datetime.now(timezone.utc)
    ip_addr = request.client.host if request.client else "127.0.0.1"
    user_agent = request.headers.get("user-agent", "Browser")

    # Compute SHA-256 cryptographic digest of canonical consent contents
    digest_source = (
        f"AIIA-CTMS-ECONSENT:trial={subject.trial_id}:site={subject.site_id}:"
        f"subject={subject.subject_code}:user={user.email}:name={body.signer_name}:"
        f"abha={body.abha_id or 'none'}:lang={body.language}:time={now.isoformat()}:"
        f"sig_prefix={body.signature_data_url[:80]}"
    )
    sha256_hash = hashlib.sha256(digest_source.encode("utf-8")).hexdigest()

    existing = session.exec(select(EConsent).where(EConsent.subject_id == subject.id)).first()
    if existing:
        consent = existing
        consent.signer_name = body.signer_name
        consent.language = body.language
        consent.abha_id = body.abha_id
        consent.signature_data_url = body.signature_data_url
        consent.sha256_hash = sha256_hash
        consent.status = ConsentStatus.SIGNED.value
        consent.signed_at = now
        consent.ip_address = ip_addr
        consent.user_agent = user_agent
        consent.updated_at = now
    else:
        consent = EConsent(
            trial_id=subject.trial_id,
            site_id=subject.site_id,
            subject_id=subject.id,  # type: ignore[arg-type]
            user_id=user.id,
            language=body.language,
            abha_id=body.abha_id,
            signer_name=body.signer_name,
            signature_data_url=body.signature_data_url,
            sha256_hash=sha256_hash,
            status=ConsentStatus.SIGNED.value,
            signed_at=now,
            ip_address=ip_addr,
            user_agent=user_agent,
            created_at=now,
            updated_at=now,
        )

    try:
        session.add(consent)
        session.flush()

        # 21 CFR Part 11 Electronic Signature Audit Trail entry in SAME transaction
        audit.record(
            session,
            user=user,
            action=AuditAction.SIGN,
            entity_type="econsents",
            entity_id=consent.id,
            entity_label=f"e-Consent: {subject.subject_code}",
            reason=f"Digital informed consent signed under NDCT Rules 2019 [SHA-256: {sha256_hash[:16]}...]",
            trial_id=subject.trial_id,
            request=request,
        )
        # Single atomic commit for both EConsent and AuditLog
        session.commit()
        session.refresh(consent)
    except Exception:
        session.rollback()
        raise

    # Broadcast sanitized event across Redis WebSockets AFTER DB transaction succeeds
    # Excludes all PII (no signer name, patient email, ABHA ID or signature data URL)
    try:
        await bus.publish(
            {
                "type": "econsent.signed",
                "at": now_iso(),
                "trial_id": subject.trial_id,
                "site_id": subject.site_id,
                "subject_id": subject.id,
                "label": f"Consent #{consent.id}",
                "entity_id": consent.id,
                "message": "Informed consent was digitally signed for a trial participant.",
            }
        )
    except Exception:
        # Redis failure must not corrupt or roll back already committed DB record
        pass

    return _hydrate_consent(session, consent, user)


@router.get("/subjects/{subject_id}", response_model=EConsentPublic)
def get_subject_consent(
    subject_id: int,
    session: Session = Depends(get_session),
    user: CurrentUser = Depends(require(Permission.ECONSENT_READ)),
) -> EConsentPublic:
    """View a participant's verified e-Consent certificate."""
    subject = session.get(Subject, subject_id)
    if not subject:
        raise HTTPException(status_code=404, detail=f"subject {subject_id} not found")

    if user.role == UserRole.PATIENT.value:
        if user.subject_id != subject_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="forbidden: patients may only view their own consent certificate",
            )
    elif user.is_site_scoped:
        assert_site_visible(user, subject.site_id)

    consent = session.exec(select(EConsent).where(EConsent.subject_id == subject_id)).first()
    if not consent:
        raise HTTPException(status_code=404, detail="e-Consent has not been recorded for this participant yet")

    return _hydrate_consent(session, consent, user)
