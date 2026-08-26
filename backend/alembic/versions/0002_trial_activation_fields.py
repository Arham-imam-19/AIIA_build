"""Add ethics approval validity and trial activation fields.

Revision ID: 0002
Revises: 0001
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0002"
down_revision: str | None = "0001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    with op.batch_alter_table("trials") as batch_op:
        batch_op.add_column(
            sa.Column("ethics_approval_status", sa.String(length=30), nullable=True)
        )
        batch_op.add_column(
            sa.Column("ethics_approval_valid_until", sa.Date(), nullable=True)
        )
        batch_op.add_column(sa.Column("activated_at", sa.DateTime(), nullable=True))
        batch_op.add_column(
            sa.Column("activated_by_user_id", sa.Integer(), nullable=True)
        )
        batch_op.create_foreign_key(
            "fk_trials_activated_by_user_id_users",
            "users",
            ["activated_by_user_id"],
            ["id"],
        )
        batch_op.create_index(
            "ix_trials_activated_by_user_id", ["activated_by_user_id"], unique=False
        )


def downgrade() -> None:
    with op.batch_alter_table("trials") as batch_op:
        batch_op.drop_index("ix_trials_activated_by_user_id")
        batch_op.drop_constraint(
            "fk_trials_activated_by_user_id_users", type_="foreignkey"
        )
        batch_op.drop_column("activated_by_user_id")
        batch_op.drop_column("activated_at")
        batch_op.drop_column("ethics_approval_valid_until")
        batch_op.drop_column("ethics_approval_status")
