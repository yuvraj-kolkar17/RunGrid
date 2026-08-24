import pytest
import asyncio
import uuid
from datetime import datetime, timezone, timedelta
from typing import Generator
from sqlalchemy import text
from sqlalchemy.orm import Session

from backend.app.main import app
from backend.app.core.database import SessionLocal
from backend.app.core.config import settings
from backend.app.models import RetryPolicy, Job, Worker, Queue, Project, DeadLetterJob, User, Organization
from backend.app.services.scheduler import process_delayed_jobs
from backend.app.services.reaper import reap_stale_workers_and_jobs
from worker.worker import WorkerProcess
from worker.config import settings as worker_settings

@pytest.fixture(scope="function")
def db() -> Generator[Session, None, None]:
    """Provides a clean database transaction for each integration test."""
    session = SessionLocal()
    try:
        session.execute(text(
            "TRUNCATE TABLE organizations, users, projects, queues, retry_policies, jobs, job_executions, workers, worker_heartbeats, job_logs, scheduled_jobs, dead_letter_jobs, job_dependencies CASCADE;"
        ))
        session.commit()
        yield session
    finally:
        session.rollback()
        session.close()

def setup_test_entities(db: Session):
    """Utility to create org, user, project, queue, and default retry policy."""
    now = datetime.now(timezone.utc)
    org = Organization(id=uuid.uuid4(), name="Integration Org", created_at=now, updated_at=now)
    db.add(org)
    db.flush()
    
    user = User(
        id=uuid.uuid4(),
        organization_id=org.id,
        email="worker_e2e@example.com",
        password_hash="password",
        created_at=now,
        updated_at=now
    )
    db.add(user)
    
    project = Project(
        id=uuid.uuid4(),
        organization_id=org.id,
        name="Integration Project",
        created_at=now,
        updated_at=now
    )
    db.add(project)
    db.flush()
    
    policy = RetryPolicy(
        id=uuid.uuid4(),
        name="Default Policy",
        strategy="linear",
        base_delay=2,
        max_retries=2,
        created_at=now
    )
    db.add(policy)
    db.flush()
    
    queue = Queue(
        id=uuid.uuid4(),
        project_id=project.id,
        name="integration-queue",
        concurrency_limit=3,
        created_at=now,
        updated_at=now
    )
    db.add(queue)
    db.commit()
    return org, user, project, queue, policy

@pytest.mark.asyncio
async def test_e2e_success_path(db: Session):
    _, _, _, queue, _ = setup_test_entities(db)
    
    # 1. Submit immediate job
    now = datetime.now(timezone.utc)
    job = Job(
        id=uuid.uuid4(),
        queue_id=queue.id,
        task_type="demo.success",
        payload={"data": "Integration test data!"},
        status="QUEUED",
        priority=10,
        max_retries=2,
        attempt=0,
        available_at=now,
        created_at=now,
        updated_at=now
    )
    db.add(job)
    db.commit()
    
    # 2. Run worker process routing requests to backend app
    worker = WorkerProcess(app=app)
    worker_task = asyncio.create_task(worker.run())
    
    # Wait for job to transition to COMPLETED in database
    for _ in range(30):
        await asyncio.sleep(0.1)
        db.expire_all()
        db_job = db.query(Job).filter(Job.id == job.id).first()
        if db_job and db_job.status == "COMPLETED":
            break
            
    assert db_job is not None
    assert db_job.status == "COMPLETED"
    assert db_job.result is not None
    assert db_job.result["result"] == {"status": "success", "data": "Integration test data!"}
    
    await worker.shutdown()
    await worker_task

@pytest.mark.asyncio
async def test_e2e_successful_retry_backoff(db: Session):
    _, _, _, queue, policy = setup_test_entities(db)
    
    # 1. Submit retry-eligible job
    now = datetime.now(timezone.utc)
    zero_policy = RetryPolicy(
        id=uuid.uuid4(),
        name="Zero Delay Retry Policy",
        strategy="fixed",
        base_delay=0,
        max_retries=2,
        created_at=now
    )
    db.add(zero_policy)
    db.flush()

    job = Job(
        id=uuid.uuid4(),
        queue_id=queue.id,
        retry_policy_id=zero_policy.id,
        task_type="demo.retry",
        payload={"fail_until_attempt": 2},
        status="QUEUED",
        priority=10,
        max_retries=2,
        attempt=0,
        available_at=now,
        created_at=now,
        updated_at=now
    )
    db.add(job)
    db.commit()
    
    worker = WorkerProcess(app=app)
    worker_task = asyncio.create_task(worker.run())
    
    # Wait for job to fail first time and transition to RETRY_WAITING
    for _ in range(30):
        await asyncio.sleep(0.1)
        db.expire_all()
        db_job = db.query(Job).filter(Job.id == job.id).first()
        if db_job and db_job.status == "RETRY_WAITING":
            break
            
    assert db_job is not None
    assert db_job.status == "RETRY_WAITING"
    assert db_job.attempt == 1
    
    # Pause polling temporarily by cancelling the polling task (simulate wait)
    assert worker.polling_task is not None
    worker.polling_task.cancel()
    
    # Run scheduler to transition RETRY_WAITING to QUEUED (available_at <= NOW naturally)
    process_delayed_jobs(db)
    db.commit()
    
    # Resume worker polling
    worker.polling_task = asyncio.create_task(worker.polling_loop())
    
    # Wait for job to succeed on attempt 2
    for _ in range(30):
        await asyncio.sleep(0.1)
        db.expire_all()
        db_job = db.query(Job).filter(Job.id == job.id).first()
        if db_job and db_job.status == "COMPLETED":
            break
            
    assert db_job is not None
    assert db_job.status == "COMPLETED"
    assert db_job.attempt == 2
    
    await worker.shutdown()
    await worker_task

@pytest.mark.asyncio
async def test_e2e_dlq_permanent_failure(db: Session):
    _, _, _, queue, policy = setup_test_entities(db)
    
    # Submit job with max_retries = 1
    now = datetime.now(timezone.utc)
    job = Job(
        id=uuid.uuid4(),
        queue_id=queue.id,
        retry_policy_id=policy.id,
        task_type="demo.failure",
        payload={"error_message": "DLQ test crash"},
        status="QUEUED",
        priority=10,
        max_retries=1,
        attempt=0,
        available_at=now,
        created_at=now,
        updated_at=now
    )
    db.add(job)
    db.commit()
    
    worker = WorkerProcess(app=app)
    worker_task = asyncio.create_task(worker.run())
    
    # Wait for job to transition to DEAD_LETTER
    for _ in range(30):
        await asyncio.sleep(0.1)
        db.expire_all()
        db_job = db.query(Job).filter(Job.id == job.id).first()
        if db_job and db_job.status == "DEAD_LETTER":
            break
            
    assert db_job is not None
    assert db_job.status == "DEAD_LETTER"
    assert db_job.attempt == 1
    
    # Check DeadLetterJob table
    dlq_entry = db.query(DeadLetterJob).filter(DeadLetterJob.job_id == job.id).first()
    assert dlq_entry is not None
    assert "DLQ test crash" in dlq_entry.failure_reason
    
    await worker.shutdown()
    await worker_task

@pytest.mark.asyncio
async def test_e2e_worker_recovery_reaper(db: Session):
    _, _, _, queue, _ = setup_test_entities(db)
    
    # 1. Register Worker A manually in db
    now = datetime.now(timezone.utc)
    worker_a = Worker(id=uuid.uuid4(), hostname="worker-a", ip_address="127.0.0.1", status="ACTIVE", last_heartbeat_at=now, created_at=now, updated_at=now)
    db.add(worker_a)
    db.flush()
    
    zero_policy = RetryPolicy(
        id=uuid.uuid4(),
        name="Zero Delay Reaper Policy",
        strategy="fixed",
        base_delay=0,
        max_retries=3,
        created_at=now
    )
    db.add(zero_policy)
    db.flush()
    
    # 2. Claim job under Worker A and set status = RUNNING
    job = Job(
        id=uuid.uuid4(),
        queue_id=queue.id,
        retry_policy_id=zero_policy.id,
        task_type="demo.success",
        status="RUNNING",
        attempt=1,
        claimed_by_worker_id=worker_a.id,
        claimed_at=now,
        started_at=now,
        available_at=now,
        lease_expires_at=now - timedelta(seconds=1),  # Expired lease!
        created_at=now,
        updated_at=now
    )
    db.add(job)
    db.commit()
    
    # 3. Run Reaper service to recover the zombie job
    _, reaped_count = reap_stale_workers_and_jobs(db, heartbeat_timeout_seconds=0)
    db.commit()
    assert reaped_count == 1
    
    # Reload and assert job status has been set back to RETRY_WAITING
    db.refresh(job)
    assert job.status == "RETRY_WAITING"
    
    # Process delayed jobs via actual service to transition RETRY_WAITING to QUEUED
    process_delayed_jobs(db)
    db.commit()
    
    db.refresh(job)
    assert job.status == "QUEUED"
    assert job.claimed_by_worker_id is None
    
    # 4. Start Worker B to process the recovered job
    worker_b = WorkerProcess(app=app)
    worker_task = asyncio.create_task(worker_b.run())
    
    for _ in range(30):
        await asyncio.sleep(0.1)
        db.expire_all()
        db_job = db.query(Job).filter(Job.id == job.id).first()
        if db_job and db_job.status == "COMPLETED":
            break
            
    assert db_job is not None
    assert db_job.status == "COMPLETED"
    
    await worker_b.shutdown()
    await worker_task

@pytest.mark.asyncio
async def test_e2e_worker_ownership_protection(db: Session):
    _, _, _, queue, _ = setup_test_entities(db)
    
    now = datetime.now(timezone.utc)
    worker_a_id = uuid.uuid4()
    worker_b_id = uuid.uuid4()
    
    # Manually register workers
    w_a = Worker(id=worker_a_id, hostname="worker-a", ip_address="127.0.0.1", status="ACTIVE", last_heartbeat_at=now, created_at=now, updated_at=now)
    w_b = Worker(id=worker_b_id, hostname="worker-b", ip_address="127.0.0.1", status="ACTIVE", last_heartbeat_at=now, created_at=now, updated_at=now)
    db.add(w_a)
    db.add(w_b)
    
    # Job claimed by Worker A
    job = Job(
        id=uuid.uuid4(),
        queue_id=queue.id,
        task_type="demo.success",
        status="RUNNING",
        attempt=1,
        claimed_by_worker_id=worker_a_id,
        claimed_at=now,
        started_at=now,
        lease_expires_at=now + timedelta(seconds=60),
        created_at=now,
        updated_at=now
    )
    db.add(job)
    db.commit()
    
    # Initialize worker clients
    client_a = WorkerProcess(app=app).client
    client_b = WorkerProcess(app=app).client
    
    # Worker B attempts to complete Worker A's job -> rejected with WORKER_MISMATCH HTTP 400
    import httpx
    with pytest.raises(httpx.HTTPStatusError) as exc_info:
        await client_b.complete_job(str(job.id), str(worker_b_id), {"status": "stolen"})
    assert exc_info.value.response.status_code == 400
    assert exc_info.value.response.json()["error"]["code"] == "WORKER_MISMATCH"
    
    # Worker A completes -> accepted
    res = await client_a.complete_job(str(job.id), str(worker_a_id), {"status": "ok"})
    assert res["status"] == "COMPLETED"
    
    # Verify DB state
    db.expire_all()
    db_job = db.query(Job).filter(Job.id == job.id).first()
    assert db_job is not None
    assert db_job.status == "COMPLETED"
    
    await client_a.close()
    await client_b.close()

@pytest.mark.asyncio
async def test_e2e_graceful_shutdown_draining(db: Session):
    _, _, _, queue, _ = setup_test_entities(db)
    
    # Submit slow job (1.0 second duration)
    now = datetime.now(timezone.utc)
    job = Job(
        id=uuid.uuid4(),
        queue_id=queue.id,
        task_type="demo.slow",
        payload={"duration": 0.6},
        status="QUEUED",
        priority=10,
        max_retries=1,
        attempt=0,
        available_at=now,
        created_at=now,
        updated_at=now
    )
    db.add(job)
    db.commit()
    
    worker = WorkerProcess(app=app)
    worker_task = asyncio.create_task(worker.run())
    
    # Wait for job to start running
    for _ in range(30):
        await asyncio.sleep(0.1)
        db.expire_all()
        db_job = db.query(Job).filter(Job.id == job.id).first()
        if db_job and db_job.status == "RUNNING":
            break
            
    assert db_job is not None
    assert db_job.status == "RUNNING"
    
    # Call shutdown with sufficient timeout (1.0s) -> should allow the active task to complete
    # Patch shutdown timeout settings to 1.0s
    from unittest.mock import patch
    with patch.object(worker_settings, 'SHUTDOWN_TIMEOUT', 1.0):
        await worker.shutdown()
        
    await worker_task
    
    # Assert job completed successfully during drain period
    db.expire_all()
    db_job = db.query(Job).filter(Job.id == job.id).first()
    assert db_job is not None
    assert db_job.status == "COMPLETED"
