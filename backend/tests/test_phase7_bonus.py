import pytest
import uuid
from typing import Generator
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session
from sqlalchemy import text

from backend.app.main import app
from backend.app.core.database import SessionLocal, get_db
from backend.app.core.rate_limiter import limiter
from backend.app.models import User, Organization, Project, Queue, Job, JobDependency, Worker
from backend.app.services.claiming import claim_job, would_create_cycle
from backend.app.services.failure_summary import FailureSummaryService

@pytest.fixture(scope="function")
def db() -> Generator[Session, None, None]:
    session = SessionLocal()
    try:
        session.execute(text("TRUNCATE TABLE organizations, users, projects, queues, retry_policies, jobs, job_executions, workers, worker_heartbeats, job_logs, scheduled_jobs, dead_letter_jobs, job_dependencies CASCADE;"))
        session.commit()
        # Reset limiter counter
        limiter._requests.clear()
        limiter.rejection_count = 0
        yield session
    finally:
        session.rollback()
        session.close()

@pytest.fixture(scope="function")
def client(db: Session) -> Generator[TestClient, None, None]:
    def override_get_db():
        yield db
    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()

def setup_user_and_queue(client: TestClient, email: str = "owner@example.com", role: str = "OWNER"):
    reg = client.post("/api/v1/auth/register", json={
        "email": email,
        "password": "Password123!",
        "organization_name": "Phase7 Corp",
        "role": role
    })
    token = client.post("/api/v1/auth/token", data={
        "username": email,
        "password": "Password123!"
    }).json()["access_token"]

    queues = client.get("/api/v1/queues", headers={"Authorization": f"Bearer {token}"}).json()["items"]
    queue_id = queues[0]["id"]
    return token, queue_id

# --- 1. Batch Jobs Tests ---

def test_atomic_batch_jobs_creation(client: TestClient):
    token, queue_id = setup_user_and_queue(client)
    headers = {"Authorization": f"Bearer {token}"}

    payload = {
        "jobs": [
            {"task_type": "demo.success", "queue_id": queue_id, "priority": 1},
            {"task_type": "demo.slow", "queue_id": queue_id, "priority": 2},
            {"task_type": "demo.retry", "queue_id": queue_id, "priority": 3}
        ]
    }

    res = client.post("/api/v1/jobs/batch", json=payload, headers=headers)
    assert res.status_code == 201
    body = res.json()
    assert body["total_created"] == 3
    assert len(body["jobs"]) == 3

def test_atomic_batch_jobs_rollback_on_failure(client: TestClient, db: Session):
    token, queue_id = setup_user_and_queue(client)
    headers = {"Authorization": f"Bearer {token}"}

    invalid_queue_id = str(uuid.uuid4())
    payload = {
        "jobs": [
            {"task_type": "demo.success", "queue_id": queue_id},
            {"task_type": "demo.slow", "queue_id": invalid_queue_id}  # Invalid queue
        ]
    }

    res = client.post("/api/v1/jobs/batch", json=payload, headers=headers)
    assert res.status_code in (400, 404)
    # Ensure no jobs were persisted
    assert db.query(Job).count() == 0

# --- 2. RBAC Access Control Tests ---

def test_rbac_role_enforcement(client: TestClient, db: Session):
    # Register Owner
    owner_token, queue_id = setup_user_and_queue(client, "owner_test@example.com", "OWNER")
    
    # Register Viewer User in same Org
    org = db.query(Organization).first()
    assert org is not None
    viewer_user = User(
        id=uuid.uuid4(),
        email="viewer@example.com",
        password_hash="fakehash",
        organization_id=org.id,
        role="VIEWER"
    )
    db.add(viewer_user)
    db.commit()

    # Login as Viewer
    from backend.app.core.security import create_access_token
    viewer_token = create_access_token({"sub": str(viewer_user.id), "role": "VIEWER"})
    v_headers = {"Authorization": f"Bearer {viewer_token}"}
    o_headers = {"Authorization": f"Bearer {owner_token}"}

    # Viewer cannot submit single job
    res = client.post("/api/v1/jobs", json={"task_type": "demo.success", "queue_id": queue_id}, headers=v_headers)
    assert res.status_code == 403

    # Viewer cannot pause queue
    res = client.patch(f"/api/v1/queues/{queue_id}/pause", headers=v_headers)
    assert res.status_code == 403

    # Owner CAN pause queue
    res = client.patch(f"/api/v1/queues/{queue_id}/pause", headers=o_headers)
    assert res.status_code == 200
    assert res.json()["is_paused"] is True

# --- 3. Rate Limiting Tests ---

def test_rate_limiting_enforcement(client: TestClient):
    token, queue_id = setup_user_and_queue(client)
    headers = {"Authorization": f"Bearer {token}"}

    # Exceed limit artificially
    key = f"user:test_rate_limit:batch"
    limiter.check_rate_limit(key, max_requests=2, window_seconds=60)
    limiter.check_rate_limit(key, max_requests=2, window_seconds=60)

    with pytest.raises(Exception) as exc_info:
        limiter.check_rate_limit(key, max_requests=2, window_seconds=60)
    assert "429" in str(exc_info.value) or "Rate limit exceeded" in str(exc_info.value)

# --- 4. Workflow Dependencies & Claiming Tests ---

def test_job_workflow_dependencies(client: TestClient, db: Session):
    token, queue_id = setup_user_and_queue(client)
    headers = {"Authorization": f"Bearer {token}"}

    # Create Job A (Parent) and Job B (Dependent Child)
    j_a = client.post("/api/v1/jobs", json={"task_type": "demo.success", "queue_id": queue_id}, headers=headers).json()
    j_b = client.post("/api/v1/jobs", json={"task_type": "demo.success", "queue_id": queue_id}, headers=headers).json()

    job_a_id = uuid.UUID(j_a["id"])
    job_b_id = uuid.UUID(j_b["id"])

    # Job B depends on Job A
    res = client.post(f"/api/v1/jobs/{job_b_id}/dependencies", json={"depends_on_job_id": str(job_a_id)}, headers=headers)
    assert res.status_code == 201

    # Verify circular dependency prevention: Job A depending on Job B must fail
    res_cycle = client.post(f"/api/v1/jobs/{job_a_id}/dependencies", json={"depends_on_job_id": str(job_b_id)}, headers=headers)
    assert res_cycle.status_code == 400
    assert "circular dependency" in str(res_cycle.json()).lower()

    # Register worker
    w_id = uuid.uuid4()
    worker = Worker(id=w_id, hostname="test-worker", ip_address="127.0.0.1", status="ACTIVE")
    db.add(worker)
    db.commit()

    # First claim attempt: Job A MUST be claimed because Job B's dependency (Job A) is not completed yet!
    claimed_1 = claim_job(db, w_id)
    assert claimed_1 is not None
    assert claimed_1.id == job_a_id

    # Try claiming again before Job A completes: Job B should NOT be claimed yet
    claimed_2 = claim_job(db, w_id)
    assert claimed_2 is None

    # Complete Job A
    claimed_1.status = "COMPLETED"
    db.commit()

    # Now Job B should be claimed!
    claimed_3 = claim_job(db, w_id)
    assert claimed_3 is not None
    assert claimed_3.id == job_b_id

# --- 5. AI Failure Summary Tests ---

def test_failure_summary_generation(client: TestClient, db: Session):
    token, queue_id = setup_user_and_queue(client)
    headers = {"Authorization": f"Bearer {token}"}

    job_data = client.post("/api/v1/jobs", json={"task_type": "demo.failure", "queue_id": queue_id}, headers=headers).json()
    job_id = uuid.UUID(job_data["id"])

    job = db.query(Job).filter(Job.id == job_id).first()
    assert job is not None
    job.status = "FAILED"
    job.error = "Connection refused to database host PostgreSQL:5432"
    job.attempt = 3
    db.commit()

    detail = client.get(f"/api/v1/jobs/{job_id}", headers=headers).json()
    assert "failure_summary" in detail
    fs = detail["failure_summary"]
    assert fs is not None
    assert "summary" in fs
    assert "likely_cause" in fs
    assert "recommended_action" in fs
    assert "connection" in fs["summary"].lower() or "refused" in fs["summary"].lower()

# --- 6. Observability Metrics Integration Test ---

def test_phase7_observability_metrics(client: TestClient):
    token, _ = setup_user_and_queue(client)
    headers = {"Authorization": f"Bearer {token}"}

    metrics = client.get("/api/v1/metrics", headers=headers).json()
    assert "bonus_features" in metrics
    bf = metrics["bonus_features"]
    assert "batch_jobs_created" in bf
    assert "dependency_blocked_jobs" in bf
    assert "rate_limit_rejections" in bf
    assert "failure_summaries_generated" in bf
