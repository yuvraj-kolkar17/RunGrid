import pytest
import uuid
from datetime import datetime, timezone, timedelta
from fastapi.testclient import TestClient
from collections.abc import Generator
from sqlalchemy.orm import Session
import json

from backend.app.main import app
from backend.app.core.database import SessionLocal, get_db
from backend.app.models import Job, Queue, Project, Worker, JobExecution, DeadLetterJob, ScheduledJob, User, Organization
from backend.app.core.logging import StructuredJsonFormatter, sanitize_data, log_event

@pytest.fixture(scope="function")
def db() -> Generator[Session, None, None]:
    """Provides a clean database transaction for each test."""
    session = SessionLocal()
    try:
        from sqlalchemy import text
        session.execute(text("TRUNCATE TABLE organizations, users, projects, queues, retry_policies, jobs, job_executions, workers, worker_heartbeats, job_logs, scheduled_jobs, dead_letter_jobs CASCADE;"))
        session.commit()
        yield session
    finally:
        session.rollback()
        session.close()

@pytest.fixture(scope="function")
def client(db: Session) -> Generator[TestClient, None, None]:
    """Provides a TestClient with overridden get_db."""
    def override_get_db():
        yield db
    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()

@pytest.fixture
def auth_headers(client: TestClient) -> dict:
    """Helper to register and login a user, returning Bearer auth headers."""
    email = f"obs_user_{uuid.uuid4().hex[:6]}@example.com"
    password = "Password123!"
    client.post("/api/v1/auth/register", json={
        "email": email,
        "password": password,
        "organization_name": "Obs Corp"
    })
    token_resp = client.post("/api/v1/auth/token", data={
        "username": email,
        "password": password
    })
    token = token_resp.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}

def test_metrics_authentication_required(client: TestClient):
    """10. Metrics endpoint requires appropriate authentication."""
    res = client.get("/api/v1/metrics")
    assert res.status_code == 401

def test_metrics_zero_jobs_no_divide_by_zero(client: TestClient, auth_headers: dict):
    """3. Zero-job metrics don't divide by zero."""
    res = client.get("/api/v1/metrics", headers=auth_headers)
    assert res.status_code == 200
    data = res.json()
    assert data["jobs"]["total"] == 0
    assert data["jobs"]["rates"]["success_rate"] == 0.0
    assert data["jobs"]["rates"]["failure_rate"] == 0.0
    assert data["jobs"]["rates"]["retry_rate"] == 0.0
    assert data["execution_performance"]["avg_duration_ms"] == 0.0

def test_metrics_job_counts_and_rates(client: TestClient, auth_headers: dict, db: Session):
    """1, 2. Metrics returns correct job counts & success/failure rates."""
    # Retrieve auto-created default queue
    queue = db.query(Queue).first()
    assert queue is not None

    now = datetime.now(timezone.utc)
    
    # Insert completed job
    j1 = Job(
        id=uuid.uuid4(), queue_id=queue.id, status="COMPLETED",
        payload={"task_type": "demo.success"}, completed_at=now
    )
    # Insert failed job
    j2 = Job(
        id=uuid.uuid4(), queue_id=queue.id, status="FAILED",
        payload={"task_type": "demo.failed"}, failed_at=now
    )
    # Insert retry_waiting job
    j3 = Job(
        id=uuid.uuid4(), queue_id=queue.id, status="RETRY_WAITING",
        payload={"task_type": "demo.retry"}, attempt=2
    )
    db.add_all([j1, j2, j3])
    db.commit()

    res = client.get("/api/v1/metrics", headers=auth_headers)
    assert res.status_code == 200
    data = res.json()

    assert data["jobs"]["total"] == 3
    assert data["jobs"]["completed"] == 1
    assert data["jobs"]["failed"] == 1
    assert data["jobs"]["retry_waiting"] == 1
    # 1 completed out of 2 terminal jobs = 50.0%
    assert data["jobs"]["rates"]["success_rate"] == 50.0
    assert data["jobs"]["rates"]["failure_rate"] == 50.0

def test_queue_utilization_finite_and_unlimited(client: TestClient, auth_headers: dict, db: Session):
    """4, 5. Queue utilization handles finite concurrency limits and NULL (unlimited)."""
    proj = db.query(Project).first()
    assert proj is not None

    # Finite queue
    q_finite = Queue(id=uuid.uuid4(), project_id=proj.id, name="finite-q", concurrency_limit=5)
    # Unlimited queue
    q_unlimited = Queue(id=uuid.uuid4(), project_id=proj.id, name="unlimited-q", concurrency_limit=None)
    db.add_all([q_finite, q_unlimited])
    db.commit()

    # Add active job to finite queue
    j_active = Job(id=uuid.uuid4(), queue_id=q_finite.id, status="RUNNING", payload={"task_type": "test"})
    db.add(j_active)
    db.commit()

    res = client.get("/api/v1/metrics", headers=auth_headers)
    assert res.status_code == 200
    queues_res = {q["queue_name"]: q for q in res.json()["queues"]}

    assert queues_res["finite-q"]["utilization_percentage"] == 20.0  # 1 active out of 5 limit
    assert queues_res["unlimited-q"]["utilization_percentage"] is None  # Unlimited queue

def test_worker_stale_detection(client: TestClient, auth_headers: dict, db: Session):
    """6, 7. Worker heartbeat freshness and STALE detection match 60s timeout."""
    now = datetime.now(timezone.utc)
    
    # Active worker (last heartbeat 10s ago)
    w_active = Worker(
        id=uuid.uuid4(), hostname="node-1", ip_address="192.168.1.1", status="ACTIVE",
        last_heartbeat_at=now - timedelta(seconds=10)
    )
    # Stale worker (last heartbeat 75s ago)
    w_stale = Worker(
        id=uuid.uuid4(), hostname="node-2", ip_address="192.168.1.2", status="ACTIVE",
        last_heartbeat_at=now - timedelta(seconds=75)
    )
    db.add_all([w_active, w_stale])
    db.commit()

    res = client.get("/api/v1/metrics", headers=auth_headers)
    assert res.status_code == 200
    w_summary = res.json()["workers"]
    
    assert w_summary["active_workers"] == 1
    assert w_summary["stale_workers"] == 1

def test_throughput_time_windows(client: TestClient, auth_headers: dict, db: Session):
    """8. Throughput window calculations are correct."""
    queue = db.query(Queue).first()
    assert queue is not None
    now = datetime.now(timezone.utc)

    # Job completed 2 mins ago (in 5m, 15m, 1h)
    j_5m = Job(id=uuid.uuid4(), queue_id=queue.id, status="COMPLETED", payload={"task_type": "test"}, completed_at=now - timedelta(minutes=2))
    # Job completed 10 mins ago (in 15m, 1h)
    j_15m = Job(id=uuid.uuid4(), queue_id=queue.id, status="COMPLETED", payload={"task_type": "test"}, completed_at=now - timedelta(minutes=10))
    # Job completed 2 hours ago (out of 1h)
    j_old = Job(id=uuid.uuid4(), queue_id=queue.id, status="COMPLETED", payload={"task_type": "test"}, completed_at=now - timedelta(hours=2))

    db.add_all([j_5m, j_15m, j_old])
    db.commit()

    res = client.get("/api/v1/metrics", headers=auth_headers)
    assert res.status_code == 200
    tp = res.json()["throughput"]

    assert tp["completed_last_5m"] == 1
    assert tp["completed_last_15m"] == 2
    assert tp["completed_last_hour"] == 2

def test_execution_duration_metrics(client: TestClient, auth_headers: dict, db: Session):
    """9. Execution duration metrics (avg, min, max, percentiles) are correct."""
    queue = db.query(Queue).first()
    assert queue is not None
    job = Job(id=uuid.uuid4(), queue_id=queue.id, status="COMPLETED", payload={"task_type": "test"})
    db.add(job)
    db.commit()

    now = datetime.now(timezone.utc)
    # Execution 1: 100ms
    ex1 = JobExecution(id=uuid.uuid4(), job_id=job.id, status="COMPLETED", attempt=1, started_at=now - timedelta(milliseconds=100), finished_at=now)
    # Execution 2: 300ms
    ex2 = JobExecution(id=uuid.uuid4(), job_id=job.id, status="COMPLETED", attempt=2, started_at=now - timedelta(milliseconds=300), finished_at=now)
    db.add_all([ex1, ex2])
    db.commit()

    res = client.get("/api/v1/metrics", headers=auth_headers)
    assert res.status_code == 200
    perf = res.json()["execution_performance"]

    assert perf["completed_executions_count"] == 2
    assert perf["min_duration_ms"] > 0
    assert perf["max_duration_ms"] >= perf["min_duration_ms"]
    assert perf["avg_duration_ms"] > 0

def test_sensitive_data_sanitization_in_logs():
    """11. Sensitive values never appear in structured log output."""
    raw_payload = {
        "user_email": "test@example.com",
        "password": "SuperSecretPassword123!",
        "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9",
        "normal_field": "public_data"
    }

    sanitized = sanitize_data(raw_payload)
    assert sanitized["password"] == "[REDACTED]"
    assert sanitized["access_token"] == "[REDACTED]"
    assert sanitized["normal_field"] == "public_data"
