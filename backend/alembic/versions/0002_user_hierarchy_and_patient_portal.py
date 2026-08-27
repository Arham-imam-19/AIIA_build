"""User hierarchy expansion and patient portal requests.

Revision ID: 0002
Revises: 0001
Create Date: User Hierarchy

Extends the data model to support the full hierarchy:
Primary Admin -> Institution (Site) -> Institution Admins -> Researchers -> Patients.

Adds:
1. `users.subject_id` (link patient user to clinical subject)
2. `subjects.assigned_researcher_id` and `subjects.user_id`
3. `patient_requests` table for patient inquiries and communications to Institution Admins.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0002"
down_revision: str | None = "0001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # ----------------------------------------------------------- user columns
    with op.batch_alter_table("users") as batch_op:
        batch_op.add_column(
            sa.Column("subject_id", sa.Integer(), nullable=True)
        )
        batch_op.create_foreign_key(
            "fk_users_subject_id",
            "subjects",
            ["subject_id"],
            ["id"],
        )
        batch_op.create_index("ix_users_subject_id", ["subject_id"])

    # -------------------------------------------------------- subject columns
    with op.batch_alter_table("subjects") as batch_op:
        batch_op.add_column(
            sa.Column(
                "assigned_researcher_id",
                sa.Integer(),
                nullable=True,
            )
        )
        batch_op.create_foreign_key(
            "fk_subjects_assigned_researcher_id",
            "users",
            ["assigned_researcher_id"],
            ["id"],
        )
        batch_op.create_index(
            "ix_subjects_assigned_researcher_id", ["assigned_researcher_id"]
        )

        batch_op.add_column(
            sa.Column("user_id", sa.Integer(), nullable=True)
        )
        batch_op.create_foreign_key(
            "fk_subjects_user_id",
            "users",
            ["user_id"],
            ["id"],
        )
        batch_op.create_index("ix_subjects_user_id", ["user_id"])

    # ------------------------------------------------------- patient_requests
    op.create_table(
        "patient_requests",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("site_id", sa.Integer(), sa.ForeignKey("sites.id"), nullable=False),
        sa.Column("trial_id", sa.Integer(), sa.ForeignKey("trials.id"), nullable=True),
        sa.Column(
            "patient_user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False
        ),
        sa.Column(
            "subject_id", sa.Integer(), sa.ForeignKey("subjects.id"), nullable=True
        ),
        sa.Column("category", sa.String(length=40), nullable=False),
        sa.Column("subject_line", sa.String(length=200), nullable=False),
        sa.Column("message", sa.String(length=3000), nullable=False),
        sa.Column("status", sa.String(length=30), nullable=False),
        sa.Column(
            "assigned_admin_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=True
        ),
        sa.Column("admin_response", sa.String(length=3000), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.Column("resolved_at", sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_patient_requests_site_id", "patient_requests", ["site_id"])
    op.create_index("ix_patient_requests_trial_id", "patient_requests", ["trial_id"])
    op.create_index(
        "ix_patient_requests_patient_user_id", "patient_requests", ["patient_user_id"]
    )
    op.create_index(
        "ix_patient_requests_subject_id", "patient_requests", ["subject_id"]
    )
    op.create_index("ix_patient_requests_category", "patient_requests", ["category"])
    op.create_index("ix_patient_requests_status", "patient_requests", ["status"])
    op.create_index(
        "ix_patient_requests_assigned_admin_id",
        "patient_requests",
        ["assigned_admin_id"],
    )


def downgrade() -> None:
    op.drop_index("ix_patient_requests_assigned_admin_id", table_name="patient_requests")
    op.drop_index("ix_patient_requests_status", table_name="patient_requests")
    op.drop_index("ix_patient_requests_category", table_name="patient_requests")
    op.drop_index("ix_patient_requests_subject_id", table_name="patient_requests")
    op.drop_index("ix_patient_requests_patient_user_id", table_name="patient_requests")
    op.drop_index("ix_patient_requests_trial_id", table_name="patient_requests")
    op.drop_index("ix_patient_requests_site_id", table_name="patient_requests")
    op.drop_table("patient_requests")

    with op.batch_alter_table("subjects") as batch_op:
        batch_op.drop_constraint("fk_subjects_user_id", type_="foreignkey")
        batch_op.drop_index("ix_subjects_user_id")
        batch_op.drop_column("user_id")
        batch_op.drop_constraint("fk_subjects_assigned_researcher_id", type_="foreignkey")
        batch_op.drop_index("ix_subjects_assigned_researcher_id")
        batch_op.drop_column("assigned_researcher_id")

    with op.batch_alter_table("users") as batch_op:
        batch_op.drop_constraint("fk_users_subject_id", type_="foreignkey")
        batch_op.drop_index("ix_users_subject_id")
        batch_op.drop_column("subject_id")
