"""Who is allowed to see and do what.

**RBAC (role-based access control)** attaches permissions to job titles rather
than to individual people. A hotel keycard opens your floor; the manager's opens
every floor. Nobody edits your card when you change rooms - they change which
role your card holds.

Two independent questions are answered here, and keeping them separate is what
makes the rules readable:

1. **What kind of thing may this role touch?** Answered by `ROLE_PERMISSIONS`
   below - a plain table of role to permission set.
2. **Whose rows may they see?** Answered by site scoping. A Principal
   Investigator and a Coordinator are *site-scoped*: their world is their own
   hospital, and another site's participant is a 403, not an empty result. A
   Sponsor, Ethics Committee member or Regulator sees every site.

Why "hard" scoping rather than just hiding the other sites: a filter you can
remove by editing the URL is not access control. Every query is narrowed
server-side, and asking for a record outside your scope is refused explicitly.
"""

from __future__ import annotations

from enum import Enum

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pydantic import BaseModel
from sqlmodel import Session

from app import security
from app.db import get_session
from app.enums import UserRole
from app.events import bus
from app.models import User


class Permission(str, Enum):
    """One capability. Named `area:verb` so a permission reads as a sentence."""

    TRIAL_READ = "trial:read"  # the protocol, its dates, its registrations
    SITE_READ = "site:read"  # the participating hospitals / institutions
    INSTITUTION_MANAGE = "institution:manage"  # create or manage institutions
    SUBJECT_READ = "subject:read"  # participant records (de-identified)
    SUBJECT_WRITE = "subject:write"  # screen or enrol someone
    VISIT_READ = "visit:read"  # the appointment schedule
    VISIT_WRITE = "visit:write"  # record that a visit happened
    AE_READ = "ae:read"  # adverse events - the safety picture
    AE_WRITE = "ae:write"  # report a new adverse event
    COMPLIANCE_READ = "compliance:read"  # ethics/regulatory status, deviations
    ETHICS_WRITE = "ethics:write"  # update trial ethics-approval information
    CTRI_WRITE = "ctri:write"  # update trial CTRI registration information
    REGULATORY_WRITE = "regulatory:write"  # update regulatory approval information
    ACTIVATION_WRITE = "activation:write"  # activate an eligible trial
    AUDIT_READ = "audit:read"  # the who-changed-what trail
    USER_READ = "user:read"  # the list of people on the study
    USER_MANAGE = "user:manage"  # add or coordinate researchers / staff
    EXPORT = "export"  # pull data out for a submission
    PATIENT_REQUEST_READ = "patient_request:read"  # view patient inquiries and requests
    PATIENT_REQUEST_WRITE = "patient_request:write"  # submit patient requests
    PATIENT_REQUEST_RESPOND = "patient_request:respond"  # respond to patient inquiries
    ECONSENT_READ = "econsent:read"  # view informed consent records & certificates
    ECONSENT_SIGN = "econsent:sign"  # digitally sign electronic informed consent


# Shorthand so the table below fits on a screen.
_P = Permission

# --------------------------------------------------------------------------
# THE MATRIX. This table is the single source of truth for authorisation, and
# /api/rbac-matrix serves it to the UI so the screen can never disagree with the
# enforcement.

#
# Each role is written as "what this person's job actually needs", which is why
# the sets are uneven:
#
#   Principal Investigator  runs the trial at one hospital. Full clinical view
#                           and write access - but only for their own site.
#   Coordinator (CRC)       does the day-to-day data entry at one hospital. Same
#                           site limit, no compliance view: not their call.
#   Sponsor                 funds and monitors the study. Sees everything across
#                           all sites and owns trial-wide CTRI registration and
#                           regulatory approval, but cannot edit site-level data.
#   Ethics Committee        an independent safety and ethics reviewer. Deliberately
#                           NOT given the participant list: their remit is safety
#                           events, deviations and compliance, not browsing who is
#                           enrolled.
#   Regulator               oversight (CDSCO / Ministry of Ayush). Read-only across
#                           everything, including the full audit trail.
#   Admin                   keeps the system running. Everything, because someone
#                           has to be able to fix it during a demo.

# --------------------------------------------------------------------------
ROLE_PERMISSIONS: dict[str, frozenset[Permission]] = {
    UserRole.ADMIN.value: frozenset(Permission),
    UserRole.INSTITUTION_ADMIN.value: frozenset(
        {
            _P.TRIAL_READ,
            _P.SITE_READ,
            _P.SUBJECT_READ,
            _P.VISIT_READ,
            _P.AE_READ,
            _P.COMPLIANCE_READ,
            _P.USER_READ,
            _P.USER_MANAGE,
            _P.PATIENT_REQUEST_READ,
            _P.PATIENT_REQUEST_RESPOND,
            _P.ECONSENT_READ,
        }
    ),
    UserRole.PRINCIPAL_INVESTIGATOR.value: frozenset(
        {
            _P.TRIAL_READ,
            _P.SITE_READ,
            _P.SUBJECT_READ,
            _P.SUBJECT_WRITE,
            _P.VISIT_READ,
            _P.VISIT_WRITE,
            _P.AE_READ,
            _P.AE_WRITE,
            _P.COMPLIANCE_READ,
            _P.USER_READ,
            _P.PATIENT_REQUEST_READ,
            _P.ECONSENT_READ,
        }
    ),
    UserRole.COORDINATOR.value: frozenset(
        {
            _P.TRIAL_READ,
            _P.SITE_READ,
            _P.SUBJECT_READ,
            _P.SUBJECT_WRITE,
            _P.VISIT_READ,
            _P.VISIT_WRITE,
            _P.AE_READ,
            _P.AE_WRITE,
            _P.PATIENT_REQUEST_READ,
            _P.ECONSENT_READ,
        }
    ),
    UserRole.SPONSOR.value: frozenset(
        {
            _P.TRIAL_READ,
            _P.SITE_READ,
            _P.SUBJECT_READ,
            _P.VISIT_READ,
            _P.AE_READ,
            _P.COMPLIANCE_READ,
            _P.USER_READ,
            _P.EXPORT,

            _P.CTRI_WRITE,
            _P.REGULATORY_WRITE,
            _P.ACTIVATION_WRITE,

            _P.ECONSENT_READ,

        }
    ),
    UserRole.ETHICS_COMMITTEE.value: frozenset(
        {
            _P.TRIAL_READ,
            _P.SITE_READ,
            _P.VISIT_READ,  # needed to review protocol deviations
            _P.AE_READ,
            _P.COMPLIANCE_READ,
            _P.ETHICS_WRITE,
            _P.AUDIT_READ,
            _P.ECONSENT_READ,
        }
    ),
    UserRole.REGULATOR.value: frozenset(
        {
            _P.TRIAL_READ,
            _P.SITE_READ,
            _P.SUBJECT_READ,
            _P.VISIT_READ,
            _P.AE_READ,
            _P.COMPLIANCE_READ,
            _P.AUDIT_READ,
            _P.USER_READ,
            _P.EXPORT,
            _P.ECONSENT_READ,
        }
    ),
    UserRole.PATIENT.value: frozenset(
        {
            _P.TRIAL_READ,
            _P.SITE_READ,
            _P.VISIT_READ,
            _P.PATIENT_REQUEST_READ,
            _P.PATIENT_REQUEST_WRITE,
            _P.ECONSENT_READ,
            _P.ECONSENT_SIGN,
        }
    ),
}

# The roles whose view is narrowed to their own hospital/institution.
SITE_SCOPED_ROLES: frozenset[str] = frozenset(
    {
        UserRole.INSTITUTION_ADMIN.value,
        UserRole.PRINCIPAL_INVESTIGATOR.value,
        UserRole.COORDINATOR.value,
        UserRole.PATIENT.value,
    }
)

# The roles that must remain blinded to treatment allocation/randomization arms.
BLINDED_ROLES: frozenset[str] = frozenset(
    {
        UserRole.SPONSOR.value,
    }
)

# Human labels, used by the dashboards and the matrix endpoint.
ROLE_LABELS: dict[str, str] = {
    UserRole.ADMIN.value: "Primary Administrator",
    UserRole.INSTITUTION_ADMIN.value: "Institution Administrator",
    UserRole.PRINCIPAL_INVESTIGATOR.value: "Principal Investigator (Researcher)",
    UserRole.COORDINATOR.value: "Clinical Research Coordinator",
    UserRole.SPONSOR.value: "Sponsor",
    UserRole.ETHICS_COMMITTEE.value: "Ethics Committee",
    UserRole.REGULATOR.value: "Regulator",
    UserRole.PATIENT.value: "Patient (Participant)",
}

PERMISSION_LABELS: dict[str, str] = {
    _P.TRIAL_READ.value: "View the trial and its protocol",
    _P.SITE_READ.value: "View participating sites / institutions",
    _P.INSTITUTION_MANAGE.value: "Manage institutions and sites",
    _P.SUBJECT_READ.value: "View participants",
    _P.SUBJECT_WRITE.value: "Screen and enrol participants",
    _P.VISIT_READ.value: "View the visit schedule",
    _P.VISIT_WRITE.value: "Record visits",
    _P.AE_READ.value: "View adverse events",
    _P.AE_WRITE.value: "Report adverse events",
    _P.COMPLIANCE_READ.value: "View ethics and regulatory compliance",
    _P.ETHICS_WRITE.value: "Update trial ethics approval",
    _P.CTRI_WRITE.value: "Update trial CTRI registration",
    _P.REGULATORY_WRITE.value: "Update trial regulatory approval",
    _P.ACTIVATION_WRITE.value: "Activate an eligible trial",
    _P.AUDIT_READ.value: "View the audit trail",
    _P.USER_READ.value: "View study personnel and researchers",
    _P.USER_MANAGE.value: "Manage personnel and researchers",
    _P.EXPORT.value: "Export data for submission",
    _P.PATIENT_REQUEST_READ.value: "View patient requests and inquiries",
    _P.PATIENT_REQUEST_WRITE.value: "Submit patient requests to institution",
    _P.PATIENT_REQUEST_RESPOND.value: "Respond to patient inquiries and requests",
    _P.ECONSENT_READ.value: "View electronic informed consent records & certificates",
    _P.ECONSENT_SIGN.value: "Digitally sign electronic informed consent",
}


class CurrentUser(BaseModel):
    """The logged-in user, as the rest of the app sees them.

    Deliberately not the `User` table row: nothing downstream should be able to
    reach `hashed_password`, and a plain object cannot accidentally be committed
    back to the database.
    """

    id: int
    email: str
    full_name: str
    role: str
    site_id: int | None = None
    subject_id: int | None = None
    organization: str | None = None
    # Copied off the token so a WebSocket can log out the same session.
    jti: str | None = None

    @property
    def role_label(self) -> str:
        return ROLE_LABELS.get(self.role, self.role.replace("_", " ").title())

    @property
    def permissions(self) -> frozenset[Permission]:
        return ROLE_PERMISSIONS.get(self.role, frozenset())

    def can(self, permission: Permission) -> bool:
        return permission in self.permissions

    @property
    def is_site_scoped(self) -> bool:
        return self.role in SITE_SCOPED_ROLES

    @property
    def is_blinded(self) -> bool:
        return self.role in BLINDED_ROLES

    @property
    def scope_site_id(self) -> int | None:
        """The single site this user is limited to, or None for "all sites".

        A site-scoped user whose record has no site is an inconsistency, and it
        must fail closed. `_UNREACHABLE_SITE_ID` is how: they see nothing at all
        rather than everything.
        """
        if not self.is_site_scoped:
            return None
        return self.site_id if self.site_id is not None else _UNREACHABLE_SITE_ID


# No site row can have this id, so filtering on it returns nothing. Used only for
# the fail-closed case above.
_UNREACHABLE_SITE_ID = -1


# ------------------------------------------------------------- authentication

# `auto_error=False` so a missing header lands in our own handler and produces a
# message that says what to do, instead of FastAPI's bare "Not authenticated".
_bearer = HTTPBearer(auto_error=False, description="Paste the token from /api/auth/login")


def _unauthorized(detail: str) -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail=detail,
        # Tells a browser or API client that a bearer token is the way in.
        headers={"WWW-Authenticate": "Bearer"},
    )


async def user_from_token(token: str, session: Session) -> CurrentUser:
    """Turn a raw token into a CurrentUser, or raise 401 explaining why not.

    Shared by the HTTP dependency and the WebSocket handler, which cannot use
    FastAPI dependencies for the token because a browser's WebSocket API cannot
    set an Authorization header.
    """
    try:
        claims = security.decode_access_token(token)
    except security.TokenError as exc:
        raise _unauthorized(str(exc)) from exc

    if await bus.is_token_revoked(claims.get("jti")):
        raise _unauthorized("this token was logged out; log in again")

    # The token carries the role, but the database is the authority: a user
    # deactivated five minutes ago must not keep working until their token
    # expires. One cheap primary-key lookup buys that.
    user = session.get(User, claims["user_id"])
    if user is None:
        raise _unauthorized("the user in this token no longer exists")
    if not user.is_active:
        raise _unauthorized("this account has been deactivated")

    return CurrentUser(
        id=user.id,  # type: ignore[arg-type]
        email=user.email,
        full_name=user.full_name,
        role=user.role,
        site_id=user.site_id,
        subject_id=user.subject_id,
        organization=user.organization,
        jti=claims.get("jti"),
    )


async def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(_bearer),
    session: Session = Depends(get_session),
) -> CurrentUser:
    """FastAPI dependency: the logged-in user, or 401."""
    if credentials is None or not credentials.credentials:
        raise _unauthorized(
            "not signed in - log in at /api/auth/login and send the token as "
            "'Authorization: Bearer <token>'"
        )
    return await user_from_token(credentials.credentials, session)


# -------------------------------------------------------------- authorisation


def require(*permissions: Permission):
    """Build a dependency that demands every listed permission.

    Used as `user: CurrentUser = Depends(require(Permission.AE_READ))`. The user
    object comes back, so an endpoint gets authentication, authorisation and the
    caller's identity from one line.
    """

    async def dependency(
        user: CurrentUser = Depends(get_current_user),
    ) -> CurrentUser:
        missing = [p for p in permissions if not user.can(p)]
        if missing:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=(
                    f"{user.role_label} cannot do this. "
                    f"Missing permission: {', '.join(p.value for p in missing)}"
                ),
            )
        return user

    return dependency


def scoped(statement, column, user: CurrentUser):
    """Narrow a query to the user's own site, if they are site-scoped.

    `column` is whichever site column that table has - `Subject.site_id`,
    `AdverseEvent.site_id`, `Site.id`. Returns the statement unchanged for the
    roles that see everything.
    """
    site_id = user.scope_site_id
    if site_id is None:
        return statement
    return statement.where(column == site_id)


def assert_site_visible(user: CurrentUser, site_id: int | None) -> None:
    """403 if this record belongs to a site the user may not see.

    Used on detail endpoints, where narrowing a query is not an option: the row
    was fetched by primary key, so the only choices are show it or refuse.
    Refusing loudly is right - a silent 404 would tell a curious user to keep
    guessing ids.
    """
    scope = user.scope_site_id
    if scope is None:
        return
    if site_id != scope:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=(
                f"this record belongs to another site. "
                f"{user.role_label} access is limited to site id {user.site_id}."
            ),
        )


def matrix() -> dict:
    """The whole access-control table, as data.

    Served by /api/rbac-matrix and rendered on screen, so what the demo claims
    about permissions is read from the same table that enforces them.
    """
    roles = [
        UserRole.ADMIN,
        UserRole.INSTITUTION_ADMIN,
        UserRole.PRINCIPAL_INVESTIGATOR,
        UserRole.COORDINATOR,
        UserRole.PATIENT,
        UserRole.SPONSOR,
        UserRole.ETHICS_COMMITTEE,
        UserRole.REGULATOR,
    ]
    return {
        "permissions": [
            {"key": p.value, "label": PERMISSION_LABELS.get(p.value, p.value)}
            for p in Permission
        ],
        "roles": [
            {
                "key": role.value,
                "label": ROLE_LABELS[role.value],
                "site_scoped": role.value in SITE_SCOPED_ROLES,
                "scope": (
                    "own site only"
                    if role.value in SITE_SCOPED_ROLES
                    else "all sites"
                ),
                "granted": sorted(p.value for p in ROLE_PERMISSIONS[role.value]),
            }
            for role in roles
        ],
        "note": (
            "Site-scoped roles see only their own hospital's rows; requesting "
            "another site's record returns 403, not an empty result."
        ),
    }
