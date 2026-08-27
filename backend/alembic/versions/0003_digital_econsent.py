"""Digital e-Consent records under NDCT Rules 2019 and 21 CFR Part 11.

Revision ID: 0003
Revises: 0002
Create Date: Digital e-Consent

Adds the `econsents` table for participant electronic informed consent verification,
bilingual information sheet metadata, ABHA ID linkage, digital signature canvas drawings,
and SHA-256 cryptographic digests.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0003"
down_revision: str | None = "0002"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "econsents",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("trial_id", sa.Integer(), sa.ForeignKey("trials.id"), nullable=False),
        sa.Column("site_id", sa.Integer(), sa.ForeignKey("sites.id"), nullable=False),
        sa.Column("subject_id", sa.Integer(), sa.ForeignKey("subjects.id"), nullable=False),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("language", sa.String(length=10), nullable=False),
        sa.Column("abha_id", sa.String(length=50), nullable=True),
        sa.Column("signer_name", sa.String(length=200), nullable=False),
        sa.Column("signature_data_url", sa.Text(), nullable=False),
        sa.Column("sha256_hash", sa.String(length=64), nullable=False),
        sa.Column("status", sa.String(length=30), nullable=False),
        sa.Column("signed_at", sa.DateTime(), nullable=False),
        sa.Column("ip_address", sa.String(length=100), nullable=True),
        sa.Column("user_agent", sa.String(length=300), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("subject_id", name="uq_econsents_subject_id"),
    )
    op.create_index("ix_econsents_trial_id", "econsents", ["trial_id"])
    op.create_index("ix_econsents_site_id", "econsents", ["site_id"])
    op.create_index("ix_econsents_subject_id", "econsents", ["subject_id"])
    op.create_index("ix_econsents_user_id", "econsents", ["user_id"])
    op.create_index("ix_econsents_sha256_hash", "econsents", ["sha256_hash"])
    op.create_index("ix_econsents_status", "econsents", ["status"])


def downgrade() -> None:
    op.drop_index("ix_econsents_status", table_name="econsents")
    op.drop_index("ix_econsents_sha256_hash", table_name="econsents")
    op.drop_index("ix_econsents_user_id", table_name="econsents")
    op.drop_index("ix_econsents_subject_id", table_name="econsents")
    op.drop_index("ix_econsents_site_id", table_name="econsents")
    op.drop_index("ix_econsents_trial_id", table_name="econsents")
    op.drop_table("econsents")
