"""Privacy and Data Minimization Service under the Digital Personal Data Protection (DPDP) Act, 2023.

Implements purpose-limitation, role-based data minimization, and pseudonymization
for trial participants and patients.

Rules:
1. Site Clinical Staff (Principal Investigator, Coordinator, Institution Admin for their site)
   and the Patient themselves have legitimate clinical necessity to view unmasked patient PII
   (e.g., full signer name, phone number, ABHA ID) during direct clinical care and consent administration.
2. Oversight and Governance Roles (Sponsor, DSMB / Ethics Committee, Global Administrator,
   Regulator, External Monitors) MUST only receive minimized / pseudonymized data (e.g.,
   'Subject #01-014', masked phone '+91-XXXXX-XX321', masked ABHA '14-XXXX-XXXX-5544').
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from app.enums import UserRole

if TYPE_CHECKING:
    from app.rbac import CurrentUser


def should_mask_patient_pii(user: CurrentUser, site_id: int | None = None) -> bool:
    """Determine whether direct patient PII must be redacted/minimized for the caller.

    Returns True if caller is an oversight/admin/regulatory role that should NOT
    see unmasked patient identifiers.
    Returns False if caller is authorized site clinical staff (same site) or patient themselves.
    """
    # Patients viewing their own data are never masked
    if user.role == UserRole.PATIENT.value:
        return False

    # Site-specific clinical roles (PI, Coordinator, Institution Admin) for their own site
    site_clinical_roles = {
        UserRole.PRINCIPAL_INVESTIGATOR.value,
        UserRole.COORDINATOR.value,
        UserRole.INSTITUTION_ADMIN.value,
    }

    if user.role in site_clinical_roles:
        # If user has a site constraint, verify it matches
        if user.site_id is not None and site_id is not None:
            return user.site_id != site_id
        return False

    # All other roles (Sponsor, Ethics Committee, Regulator, Global Admin) receive minimized data
    return True


def mask_patient_name(name: str | None, subject_code: str | None = None) -> str:
    """Mask patient full name to a privacy-preserving pseudonym."""
    if not name:
        return "-"
    if subject_code:
        return f"Subject {subject_code}"
    return "De-identified Participant"


def mask_phone(phone: str | None) -> str | None:
    """Mask telephone numbers: '+91 9876543210' -> '+91 XXXXX XX210'."""
    if not phone or len(phone.strip()) < 4:
        return None
    cleaned = phone.strip()
    suffix = cleaned[-3:]
    prefix = "+91 " if cleaned.startswith("+91") or cleaned.startswith("+") else ""
    return f"{prefix}XXXXX-XX{suffix}"


def mask_abha_id(abha_id: str | None) -> str | None:
    """Mask Ayushman Bharat Health Account (ABHA) IDs: '14-9988-7766-5544' -> '14-XXXX-XXXX-5544'."""
    if not abha_id:
        return None
    parts = abha_id.strip().split("-")
    if len(parts) == 4:
        return f"{parts[0]}-XXXX-XXXX-{parts[3]}"
    if len(abha_id) > 6:
        return f"{abha_id[:2]}-XXXX-XXXX-{abha_id[-4:]}"
    return "XX-XXXX-XXXX"


def mask_email(email: str | None) -> str | None:
    """Mask email addresses: 'patient.01.014@demo.aiia-ctms.in' -> 'p***@***.in'."""
    if not email or "@" not in email:
        return email
    local_part, domain = email.split("@", 1)
    masked_local = f"{local_part[0]}***" if local_part else "***"
    domain_parts = domain.split(".")
    tld = domain_parts[-1] if domain_parts else "com"
    return f"{masked_local}@***.{tld}"
