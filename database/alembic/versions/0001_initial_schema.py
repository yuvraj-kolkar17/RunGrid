"""initial schema

Revision ID: 0001_initial_schema
Revises: 
Create Date: 2026-08-22 15:30:00.000000

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = '0001_initial_schema'
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. Organizations
    op.create_table(
        'organizations',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('name', sa.String(length=255), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.PrimaryKeyConstraint('id')
    )

    # 2. Users
    op.create_table(
        'users',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('email', sa.String(length=255), nullable=False),
        sa.Column('password_hash', sa.String(length=255), nullable=False),
        sa.Column('organization_id', sa.UUID(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['organization_id'], ['organizations.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('email')
    )

    # 3. Projects
    op.create_table(
        'projects',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('name', sa.String(length=255), nullable=False),
        sa.Column('organization_id', sa.UUID(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['organization_id'], ['organizations.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )

    # 4. Queues
    op.create_table(
        'queues',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('project_id', sa.UUID(), nullable=False),
        sa.Column('name', sa.String(length=255), nullable=False),
        sa.Column('priority', sa.Integer(), server_default='0', nullable=False),
        sa.Column('concurrency_limit', sa.Integer(), nullable=True),
        sa.Column('is_paused', sa.Boolean(), server_default='false', nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.CheckConstraint('concurrency_limit > 0', name='chk_queue_positive_concurrency_limit'),
        sa.ForeignKeyConstraint(['project_id'], ['projects.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('project_id', 'name', name='uq_project_queue_name')
    )

    # 5. Retry Policies
    op.create_table(
        'retry_policies',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('name', sa.String(length=255), nullable=False),
        sa.Column('strategy', sa.String(length=50), nullable=False),
        sa.Column('base_delay', sa.Integer(), nullable=False),
        sa.Column('max_retries', sa.Integer(), server_default='3', nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.CheckConstraint("strategy IN ('fixed', 'linear', 'exponential')", name='chk_retry_policy_strategy'),
        sa.CheckConstraint('base_delay >= 0', name='chk_retry_policy_base_delay'),
        sa.CheckConstraint('max_retries >= 0', name='chk_retry_policy_max_retries'),
        sa.PrimaryKeyConstraint('id')
    )

    # 6. Workers
    op.create_table(
        'workers',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('hostname', sa.String(length=255), nullable=False),
        sa.Column('ip_address', sa.String(length=45), nullable=False),
        sa.Column('status', sa.String(length=50), server_default='ACTIVE', nullable=False),
        sa.Column('last_heartbeat_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.CheckConstraint("status IN ('ACTIVE', 'INACTIVE')", name='chk_worker_status'),
        sa.PrimaryKeyConstraint('id')
    )

    # 7. Worker Heartbeats
    op.create_table(
        'worker_heartbeats',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('worker_id', sa.UUID(), nullable=False),
        sa.Column('status_details', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['worker_id'], ['workers.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )

    # 8. Jobs
    op.create_table(
        'jobs',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('queue_id', sa.UUID(), nullable=False),
        sa.Column('retry_policy_id', sa.UUID(), nullable=True),
        sa.Column('status', sa.String(length=50), server_default='QUEUED', nullable=False),
        sa.Column('payload', postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column('result', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column('error', sa.Text(), nullable=True),
        sa.Column('priority', sa.Integer(), server_default='0', nullable=False),
        sa.Column('max_retries', sa.Integer(), server_default='3', nullable=False),
        sa.Column('attempt', sa.Integer(), server_default='0', nullable=False),
        sa.Column('scheduled_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('available_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('claimed_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('started_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('completed_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('failed_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('lease_expires_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('claimed_by_worker_id', sa.UUID(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.CheckConstraint("status IN ('SCHEDULED', 'QUEUED', 'CLAIMED', 'RUNNING', 'COMPLETED', 'FAILED', 'RETRY_WAITING', 'DEAD_LETTER')", name='chk_job_status'),
        sa.CheckConstraint('priority >= 0', name='chk_job_priority'),
        sa.CheckConstraint('max_retries >= 0', name='chk_job_max_retries'),
        sa.CheckConstraint('attempt >= 0', name='chk_job_attempt'),
        sa.ForeignKeyConstraint(['claimed_by_worker_id'], ['workers.id'], ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['queue_id'], ['queues.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['retry_policy_id'], ['retry_policies.id'], ondelete='SET NULL'),
        sa.PrimaryKeyConstraint('id')
    )

    # 9. Job Executions
    op.create_table(
        'job_executions',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('job_id', sa.UUID(), nullable=False),
        sa.Column('worker_id', sa.UUID(), nullable=True),
        sa.Column('status', sa.String(length=50), nullable=False),
        sa.Column('error', sa.Text(), nullable=True),
        sa.Column('attempt', sa.Integer(), nullable=False),
        sa.Column('started_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('finished_at', sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint('attempt >= 0', name='chk_job_execution_attempt'),
        sa.ForeignKeyConstraint(['job_id'], ['jobs.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['worker_id'], ['workers.id'], ondelete='SET NULL'),
        sa.PrimaryKeyConstraint('id')
    )

    # 10. Job Logs
    op.create_table(
        'job_logs',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('job_id', sa.UUID(), nullable=False),
        sa.Column('execution_id', sa.UUID(), nullable=True),
        sa.Column('log_level', sa.String(length=50), nullable=False),
        sa.Column('message', sa.Text(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['execution_id'], ['job_executions.id'], ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['job_id'], ['jobs.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )

    # 11. Scheduled Jobs
    op.create_table(
        'scheduled_jobs',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('project_id', sa.UUID(), nullable=False),
        sa.Column('queue_id', sa.UUID(), nullable=False),
        sa.Column('name', sa.String(length=255), nullable=False),
        sa.Column('cron_expression', sa.String(length=255), nullable=False),
        sa.Column('payload', postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column('is_active', sa.Boolean(), server_default='true', nullable=False),
        sa.Column('last_run_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('next_run_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['project_id'], ['projects.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['queue_id'], ['queues.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )

    # 12. Dead Letter Jobs
    op.create_table(
        'dead_letter_jobs',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('job_id', sa.UUID(), nullable=False),
        sa.Column('queue_id', sa.UUID(), nullable=False),
        sa.Column('original_payload', postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column('failure_reason', sa.Text(), nullable=False),
        sa.Column('moved_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['job_id'], ['jobs.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['queue_id'], ['queues.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('job_id')
    )

    # Indexes
    # idx_jobs_queued_claim: Partial index on jobs where status = 'QUEUED'
    # Ordered by: queue_id, priority DESC, available_at ASC, created_at ASC
    op.create_index(
        'idx_jobs_queued_claim',
        'jobs',
        ['queue_id', 'priority', 'available_at', 'created_at'],
        postgresql_where=sa.text("status = 'QUEUED'")
    )

    # idx_jobs_queue_status: Optimizes queue queries filtering by status
    op.create_index('idx_jobs_queue_status', 'jobs', ['queue_id', 'status'])

    # idx_jobs_worker_lease: Optimizes reaper checks for active/expired worker leases
    op.create_index('idx_jobs_worker_lease', 'jobs', ['claimed_by_worker_id', 'status', 'lease_expires_at'])

    # idx_workers_heartbeat: Optimizes worker heartbeat status checks for reaping
    op.create_index('idx_workers_heartbeat', 'workers', ['status', 'last_heartbeat_at'])

    # idx_scheduled_jobs_next_run: Optimizes cron execution queries
    op.create_index('idx_scheduled_jobs_next_run', 'scheduled_jobs', ['is_active', 'next_run_at'])

    # idx_job_executions_job: Optimizes execution history fetching for a job
    op.create_index('idx_job_executions_job', 'job_executions', ['job_id'])


def downgrade() -> None:
    op.drop_index('idx_job_executions_job', table_name='job_executions')
    op.drop_index('idx_scheduled_jobs_next_run', table_name='scheduled_jobs')
    op.drop_index('idx_workers_heartbeat', table_name='workers')
    op.drop_index('idx_jobs_worker_lease', table_name='jobs')
    op.drop_index('idx_jobs_queue_status', table_name='jobs')
    op.drop_index('idx_jobs_queued_claim', table_name='jobs')

    op.drop_table('dead_letter_jobs')
    op.drop_table('scheduled_jobs')
    op.drop_table('job_logs')
    op.drop_table('job_executions')
    op.drop_table('jobs')
    op.drop_table('worker_heartbeats')
    op.drop_table('workers')
    op.drop_table('retry_policies')
    op.drop_table('queues')
    op.drop_table('projects')
    op.drop_table('users')
    op.drop_table('organizations')
