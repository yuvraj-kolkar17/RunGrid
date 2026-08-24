import pytest
from fastapi.testclient import TestClient
from collections.abc import Generator
from sqlalchemy.orm import Session
import uuid

from backend.app.main import app
from backend.app.core.database import SessionLocal, get_db
from backend.app.models import Organization, User, Project, Queue, Job, BatchSubmission
from backend.app.core.security import create_access_token, get_password_hash


@pytest.fixture(scope="function")
def db() -> Generator[Session, None, None]:
    """Provides a clean database transaction for each test."""
    session = SessionLocal()
    try:
        from sqlalchemy import text
        session.execute(text("TRUNCATE TABLE organizations, users, projects, queues, retry_policies, jobs, job_executions, workers, worker_heartbeats, job_logs, scheduled_jobs, dead_letter_jobs, batch_submissions CASCADE;"))
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
            pass

    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()


@pytest.fixture
def auth_headers(db: Session):
    org = Organization(id=uuid.uuid4(), name="Platform Test Org")
    db.add(org)

    user = User(
        id=uuid.uuid4(),
        email="platform_owner@test.com",
        password_hash=get_password_hash("password123"),
        role="OWNER",
        organization_id=org.id
    )
    db.add(user)

    proj = Project(id=uuid.uuid4(), name="Platform Project", organization_id=org.id)
    db.add(proj)

    queue = Queue(id=uuid.uuid4(), project_id=proj.id, name="platform-queue", priority=1)
    db.add(queue)

    db.commit()

    token = create_access_token({"sub": str(user.id)})
    return {"Authorization": f"Bearer {token}"}, user, queue


def test_platform_overview(client: TestClient, auth_headers):
    headers, user, queue = auth_headers
    response = client.get("/api/v1/platform/overview", headers=headers)
    assert response.status_code == 200
    data = response.json()
    assert "summary" in data
    assert "batch_jobs_created" in data["summary"]
    assert "dependency_blocks" in data["summary"]
    assert "rate_limit_rejections" in data["summary"]
    assert "failure_analyses" in data["summary"]
    assert "system_health" in data


def test_platform_observability(client: TestClient, auth_headers):
    headers, user, queue = auth_headers
    response = client.get("/api/v1/platform/observability", headers=headers)
    assert response.status_code == 200
    data = response.json()
    assert "job_states" in data
    assert "throughput_series" in data
    assert "execution_performance" in data


def test_batch_submission_history_and_atomic_rollback(client: TestClient, auth_headers, db: Session):
    headers, user, queue = auth_headers

    # 1. Submit batch with valid task types
    batch_payload = {
        "jobs": [
            {
                "queue_id": str(queue.id),
                "task_type": "email.send",
                "payload": {"email": "user1@test.com"}
            },
            {
                "queue_id": str(queue.id),
                "task_type": "report.generate",
                "payload": {"report_id": "rep_101"}
            }
        ]
    }
    response = client.post("/api/v1/jobs/batch", json=batch_payload, headers=headers)
    assert response.status_code == 201
    assert response.json()["total_created"] == 2

    # 2. List batches
    batches_res = client.get("/api/v1/platform/batches", headers=headers)
    assert batches_res.status_code == 200
    b_data = batches_res.json()
    assert b_data["total"] >= 1
    batch_id = b_data["items"][0]["id"]

    # 3. Get batch detail
    detail_res = client.get(f"/api/v1/platform/batches/{batch_id}", headers=headers)
    assert detail_res.status_code == 200
    assert len(detail_res.json()["jobs"]) == 2

    # 4. Atomic rollback test (invalid queue ID in batch)
    invalid_batch_payload = {
        "jobs": [
            {
                "queue_id": str(queue.id),
                "task_type": "email.send",
                "payload": {"email": "user2@test.com"}
            },
            {
                "queue_id": str(uuid.uuid4()),  # Non-existent queue
                "task_type": "report.generate",
                "payload": {"report_id": "rep_102"}
            }
        ]
    }
    fail_res = client.post("/api/v1/jobs/batch", json=invalid_batch_payload, headers=headers)
    assert fail_res.status_code == 404
    err_body = fail_res.json()
    assert "QUEUE_NOT_FOUND" in str(err_body)


def test_platform_workflows(client: TestClient, auth_headers):
    headers, user, queue = auth_headers

    # Create two jobs and a dependency with valid task types
    j1_res = client.post("/api/v1/jobs", json={
        "queue_id": str(queue.id),
        "task_type": "report.generate",
        "payload": {"title": "Parent Workflow Job"}
    }, headers=headers)
    assert j1_res.status_code == 201
    j1_id = j1_res.json()["id"]

    j2_res = client.post("/api/v1/jobs", json={
        "queue_id": str(queue.id),
        "task_type": "email.send",
        "payload": {"title": "Child Workflow Job"}
    }, headers=headers)
    assert j2_res.status_code == 201
    j2_id = j2_res.json()["id"]

    # Add dependency: j2 depends on j1
    dep_res = client.post(f"/api/v1/jobs/{j2_id}/dependencies", json={
        "depends_on_job_id": j1_id
    }, headers=headers)
    assert dep_res.status_code == 201

    # Fetch workflows
    wf_res = client.get("/api/v1/platform/workflows", headers=headers)
    assert wf_res.status_code == 200
    wfs = wf_res.json()["workflows"]
    assert len(wfs) >= 1
    assert wfs[0]["total_jobs"] >= 2


def test_platform_rate_limiting_and_test_control(client: TestClient, auth_headers):
    headers, user, queue = auth_headers

    # 1. Get status
    rl_res = client.get("/api/v1/platform/rate-limits", headers=headers)
    assert rl_res.status_code == 200
    assert "protected_endpoints" in rl_res.json()

    # 2. Trigger operator rate limit test
    test_res = client.post("/api/v1/platform/rate-limits/test?num_requests=25", headers=headers)
    assert test_res.status_code == 200
    t_data = test_res.json()
    assert t_data["requests_sent"] == 25
    assert t_data["allowed_requests"] == 20
    assert t_data["rejected_429_requests"] == 5


def test_platform_failure_analysis(client: TestClient, auth_headers, db: Session):
    headers, user, queue = auth_headers

    # Create a failed job in DB
    failed_job = Job(
        id=uuid.uuid4(),
        queue_id=queue.id,
        status="FAILED",
        payload={"task_type": "image.process", "title": "Transcode Video"},
        error="Transcoding subprocess timed out after 300 seconds",
        attempt=3,
        max_retries=3
    )
    db.add(failed_job)
    db.commit()

    response = client.get("/api/v1/platform/failures", headers=headers)
    assert response.status_code == 200
    data = response.json()
    assert data["total"] >= 1
    item = data["items"][0]
    assert "failure_analysis" in item
    assert "summary" in item["failure_analysis"]
    assert "likely_cause" in item["failure_analysis"]
    assert "recommended_action" in item["failure_analysis"]


from unittest.mock import patch, MagicMock
import io
import json

def test_prometheus_timeseries_endpoint_authenticated(client: TestClient, auth_headers):
    headers, user, queue = auth_headers
    
    # 1. Unauthenticated request should fail
    unauth_res = client.get("/api/v1/platform/observability/timeseries")
    assert unauth_res.status_code == 401

    # 2. Authenticated request
    response = client.get("/api/v1/platform/observability/timeseries?range=15m&step=10s", headers=headers)
    assert response.status_code == 200
    data = response.json()
    assert "range" in data
    assert "step" in data
    assert "prometheus_status" in data
    assert "series" in data
    assert "latest_values" in data
    assert isinstance(data["series"], list)


def test_prometheus_timeseries_mocked_success(client: TestClient, auth_headers):
    headers, user, queue = auth_headers

    mock_prom_response = {
        "status": "success",
        "data": {
            "resultType": "matrix",
            "result": [
                {
                    "metric": {},
                    "values": [
                        [1756051200, "2.5"],
                        [1756051210, "3.1"],
                        [1756051220, "4.0"]
                    ]
                }
            ]
        }
    }

    mock_body = json.dumps(mock_prom_response).encode("utf-8")
    
    with patch("urllib.request.urlopen") as mock_urlopen:
        cm = MagicMock()
        cm.read.return_value = mock_body
        cm.__enter__.return_value = cm
        mock_urlopen.return_value = cm

        res = client.get("/api/v1/platform/observability/timeseries?range=5m&step=5s", headers=headers)
        assert res.status_code == 200
        data = res.json()

        assert data["prometheus_status"] == "HEALTHY"
        assert data["range"] == "5m"
        assert data["step"] == 5
        assert len(data["series"]) >= 3

        # Check timestamp and value parsing
        pt0 = data["series"][0]
        assert "timestamp" in pt0
        assert "time_label" in pt0
        assert ":" in pt0["time_label"]
        assert pt0["completed_per_second"] >= 0.0


def test_prometheus_timeseries_unavailable(client: TestClient, auth_headers):
    headers, user, queue = auth_headers

    with patch("urllib.request.urlopen", side_effect=Exception("Prometheus Connection Refused")):
        res = client.get("/api/v1/platform/observability/timeseries?range=15m", headers=headers)
        assert res.status_code == 200
        data = res.json()

        assert data["prometheus_status"] == "UNREACHABLE"
        assert "series" in data
        assert "latest_values" in data


def test_prometheus_timeseries_range_parsing(client: TestClient, auth_headers):
    headers, user, queue = auth_headers

    # Test range=5m -> step 5s
    res_5m = client.get("/api/v1/platform/observability/timeseries?range=5m", headers=headers)
    assert res_5m.status_code == 200
    assert res_5m.json()["step"] == 5

    # Test range=1h -> step 30s
    res_1h = client.get("/api/v1/platform/observability/timeseries?range=1h", headers=headers)
    assert res_1h.status_code == 200
    assert res_1h.json()["step"] == 30

    # Test custom range string
    res_custom = client.get("/api/v1/platform/observability/timeseries?range=10m&step=20s", headers=headers)
    assert res_custom.status_code == 200
    assert res_custom.json()["range"] == "10m"
    assert res_custom.json()["step"] == 20

