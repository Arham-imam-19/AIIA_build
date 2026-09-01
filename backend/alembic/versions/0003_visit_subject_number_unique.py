"""Prevent duplicate Visit numbers for one Subject.

Revision ID: 0003
Revises: 0002
"""

from collections.abc import Sequence

from alembic import op

revision: str = "0003"
down_revision: str | None = "0002"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    with op.batch_alter_table("visits") as batch_op:
        batch_op.create_unique_constraint(
            "uq_visits_subject_id_visit_number",
            ["subject_id", "visit_number"],
        )


def downgrade() -> None:
    with op.batch_alter_table("visits") as batch_op:
        batch_op.drop_constraint(
            "uq_visits_subject_id_visit_number",
            type_="unique",
        )
