import pytest
import uuid
from datetime import datetime, timezone, timedelta
from fastapi import status
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from backend.app.main import app
from backend.app.models import (
    Organization, User, Project, Queue, Job, Worker,
    ScheduledJob, JobExecution, JobLog, WorkerHeartbeat
)
from backend.app.core.security import create_access_token, get_password_hash
from backend.app.core.config import settings
from backend.app.services.scheduler import run_scheduler_cycle

from typing import Generator
from backend.app.core.database import SessionLocal

client = TestClient(app)

@pytest.fixture(scope="function")
def db() -> Generator[Session, None, None]:
    """Fixture to provide a clean database session rolled back after each test."""
    session = SessionLocal()
    try:
        yield session
    finally:
        session.rollback()
        session.close()

def create_test_auth(db: Session, email_prefix: str = "hardening"):
    now = datetime.now(timezone.utc)
    uid = uuid.uuid4().hex[:8]
    org = Organization(id=uuid.uuid4(), name=f"{email_prefix} Org {uid}", created_at=now, updated_at=now)
    db.add(org)
    db.flush()
    
    user = User(
        id=uuid.uuid4(),
        organization_id=org.id,
        email=f"{email_prefix}_{uid}@example.com",
        password_hash=get_password_hash("password123"),
        created_at=now,
        updated_at=now
    )
    db.add(user)
    db.commit()
    
    token = create_access_token({"sub": str(user.id), "email": user.email})
    headers = {"Authorization": f"Bearer {token}"}
    return org, user, headers

def test_health_and_readiness_endpoints():
    res_health = client.get("/health")
    assert res_health.status_code == 200
    assert res_health.json() == {"status": "healthy"}
    
    res_ready = client.get("/ready")
    assert res_ready.status_code == 200
    assert res_ready.json() == {"status": "ready"}

def test_metrics_endpoint(db: Session):
    _, _, headers = create_test_auth(db, "metrics")
    res = client.get("/api/v1/metrics", headers=headers)
    assert res.status_code == 200
    data = res.json()
    assert "jobs" in data
    assert "workers" in data
    assert "queues" in data
    assert "throughput" in data
    assert data["jobs"]["total"] >= 0

def test_recurring_jobs_cron_deduplication(db: Session):
    db.query(ScheduledJob).delete()
    db.query(Job).delete()
    db.commit()

    org, user, headers = create_test_auth(db, "cron")
    now = datetime.now(timezone.utc)
    
    proj = Project(id=uuid.uuid4(), organization_id=org.id, name="Cron Proj", created_at=now, updated_at=now)
    db.add(proj)
    db.flush()
    
    queue = Queue(id=uuid.uuid4(), project_id=proj.id, name="cron-queue", concurrency_limit=5, created_at=now, updated_at=now)
    db.add(queue)
    db.flush()
    
    past_due = now - timedelta(minutes=5)
    sched = ScheduledJob(
        id=uuid.uuid4(),
        project_id=proj.id,
        queue_id=queue.id,
        name="Cron Job Test",
        cron_expression="* * * * *",
        payload={"task_type": "demo.success", "msg": "cron test"},
        is_active=True,
        next_run_at=past_due,
        created_at=now,
        updated_at=now
    )
    db.add(sched)
    db.commit()
    
    # 1st Scheduler Cycle
    created_cnt_1 = run_scheduler_cycle(db)
    db.commit()
    assert created_cnt_1 == 1
    
    # 2nd Concurrent Scheduler Cycle (Immediate re-run should NOT create duplicates)
    created_cnt_2 = run_scheduler_cycle(db)
    db.commit()
    assert created_cnt_2 == 0
    
    # Verify exactly 1 job was created
    jobs = db.query(Job).filter(Job.queue_id == queue.id).all()
    assert len(jobs) == 1
    assert jobs[0].status == "QUEUED"

def test_queue_pause_resume_and_concurrency(db: Session):
    # Clear any leftover jobs from previous tests for clean polling isolation
    db.query(Job).delete()
    db.query(Queue).delete()
    db.commit()

    org, user, headers = create_test_auth(db, "pause")
    now = datetime.now(timezone.utc)
    
    proj = Project(id=uuid.uuid4(), organization_id=org.id, name="Pause Proj", created_at=now, updated_at=now)
    db.add(proj)
    db.flush()
    
    # Create Paused Queue
    queue = Queue(id=uuid.uuid4(), project_id=proj.id, name="paused-queue", concurrency_limit=5, is_paused=True, created_at=now, updated_at=now)
    db.add(queue)
    db.commit()
    
    # Submit job to paused queue
    job = Job(id=uuid.uuid4(), queue_id=queue.id, payload={"task_type": "demo.success"}, status="QUEUED", available_at=now, created_at=now, updated_at=now)
    db.add(job)
    db.commit()
    
    # Register Worker
    internal_headers = {"X-Internal-Key": settings.INTERNAL_API_KEY}
    reg_resp = client.post("/api/v1/internal/workers/register", json={"hostname": "pause-w1", "ip_address": "127.0.0.1"}, headers=internal_headers)
    assert reg_resp.status_code == 200
    worker_id = reg_resp.json()["id"]
    
    # Worker polls paused queue -> should return 200 OK with null (no jobs claimed)
    poll_resp = client.post(f"/api/v1/internal/workers/{worker_id}/poll", json={"queue_id": str(queue.id)}, headers=internal_headers)
    assert poll_resp.status_code == 200
    assert poll_resp.json() is None
    
    # Resume Queue via API
    resume_resp = client.patch(f"/api/v1/queues/{queue.id}/resume", headers=headers)
    assert resume_resp.status_code == 200
    assert resume_resp.json()["is_paused"] is False
    
    # Worker polls resumed queue -> should claim job (200 OK)
    poll_resp_2 = client.post(f"/api/v1/internal/workers/{worker_id}/poll", json={"queue_id": str(queue.id)}, headers=internal_headers)
    assert poll_resp_2.status_code == 200
    assert poll_resp_2.json()["id"] == str(job.id)

def test_priority_ordering(db: Session):
    # Clear any leftover jobs from previous tests for clean polling isolation
    db.query(Job).delete()
    db.query(Queue).delete()
    db.commit()

    org, user, headers = create_test_auth(db, "priority")
    now = datetime.now(timezone.utc)
    
    proj = Project(id=uuid.uuid4(), organization_id=org.id, name="Priority Proj", created_at=now, updated_at=now)
    db.add(proj)
    db.flush()
    
    queue = Queue(id=uuid.uuid4(), project_id=proj.id, name="prio-queue", concurrency_limit=5, created_at=now, updated_at=now)
    db.add(queue)
    db.commit()
    
    # Add Low Priority Job (priority = 5)
    low_job = Job(id=uuid.uuid4(), queue_id=queue.id, payload={"task_type": "demo.success"}, status="QUEUED", priority=5, available_at=now, created_at=now, updated_at=now)
    # Add High Priority Job (priority = 20)
    high_job = Job(id=uuid.uuid4(), queue_id=queue.id, payload={"task_type": "demo.success"}, status="QUEUED", priority=20, available_at=now, created_at=now, updated_at=now)
    db.add(low_job)
    db.add(high_job)
    db.commit()
    
    internal_headers = {"X-Internal-Key": settings.INTERNAL_API_KEY}
    reg_resp = client.post("/api/v1/internal/workers/register", json={"hostname": "prio-w1", "ip_address": "127.0.0.1"}, headers=internal_headers)
    worker_id = reg_resp.json()["id"]
    
    # First claim MUST return high priority job (priority 20)
    poll1 = client.post(f"/api/v1/internal/workers/{worker_id}/poll", json={"queue_id": str(queue.id)}, headers=internal_headers)
    assert poll1.status_code == 200
    assert poll1.json()["id"] == str(high_job.id)

def test_api_security_enforcement(db: Session):
    org1, user1, headers1 = create_test_auth(db, "sec1")
    org2, user2, headers2 = create_test_auth(db, "sec2")
    
    # 1. Unauthenticated public API rejected
    res_no_auth = client.get("/api/v1/projects")
    assert res_no_auth.status_code == 401
    
    # 2. Invalid JWT rejected
    res_bad_jwt = client.get("/api/v1/projects", headers={"Authorization": "Bearer invalidtoken123"})
    assert res_bad_jwt.status_code == 401
    
    # 3. Organization isolation
    proj_resp = client.post("/api/v1/projects", json={"name": "Org 1 Secret Proj"}, headers=headers1)
    assert proj_resp.status_code == 201
    proj_id = proj_resp.json()["id"]
    
    # User 2 attempts to fetch User 1's project -> 404 Not Found
    res_iso = client.get(f"/api/v1/projects/{proj_id}", headers=headers2)
    assert res_iso.status_code == 404
    
    # 4. Invalid internal worker key rejected
    res_bad_key = client.post("/api/v1/internal/workers/register", json={"hostname": "w", "ip_address": "127.0.0.1"}, headers={"X-Internal-Key": "wrongkey"})
    assert res_bad_key.status_code == 401

def test_pagination_and_filtering(db: Session):
    org, user, headers = create_test_auth(db, "page")
    now = datetime.now(timezone.utc)
    
    proj = Project(id=uuid.uuid4(), organization_id=org.id, name="Page Proj", created_at=now, updated_at=now)
    db.add(proj)
    db.flush()
    
    queue = Queue(id=uuid.uuid4(), project_id=proj.id, name="page-queue", concurrency_limit=5, created_at=now, updated_at=now)
    db.add(queue)
    db.commit()
    
    # Add 15 jobs
    for i in range(15):
        j = Job(
            id=uuid.uuid4(),
            queue_id=queue.id,
            payload={"task_type": "demo.success"},
            status="QUEUED" if i < 10 else "COMPLETED",
            priority=i,
            available_at=now,
            created_at=now,
            updated_at=now
        )
        db.add(j)
    db.commit()
    
    # Test Pagination (page=1, page_size=5)
    res_p1 = client.get("/api/v1/jobs?page=1&page_size=5", headers=headers)
    assert res_p1.status_code == 200
    data_p1 = res_p1.json()
    assert len(data_p1["items"]) == 5
    assert data_p1["total"] == 15
    assert data_p1["page"] == 1
    
    # Test Status Filtering (status=COMPLETED)
    res_filter = client.get("/api/v1/jobs?status=COMPLETED", headers=headers)
    assert res_filter.status_code == 200
    data_filter = res_filter.json()
    assert len(data_filter["items"]) == 5
    assert all(item["status"] == "COMPLETED" for item in data_filter["items"])

def test_observability_persistence(db: Session):
    org, user, headers = create_test_auth(db, "obs")
    now = datetime.now(timezone.utc)
    
    proj = Project(id=uuid.uuid4(), organization_id=org.id, name="Obs Proj", created_at=now, updated_at=now)
    db.add(proj)
    db.flush()
    
    queue = Queue(id=uuid.uuid4(), project_id=proj.id, name="obs-queue", concurrency_limit=5, created_at=now, updated_at=now)
    db.add(queue)
    db.flush()
    
    worker = Worker(id=uuid.uuid4(), hostname="obs-worker", ip_address="127.0.0.1", status="ACTIVE", last_heartbeat_at=now, created_at=now, updated_at=now)
    db.add(worker)
    db.flush()
    
    job = Job(id=uuid.uuid4(), queue_id=queue.id, payload={"task_type": "demo.success"}, status="COMPLETED", created_at=now, updated_at=now)
    db.add(job)
    db.flush()
    
    # 1. Job Execution
    exec_rec = JobExecution(
        id=uuid.uuid4(),
        job_id=job.id,
        worker_id=worker.id,
        attempt=1,
        status="COMPLETED",
        started_at=now,
        finished_at=now + timedelta(milliseconds=150)
    )
    db.add(exec_rec)
    
    # 2. Job Log
    job_log = JobLog(
        id=uuid.uuid4(),
        job_id=job.id,
        log_level="INFO",
        message="Job executed successfully",
        created_at=now
    )
    db.add(job_log)
    
    # 3. Worker Heartbeat
    hb = WorkerHeartbeat(
        id=uuid.uuid4(),
        worker_id=worker.id,
        status_details={"cpu_usage": 12.5, "memory_usage": 45.0, "active_jobs_count": 1},
        created_at=now
    )
    db.add(hb)
    db.commit()
    
    # Assert records exist and are correctly persisted
    assert db.query(JobExecution).filter(JobExecution.job_id == job.id).count() == 1
    assert db.query(JobLog).filter(JobLog.job_id == job.id).count() == 1
    assert db.query(WorkerHeartbeat).filter(WorkerHeartbeat.worker_id == worker.id).count() == 1
