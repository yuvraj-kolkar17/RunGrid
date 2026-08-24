"""batch submissions table and job batch_id FK

Revision ID: 0003_batch_submissions
Revises: 0002_phase7_bonus_features
Create Date: 2026-08-23 14:10:00.000000

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

revision: str = '0003_batch_submissions'
down_revision: Union[str, None] = '0002_phase7_bonus_features'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. Create batch_submissions table
    op.create_table(
        'batch_submissions',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('organization_id', sa.UUID(), nullable=False),
        sa.Column('name', sa.String(length=255), nullable=True),
        sa.Column('status', sa.String(length=50), server_default='PROCESSING', nullable=False),
        sa.Column('total_jobs', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['organization_id'], ['organizations.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('idx_batch_submissions_org_id', 'batch_submissions', ['organization_id'])

    # 2. Add batch_id to jobs table
    op.add_column('jobs', sa.Column('batch_id', sa.UUID(), nullable=True))
    op.create_foreign_key('fk_jobs_batch_id', 'jobs', 'batch_submissions', ['batch_id'], ['id'], ondelete='SET NULL')
    op.create_index('idx_jobs_batch_id', 'jobs', ['batch_id'])


def downgrade() -> None:
    op.drop_index('idx_jobs_batch_id', table_name='jobs')
    op.drop_constraint('fk_jobs_batch_id', 'jobs', type_='foreignkey')
    op.drop_column('jobs', 'batch_id')
    op.drop_index('idx_batch_submissions_org_id', table_name='batch_submissions')
    op.drop_table('batch_submissions')
