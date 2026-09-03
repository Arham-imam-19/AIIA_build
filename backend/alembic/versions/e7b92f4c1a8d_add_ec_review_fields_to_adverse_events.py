"""Add IEC review fields to adverse_events

Revision ID: e7b92f4c1a8d
Revises: 04c5b4bf542d
Create Date: 2026-09-04 01:05:00.000000
"""

from collections.abc import Sequence
import sqlalchemy as sa
import sqlmodel
from alembic import op

revision: str = 'e7b92f4c1a8d'
down_revision: str | None = '04c5b4bf542d'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column('adverse_events', sa.Column('ec_decision', sqlmodel.sql.sqltypes.AutoString(length=40), nullable=True))
    op.add_column('adverse_events', sa.Column('ec_decision_date', sa.Date(), nullable=True))
    op.add_column('adverse_events', sa.Column('ec_decision_notes', sqlmodel.sql.sqltypes.AutoString(length=2000), nullable=True))
    op.add_column('adverse_events', sa.Column('ec_reviewed_by_user_id', sa.Integer(), nullable=True))
    try:
        op.create_index(op.f('ix_adverse_events_ec_decision'), 'adverse_events', ['ec_decision'], unique=False)
        op.create_index(op.f('ix_adverse_events_ec_reviewed_by_user_id'), 'adverse_events', ['ec_reviewed_by_user_id'], unique=False)
        op.create_foreign_key('adverse_events_ec_reviewed_by_user_id_fkey', 'adverse_events', 'users', ['ec_reviewed_by_user_id'], ['id'])
    except Exception:
        pass


def downgrade() -> None:
    try:
        op.drop_constraint('adverse_events_ec_reviewed_by_user_id_fkey', 'adverse_events', type_='foreignkey')
        op.drop_index(op.f('ix_adverse_events_ec_reviewed_by_user_id'), table_name='adverse_events')
        op.drop_index(op.f('ix_adverse_events_ec_decision'), table_name='adverse_events')
    except Exception:
        pass
    op.drop_column('adverse_events', 'ec_reviewed_by_user_id')
    op.drop_column('adverse_events', 'ec_decision_notes')
    op.drop_column('adverse_events', 'ec_decision_date')
    op.drop_column('adverse_events', 'ec_decision')
