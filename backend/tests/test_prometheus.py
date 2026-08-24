import pytest
from collections.abc import Generator
from sqlalchemy.orm import Session
from fastapi.testclient import TestClient

from backend.app.main import app
from backend.app.core.database import SessionLocal
from backend.app.core.prometheus_metrics import (
    JOBS_SUBMITTED_TOTAL, update_db_state_gauges
)

client = TestClient(app)

@pytest.fixture(scope="function")
def db() -> Generator[Session, None, None]:
    """Provides a clean database transaction for test isolation."""
    session = SessionLocal()
    try:
        from sqlalchemy import text
        session.execute(text("TRUNCATE TABLE organizations, users, projects, queues, retry_policies, jobs, job_executions, workers, worker_heartbeats, job_logs, scheduled_jobs, dead_letter_jobs CASCADE;"))
        session.commit()
        yield session
    finally:
        session.close()

def test_prometheus_metrics_endpoint(db: Session):
    """Verify that /metrics exposition endpoint returns HTTP 200 and Prometheus formatted text."""
    update_db_state_gauges(db)
    response = client.get("/metrics")
    assert response.status_code == 200
    assert "text/plain" in response.headers.get("content-type", "")
    assert "scheduler_http_requests_total" in response.text
    assert "scheduler_jobs_current" in response.text

def test_prometheus_counters_increment():
    """Verify that Prometheus metrics counters increment correctly."""
    initial = JOBS_SUBMITTED_TOTAL._value.get()
    JOBS_SUBMITTED_TOTAL.inc()
    assert JOBS_SUBMITTED_TOTAL._value.get() == initial + 1

def test_db_state_gauges(db: Session):
    """Verify that state gauges update accurately from database session."""
    update_db_state_gauges(db)
    response = client.get("/metrics")
    assert response.status_code == 200
    assert "scheduler_jobs_current" in response.text
