import re

with open('backend/app/kpi.py', 'r', encoding='utf-8') as f:
    content = f.read()

new_institution_admin = '''def _institution_admin(
    session: Session, user: CurrentUser, stats: dict, trial: Trial, today: date
) -> tuple[list[dict], list[dict]]:
    site_id = user.scope_site_id
    site_obj = session.get(Site, site_id) if site_id else None
    site_name = site_obj.name if site_obj else (user.organization or "All Sites")
    site_code = site_obj.site_code if site_obj else ""

    # Personnel count (Exclude Patients)
    researchers = list(session.exec(
        select(User).where(User.site_id == site_id, User.is_active == True, User.role != UserRole.PATIENT.value)  # noqa: E712
    ).all()) if site_id else []

    enrolled = stats.get("enrollment", {}).get("enrolled", 0)
    screened = stats.get("enrollment", {}).get("screened", 0)
    target = stats.get("enrollment", {}).get("target", 0)
    recruitment_pct = stats.get("enrollment", {}).get("percent_of_target", 0)
    sae_count = stats.get("safety", {}).get("serious", 0)
    open_ae_val = _open_ae_count(session, trial.id, user)
    deviations = stats.get("visits", {}).get("protocol_deviations", 0)

    tiles = [
        _tile("institution", "Institution", f"{site_code} {site_name}".strip() or "All Sites", tone="neutral"),
        _tile("researchers", "Researchers & Staff", len(researchers), hint="Active personnel", tone="good"),
        _tile("enrolled", "Recruited", f"{enrolled} / {target}", hint=f"{recruitment_pct}% of target", tone="good" if recruitment_pct >= 80 else "warn"),
        _tile("open_aes", "Open Safety Events", open_ae_val, tone="warn" if open_ae_val > 0 else "good"),
        _tile("sae_count", "Serious AEs", sae_count, tone="bad" if sae_count > 0 else "good"),
        _tile("deviations", "Protocol Deviations", deviations, tone="warn" if deviations > 0 else "neutral"),
        _tile("screened", "Screened Participants", screened, hint=f"{enrolled} enrolled", tone="neutral"),
    ]

    staff_rows = [
        {
            "name": u.full_name,
            "role": u.role.replace("_", " ").title(),
            "email": u.email,
            "phone": u.phone or "-",
        }
        for u in researchers
    ]

    mock_queries = [
        {
            "query_id": "QRY-1001",
            "raised_by": "Neha Sharma (CRA)",
            "patient_id": "SUB-001",
            "issue": "Missing ECG source document for Visit 2",
            "status": "OPEN"
        },
        {
            "query_id": "QRY-1002",
            "raised_by": "Neha Sharma (CRA)",
            "patient_id": "SUB-045",
            "issue": "Concomitant medication dates overlap",
            "status": "OPEN"
        },
        {
            "query_id": "QRY-1003",
            "raised_by": "Neha Sharma (CRA)",
            "patient_id": "SUB-012",
            "issue": "Incomplete Vitals form",
            "status": "PENDING PI REVIEW"
        }
    ]

    blocks = [
        _table(
            "open_queries",
            "Open Data Queries (Site Action Required)",
            [
                ("query_id", "Query ID"),
                ("raised_by", "Raised By (CRA)"),
                ("patient_id", "Related Patient ID"),
                ("issue", "Issue"),
                ("status", "Status"),
            ],
            mock_queries,
            empty="No open queries.",
        ),
        _table(
            "staff",
            "Institutional Researchers & Clinical Staff",
            [
                ("name", "Name"),
                ("role", "Role"),
                ("email", "Email"),
                ("phone", "Phone"),
            ],
            staff_rows,
            empty="No staff members assigned.",
        ),
        _breakdown(
            "status_breakdown",
            "Participant Status Breakdown",
            stats.get("subjects_by_status", {}),
        ),
    ]
    return tiles, blocks'''

# Replace the block
start_idx = content.find("def _institution_admin(")
end_idx = content.find("def _patient(")
if start_idx != -1 and end_idx != -1:
    content = content[:start_idx] + new_institution_admin + "\n\n\n" + content[end_idx:]

with open('backend/app/kpi.py', 'w', encoding='utf-8') as f:
    f.write(content)
