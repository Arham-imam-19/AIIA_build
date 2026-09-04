"""Add dsmb_decisions table

Revision ID: f8a91b2c3d4e
Revises: e7b92f4c1a8d
Create Date: 2026-09-05 03:00:00.000000
"""

from collections.abc import Sequence
import sqlalchemy as sa
import sqlmodel
from alembic import op

revision: str = 'f8a91b2c3d4e'
down_revision: str | None = 'e7b92f4c1a8d'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        'dsmb_decisions',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('trial_id', sa.Integer(), nullable=False),
        sa.Column('site_id', sa.Integer(), nullable=True),
        sa.Column('decision', sqlmodel.sql.sqltypes.AutoString(length=40), nullable=False),
        sa.Column('directive_title', sqlmodel.sql.sqltypes.AutoString(length=255), nullable=True),
        sa.Column('notes', sqlmodel.sql.sqltypes.AutoString(length=4000), nullable=False),
        sa.Column('recommended_action', sqlmodel.sql.sqltypes.AutoString(length=500), nullable=True),
        sa.Column('created_by_user_id', sa.Integer(), nullable=False),
        sa.Column('created_by_name', sqlmodel.sql.sqltypes.AutoString(length=150), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('acknowledged_at', sa.DateTime(), nullable=True),
        sa.Column('acknowledged_by_user_id', sa.Integer(), nullable=True),
        sa.Column('acknowledged_by_name', sqlmodel.sql.sqltypes.AutoString(length=150), nullable=True),
        sa.ForeignKeyConstraint(['created_by_user_id'], ['users.id']),
        sa.ForeignKeyConstraint(['acknowledged_by_user_id'], ['users.id']),
        sa.ForeignKeyConstraint(['site_id'], ['sites.id']),
        sa.ForeignKeyConstraint(['trial_id'], ['trials.id']),
        sa.PrimaryKeyConstraint('id')
    )
    try:
        op.create_index(op.f('ix_dsmb_decisions_created_at'), 'dsmb_decisions', ['created_at'], unique=False)
        op.create_index(op.f('ix_dsmb_decisions_created_by_user_id'), 'dsmb_decisions', ['created_by_user_id'], unique=False)
        op.create_index(op.f('ix_dsmb_decisions_decision'), 'dsmb_decisions', ['decision'], unique=False)
        op.create_index(op.f('ix_dsmb_decisions_site_id'), 'dsmb_decisions', ['site_id'], unique=False)
        op.create_index(op.f('ix_dsmb_decisions_trial_id'), 'dsmb_decisions', ['trial_id'], unique=False)
    except Exception:
        pass


def downgrade() -> None:
    try:
        op.drop_index(op.f('ix_dsmb_decisions_trial_id'), table_name='dsmb_decisions')
        op.drop_index(op.f('ix_dsmb_decisions_site_id'), table_name='dsmb_decisions')
        op.drop_index(op.f('ix_dsmb_decisions_decision'), table_name='dsmb_decisions')
        op.drop_index(op.f('ix_dsmb_decisions_created_by_user_id'), table_name='dsmb_decisions')
        op.drop_index(op.f('ix_dsmb_decisions_created_at'), table_name='dsmb_decisions')
    except Exception:
        pass
    op.drop_table('dsmb_decisions')
