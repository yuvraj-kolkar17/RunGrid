import pytest
import uuid
from datetime import datetime, timezone, timedelta
from fastapi.testclient import TestClient
from collections.abc import Generator
from sqlalchemy.orm import Session

from backend.app.main import app
from backend.app.core.database import SessionLocal, get_db
from backend.app.core.config import settings
from backend.app.models import RetryPolicy, Job, Queue, Project, DeadLetterJob
from backend.app.services.scheduler import process_delayed_jobs

@pytest.fixture(scope="function")
def db() -> Generator[Session, None, None]:
    """Provides a clean database transaction for each test, truncating tables to ensure isolation."""
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
    """Provides a TestClient overriding get_db to share the test transaction."""
    def override_get_db():
        try:
            yield db
        finally:
            pass  # Session rollback/close managed by the db fixture
            
    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()

def test_auth_and_registration(client: TestClient):
    """Verifies register, login, and profile retrieval flows."""
    email = f"user_{uuid.uuid4().hex[:6]}@example.com"
    password = "secretpassword"
    org_name = "Acme Corp"
    
    # 1. Register User & Org
    reg_resp = client.post("/api/v1/auth/register", json={
        "email": email,
        "password": password,
        "organization_name": org_name
    })
    assert reg_resp.status_code == 201
    reg_json = reg_resp.json()
    assert reg_json["email"] == email
    assert "id" in reg_json
    assert "organization_id" in reg_json
    
    # 2. Login to get JWT
    login_resp = client.post("/api/v1/auth/token", data={
        "username": email,
        "password": password
    })
    assert login_resp.status_code == 200
    token_json = login_resp.json()
    assert "access_token" in token_json
    assert token_json["token_type"] == "bearer"
    token = token_json["access_token"]
    
    # 3. Access /me endpoint
    me_resp = client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert me_resp.status_code == 200
    me_json = me_resp.json()
    assert me_json["email"] == email
    assert me_json["organization_id"] == reg_json["organization_id"]

def test_project_and_queue_crud(client: TestClient):
    """Verifies creation, pagination, pause/resume, and stats for projects and queues."""
    # Register & Login
    email = f"user_{uuid.uuid4().hex[:6]}@example.com"
    client.post("/api/v1/auth/register", json={"email": email, "password": "password123", "organization_name": "Org 1"})
    token = client.post("/api/v1/auth/token", data={"username": email, "password": "password123"}).json()["access_token"]
    auth_headers = {"Authorization": f"Bearer {token}"}
    
    # Create project
    proj_resp = client.post("/api/v1/projects", json={"name": "Alpha Project"}, headers=auth_headers)
    assert proj_resp.status_code == 201
    proj_id = proj_resp.json()["id"]
    
    # List projects
    list_proj = client.get("/api/v1/projects?page=1&page_size=10", headers=auth_headers).json()
    assert list_proj["total"] >= 1
    assert any(p["name"] == "Alpha Project" for p in list_proj["items"])
    
    # Create queue
    queue_resp = client.post("/api/v1/queues", json={
        "name": "high-priority-queue",
        "priority": 10,
        "concurrency_limit": 5,
        "project_id": proj_id
    }, headers=auth_headers)
    assert queue_resp.status_code == 201
    queue_json = queue_resp.json()
    assert queue_json["name"] == "high-priority-queue"
    queue_id = queue_json["id"]
    
    # Update queue
    update_resp = client.patch(f"/api/v1/queues/{queue_id}", json={"priority": 15, "concurrency_limit": 2}, headers=auth_headers)
    assert update_resp.status_code == 200
    assert update_resp.json()["priority"] == 15
    assert update_resp.json()["concurrency_limit"] == 2
    
    # Pause queue
    pause_resp = client.patch(f"/api/v1/queues/{queue_id}/pause", headers=auth_headers)
    assert pause_resp.status_code == 200
    assert pause_resp.json()["is_paused"] is True
    
    # Resume queue
    resume_resp = client.patch(f"/api/v1/queues/{queue_id}/resume", headers=auth_headers)
    assert resume_resp.status_code == 200
    assert resume_resp.json()["is_paused"] is False
    
    # Stats
    stats_resp = client.get(f"/api/v1/queues/{queue_id}/stats", headers=auth_headers)
    assert stats_resp.status_code == 200
    stats = stats_resp.json()
    assert stats["queued_count"] == 0
    assert stats["running_count"] == 0

def test_organization_isolation(client: TestClient):
    """Verifies that organization data is isolated and cross-organization lookups return 404."""
    # User A
    client.post("/api/v1/auth/register", json={"email": "usera@example.com", "password": "passwordA", "organization_name": "Org A"})
    token_a = client.post("/api/v1/auth/token", data={"username": "usera@example.com", "password": "passwordA"}).json()["access_token"]
    headers_a = {"Authorization": f"Bearer {token_a}"}
    
    # User B
    client.post("/api/v1/auth/register", json={"email": "userb@example.com", "password": "passwordB", "organization_name": "Org B"})
    token_b = client.post("/api/v1/auth/token", data={"username": "userb@example.com", "password": "passwordB"}).json()["access_token"]
    headers_b = {"Authorization": f"Bearer {token_b}"}
    
    # User A creates a project and queue
    proj_a = client.post("/api/v1/projects", json={"name": "Project A"}, headers=headers_a).json()
    queue_a = client.post("/api/v1/queues", json={
        "name": "Queue A",
        "priority": 1,
        "concurrency_limit": 2,
        "project_id": proj_a["id"]
    }, headers=headers_a).json()
    
    # User B attempts to fetch Project A -> 404
    resp = client.get(f"/api/v1/projects/{proj_a['id']}", headers=headers_b)
    assert resp.status_code == 404
    assert resp.json()["error"]["code"] == "PROJECT_NOT_FOUND"
    
    # User B attempts to fetch Queue A -> 404
    resp2 = client.get(f"/api/v1/queues/{queue_a['id']}", headers=headers_b)
    assert resp2.status_code == 404
    assert resp2.json()["error"]["code"] == "QUEUE_NOT_FOUND"
    
    # User B attempts to create queue inside Project A -> 404 Project Not Found
    resp3 = client.post("/api/v1/queues", json={
        "name": "Queue B",
        "priority": 1,
        "concurrency_limit": 2,
        "project_id": proj_a["id"]
    }, headers=headers_b)
    assert resp3.status_code == 404

def test_internal_api_key_protection(client: TestClient):
    """Verifies that internal routes block requests that don't have the correct X-Internal-Key."""
    worker_id = str(uuid.uuid4())
    
    # Missing key -> 401
    resp = client.post(f"/api/v1/internal/workers/{worker_id}/heartbeat")
    assert resp.status_code == 401
    assert resp.json()["error"]["code"] == "UNAUTHORIZED"
    
    # Wrong key -> 401
    resp2 = client.post(
        f"/api/v1/internal/workers/{worker_id}/heartbeat",
        headers={"X-Internal-Key": "wrong-secret"}
    )
    assert resp2.status_code == 401
    
    # Correct key, but worker not found -> 404 (Allowed key, logic error)
    resp3 = client.post(
        f"/api/v1/internal/workers/{worker_id}/heartbeat",
        headers={"X-Internal-Key": settings.INTERNAL_API_KEY}
    )
    assert resp3.status_code == 404
    assert resp3.json()["error"]["code"] == "WORKER_NOT_FOUND"

def test_validation_constraints(client: TestClient):
    """Verifies API parameter validation rules are strictly enforced."""
    # Register & Login
    email = f"user_{uuid.uuid4().hex[:6]}@example.com"
    client.post("/api/v1/auth/register", json={"email": email, "password": "password123", "organization_name": "Org"})
    token = client.post("/api/v1/auth/token", data={"username": email, "password": "password123"}).json()["access_token"]
    auth_headers = {"Authorization": f"Bearer {token}"}
    
    proj = client.post("/api/v1/projects", json={"name": "Proj"}, headers=auth_headers).json()
    
    # 1. Invalid Priority (< 0) -> 422
    resp = client.post("/api/v1/queues", json={
        "name": "Queue",
        "priority": -5,
        "project_id": proj["id"]
    }, headers=auth_headers)
    assert resp.status_code == 422
    assert resp.json()["error"]["code"] == "VALIDATION_ERROR"

    
    # 2. Invalid Concurrency Limit (<= 0) -> 422
    resp2 = client.post("/api/v1/queues", json={
        "name": "Queue",
        "concurrency_limit": 0,
        "project_id": proj["id"]
    }, headers=auth_headers)
    assert resp2.status_code == 422
    
    # 3. Invalid task_type -> 422
    queue = client.post("/api/v1/queues", json={
        "name": "Queue",
        "project_id": proj["id"]
    }, headers=auth_headers).json()
    
    resp3 = client.post("/api/v1/jobs", json={
        "task_type": "invalid.task.name",
        "queue_id": queue["id"]
    }, headers=auth_headers)
    assert resp3.status_code == 422

def test_end_to_end_success_path(client: TestClient, db: Session):
    """Verifies E2E path: submit immediate job -> claim -> start -> complete."""
    # Setup Auth, Project, Queue
    email = "test_success@example.com"
    client.post("/api/v1/auth/register", json={"email": email, "password": "password", "organization_name": "Org"})
    token = client.post("/api/v1/auth/token", data={"username": email, "password": "password"}).json()["access_token"]
    auth_headers = {"Authorization": f"Bearer {token}"}
    internal_headers = {"X-Internal-Key": settings.INTERNAL_API_KEY}
    
    # Create project & queue
    proj = client.post("/api/v1/projects", json={"name": "Alpha"}, headers=auth_headers).json()
    queue = client.post("/api/v1/queues", json={"name": "fast-queue", "project_id": proj["id"]}, headers=auth_headers).json()
    
    # Setup default Retry Policy in DB
    policy = RetryPolicy(name="default", strategy="fixed", base_delay=1, max_retries=3)
    db.add(policy)
    db.commit()
    
    # 1. Submit Immediate Job -> status = QUEUED
    job_resp = client.post("/api/v1/jobs", json={
        "task_type": "demo.success",
        "payload": {"data": "test"},
        "queue_id": queue["id"]
    }, headers=auth_headers)
    assert job_resp.status_code == 201
    job_json = job_resp.json()
    assert job_json["status"] == "QUEUED"
    job_id = job_json["id"]
    
    # 2. Register Worker
    worker_resp = client.post("/api/v1/internal/workers/register", json={
        "hostname": "worker-1",
        "ip_address": "127.0.0.1"
    }, headers=internal_headers)
    assert worker_resp.status_code == 200
    worker_id = worker_resp.json()["id"]
    
    # 3. Worker Poll (Atomic claim) -> status = CLAIMED
    poll_resp = client.post(f"/api/v1/internal/workers/{worker_id}/poll", headers=internal_headers)
    assert poll_resp.status_code == 200
    poll_json = poll_resp.json()
    assert poll_json is not None
    assert poll_json["id"] == job_id
    assert poll_json["status"] == "CLAIMED"
    assert poll_json["attempt"] == 0
    
    # 4. Start Job -> status = RUNNING
    start_resp = client.post(
        f"/api/v1/internal/jobs/{job_id}/start",
        json={"worker_id": worker_id},
        headers=internal_headers
    )
    assert start_resp.status_code == 200
    start_json = start_resp.json()
    assert start_json["status"] == "RUNNING"
    assert start_json["attempt"] == 1
    
    # 5. Complete Job -> status = COMPLETED
    complete_resp = client.post(
        f"/api/v1/internal/jobs/{job_id}/complete",
        json={"worker_id": worker_id, "result": {"status": "success", "duration_ms": 150}},
        headers=internal_headers
    )

    assert complete_resp.status_code == 200
    complete_json = complete_resp.json()
    assert complete_json["status"] == "COMPLETED"
    assert complete_json["result"] == {"status": "success", "duration_ms": 150}

def test_job_failure_and_retry_backoff(client: TestClient, db: Session):
    """Verifies failure path: fails -> RETRY_WAITING -> scheduler transitions back to QUEUED -> claims."""
    # Setup Auth, Project, Queue
    email = "test_failure@example.com"
    client.post("/api/v1/auth/register", json={"email": email, "password": "password", "organization_name": "Org"})
    token = client.post("/api/v1/auth/token", data={"username": email, "password": "password"}).json()["access_token"]
    auth_headers = {"Authorization": f"Bearer {token}"}
    internal_headers = {"X-Internal-Key": settings.INTERNAL_API_KEY}
    
    proj = client.post("/api/v1/projects", json={"name": "Beta"}, headers=auth_headers).json()
    queue = client.post("/api/v1/queues", json={"name": "slow-queue", "project_id": proj["id"]}, headers=auth_headers).json()
    
    policy = RetryPolicy(name="default", strategy="linear", base_delay=5, max_retries=2)
    db.add(policy)
    db.commit()
    
    # 1. Submit job
    job = client.post("/api/v1/jobs", json={
        "task_type": "demo.failure",
        "queue_id": queue["id"]
    }, headers=auth_headers).json()
    job_id = job["id"]
    
    # 2. Worker claims job
    worker = client.post("/api/v1/internal/workers/register", json={"hostname": "w1", "ip_address": "127.0.0.1"}, headers=internal_headers).json()
    worker_id = worker["id"]
    client.post(f"/api/v1/internal/workers/{worker_id}/poll", headers=internal_headers)
    
    # 3. Start execution (attempt = 1)
    client.post(f"/api/v1/internal/jobs/{job_id}/start", json={"worker_id": worker_id}, headers=internal_headers)
    
    # 4. Fail execution -> status = RETRY_WAITING
    fail_resp = client.post(
        f"/api/v1/internal/jobs/{job_id}/fail",
        json={"worker_id": worker_id, "error_message": "Execution crashed!"},
        headers=internal_headers
    )

    assert fail_resp.status_code == 200
    fail_json = fail_resp.json()
    assert fail_json["status"] == "RETRY_WAITING"
    assert fail_json["attempt"] == 1
    
    # 5. Try scheduler cycle immediately -> job not transitioned
    db.expire_all()
    scheduler_reloads = process_delayed_jobs(db)
    db.commit()
    assert scheduler_reloads == 0
    
    # 6. Manually adjust available_at to past
    db_job = db.query(Job).filter(Job.id == job_id).first()
    assert db_job is not None
    db_job.available_at = datetime.now(timezone.utc) - timedelta(seconds=1)
    db.commit()
    
    # 7. Run scheduler cycle now -> transitions RETRY_WAITING to QUEUED
    scheduler_reloads_2 = process_delayed_jobs(db)
    db.commit()
    assert scheduler_reloads_2 == 1
    
    db.refresh(db_job)
    assert db_job.status == "QUEUED"
    
    # 8. Worker polls and claims retried job
    poll_resp = client.post(f"/api/v1/internal/workers/{worker_id}/poll", headers=internal_headers)
    assert poll_resp.status_code == 200
    assert poll_resp.json()["id"] == job_id
    assert poll_resp.json()["status"] == "CLAIMED"
    assert poll_resp.json()["attempt"] == 1

def test_max_attempts_dead_letter_queue(client: TestClient, db: Session):
    """Verifies that a job exceeding max retries transitions to DEAD_LETTER queue."""
    email = "test_dlq@example.com"
    client.post("/api/v1/auth/register", json={"email": email, "password": "password", "organization_name": "Org"})
    token = client.post("/api/v1/auth/token", data={"username": email, "password": "password"}).json()["access_token"]
    auth_headers = {"Authorization": f"Bearer {token}"}
    internal_headers = {"X-Internal-Key": settings.INTERNAL_API_KEY}
    
    proj = client.post("/api/v1/projects", json={"name": "Gamma"}, headers=auth_headers).json()
    queue = client.post("/api/v1/queues", json={"name": "dlq-queue", "project_id": proj["id"]}, headers=auth_headers).json()
    
    policy = RetryPolicy(name="default", strategy="fixed", base_delay=1, max_retries=1)
    db.add(policy)
    db.commit()
    
    job = client.post("/api/v1/jobs", json={"task_type": "demo.failure", "queue_id": queue["id"]}, headers=auth_headers).json()
    job_id = job["id"]
    
    worker = client.post("/api/v1/internal/workers/register", json={"hostname": "w", "ip_address": "127.0.0.1"}, headers=internal_headers).json()
    worker_id = worker["id"]
    client.post(f"/api/v1/internal/workers/{worker_id}/poll", headers=internal_headers)
    
    client.post(f"/api/v1/internal/jobs/{job_id}/start", json={"worker_id": worker_id}, headers=internal_headers)
    
    fail_resp = client.post(
        f"/api/v1/internal/jobs/{job_id}/fail",
        json={"worker_id": worker_id, "error_message": "Permanent crash"},
        headers=internal_headers
    )

    assert fail_resp.status_code == 200
    assert fail_resp.json()["status"] == "DEAD_LETTER"
    
    dlq_entry = db.query(DeadLetterJob).filter(DeadLetterJob.job_id == job_id).first()
    assert dlq_entry is not None
    assert dlq_entry.failure_reason == "Permanent crash"
    
    stats = client.get(f"/api/v1/queues/{queue['id']}/stats", headers=auth_headers).json()
    assert stats["dead_letter_count"] == 1

def test_delayed_job_lifecycle(client: TestClient, db: Session):
    """Verifies delayed job semantics: starts SCHEDULED, poll returns nothing, scheduler triggers QUEUED."""
    email = "test_delayed@example.com"
    client.post("/api/v1/auth/register", json={"email": email, "password": "password", "organization_name": "Org"})
    token = client.post("/api/v1/auth/token", data={"username": email, "password": "password"}).json()["access_token"]
    auth_headers = {"Authorization": f"Bearer {token}"}
    internal_headers = {"X-Internal-Key": settings.INTERNAL_API_KEY}
    
    proj = client.post("/api/v1/projects", json={"name": "Delta"}, headers=auth_headers).json()
    queue = client.post("/api/v1/queues", json={"name": "delayed-queue", "project_id": proj["id"]}, headers=auth_headers).json()
    
    policy = RetryPolicy(name="default", strategy="fixed", base_delay=1, max_retries=3)
    db.add(policy)
    db.commit()
    
    job = client.post("/api/v1/jobs", json={
        "task_type": "demo.success",
        "queue_id": queue["id"],
        "delay": 60
    }, headers=auth_headers).json()
    job_id = job["id"]
    assert job["status"] == "SCHEDULED"
    
    worker = client.post("/api/v1/internal/workers/register", json={"hostname": "w", "ip_address": "127.0.0.1"}, headers=internal_headers).json()
    worker_id = worker["id"]
    poll_resp1 = client.post(f"/api/v1/internal/workers/{worker_id}/poll", headers=internal_headers)
    assert poll_resp1.status_code == 200
    assert poll_resp1.json() is None
    
    scheduler_moved = process_delayed_jobs(db)
    assert scheduler_moved == 0
    
    db_job = db.query(Job).filter(Job.id == job_id).first()
    assert db_job is not None
    db_job.available_at = datetime.now(timezone.utc) - timedelta(seconds=1)
    db.commit()
    
    scheduler_moved_2 = process_delayed_jobs(db)
    db.commit()
    assert scheduler_moved_2 == 1
    
    db.refresh(db_job)
    assert db_job.status == "QUEUED"
    
    poll_resp2 = client.post(f"/api/v1/internal/workers/{worker_id}/poll", headers=internal_headers)
    assert poll_resp2.status_code == 200
    assert poll_resp2.json()["id"] == job_id
    assert poll_resp2.json()["status"] == "CLAIMED"
