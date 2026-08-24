"""phase7 bonus features

Revision ID: 0002_phase7_bonus_features
Revises: 0001_initial_schema
Create Date: 2026-08-23 06:10:00.000000

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = '0002_phase7_bonus_features'
down_revision: Union[str, None] = '0001_initial_schema'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. Add role column to users table
    op.add_column('users', sa.Column('role', sa.String(length=50), server_default='MEMBER', nullable=False))
    op.create_check_constraint('chk_user_role', 'users', "role IN ('OWNER', 'ADMIN', 'MEMBER', 'VIEWER')")

    # 2. Create job_dependencies table
    op.create_table(
        'job_dependencies',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('job_id', sa.UUID(), nullable=False),
        sa.Column('depends_on_job_id', sa.UUID(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['job_id'], ['jobs.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['depends_on_job_id'], ['jobs.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('job_id', 'depends_on_job_id', name='uq_job_dependency'),
        sa.CheckConstraint('job_id != depends_on_job_id', name='chk_self_dependency')
    )
    op.create_index('idx_job_dependencies_job_id', 'job_dependencies', ['job_id'])
    op.create_index('idx_job_dependencies_depends_on', 'job_dependencies', ['depends_on_job_id'])


def downgrade() -> None:
    op.drop_index('idx_job_dependencies_depends_on', table_name='job_dependencies')
    op.drop_index('idx_job_dependencies_job_id', table_name='job_dependencies')
    op.drop_table('job_dependencies')
    op.drop_constraint('chk_user_role', 'users', type_='check')
    op.drop_column('users', 'role')
