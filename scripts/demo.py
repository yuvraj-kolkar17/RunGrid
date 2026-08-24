#!/usr/bin/env python3
"""
Reproducible E2E Full System Demonstration Script.

Flow:
1. Health and Readiness Checks
2. User Registration & JWT Authentication
3. Project & Queue Creation
4. Job Creation (Immediate, Delayed, Cron Recurring)
5. Worker Registration & Heartbeat
6. Job Claiming, Execution, Completion
7. Retry Path & DLQ Path Verification
8. Metrics & System Verification
"""

import sys
import time
import uuid
import logging
import httpx
from datetime import datetime, timezone, timedelta

from backend.app.core.config import settings

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("demo")

def get_client(base_url: str):
    if base_url:
        return httpx.Client(base_url=base_url, timeout=10.0)
    else:
        from fastapi.testclient import TestClient
        from backend.app.main import app
        return TestClient(app)

def run_demo(base_url: str = "http://localhost:8000"):
    client = get_client(base_url)

    logger.info("=== 1. HEALTH AND READINESS CHECKS ===")
    res_health = client.get("/health")
    assert res_health.status_code == 200, f"Health check failed: {res_health.text}"
    logger.info(f"GET /health -> {res_health.json()}")

    res_ready = client.get("/ready")
    assert res_ready.status_code == 200, f"Readiness check failed: {res_ready.text}"
    logger.info(f"GET /ready -> {res_ready.json()}")

    logger.info("\n=== 2. AUTHENTICATION & SETUP ===")
    demo_email = f"demo_user_{uuid.uuid4().hex[:6]}@example.com"
    demo_pass = "DemoPass123!"
    
    # Register User & Org
    reg_payload = {
        "email": demo_email,
        "password": demo_pass,
        "organization_name": "Demo Acme Inc"
    }
    res_reg = client.post("/api/v1/auth/register", json=reg_payload)
    assert res_reg.status_code == 201, f"Registration failed: {res_reg.text}"
    user_data = res_reg.json()
    logger.info(f"Registered user: {user_data['email']} under Org ID: {user_data['organization_id']}")

    # Obtain JWT Token
    res_token = client.post("/api/v1/auth/token", data={"username": demo_email, "password": demo_pass})
    assert res_token.status_code == 200, f"Token generation failed: {res_token.text}"
    token = res_token.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}
    logger.info("JWT Token acquired successfully.")

    logger.info("\n=== 3. PROJECT AND QUEUE CREATION ===")
    # Create Project
    res_proj = client.post("/api/v1/projects", json={"name": "Demo E2E Project"}, headers=headers)
    assert res_proj.status_code == 201
    proj_id = res_proj.json()["id"]
    logger.info(f"Project created: {res_proj.json()['name']} (ID: {proj_id})")

    # Create Queue
    queue_payload = {
        "project_id": proj_id,
        "name": "demo-high-priority",
        "concurrency_limit": 10,
        "priority": 10
    }
    res_queue = client.post("/api/v1/queues", json=queue_payload, headers=headers)
    assert res_queue.status_code == 201
    queue_id = res_queue.json()["id"]
    logger.info(f"Queue created: {res_queue.json()['name']} (ID: {queue_id})")

    logger.info("\n=== 4. JOB CREATION (IMMEDIATE, DELAYED, RECURRING) ===")
    # 4a. Immediate Job
    job_payload = {
        "queue_id": queue_id,
        "task_type": "demo.success",
        "payload": {"message": "Hello E2E World"},
        "priority": 5
    }
    res_job1 = client.post("/api/v1/jobs", json=job_payload, headers=headers)
    assert res_job1.status_code == 201
    job1 = res_job1.json()
    assert job1["status"] == "QUEUED"
    logger.info(f"Immediate Job created: ID {job1['id']} - Status: {job1['status']}")

    # 4b. Delayed Job
    delayed_payload = {
        "queue_id": queue_id,
        "task_type": "demo.success",
        "payload": {"message": "Delayed task"},
        "delay": 600
    }
    res_job2 = client.post("/api/v1/jobs", json=delayed_payload, headers=headers)
    assert res_job2.status_code == 201
    job2 = res_job2.json()
    assert job2["status"] == "SCHEDULED"
    logger.info(f"Delayed Job created: ID {job2['id']} - Status: {job2['status']}")

    # 4c. Recurring Cron Job
    cron_payload = {
        "project_id": proj_id,
        "queue_id": queue_id,
        "name": "Hourly Maintenance",
        "cron_expression": "0 * * * *",
        "payload": {"task_type": "demo.success"}
    }
    res_cron = client.post("/api/v1/jobs/scheduled", json=cron_payload, headers=headers)
    assert res_cron.status_code == 201
    cron_job = res_cron.json()
    logger.info(f"Recurring Cron Job created: ID {cron_job['id']} - Expression: {cron_job['cron_expression']}")

    logger.info("\n=== 5. WORKER REGISTRATION & HEARTBEAT ===")
    internal_headers = {"X-Internal-Key": settings.INTERNAL_API_KEY}
    
    worker_reg = {
        "hostname": "demo-worker-node-1",
        "ip_address": "192.168.1.100"
    }
    res_w = client.post("/api/v1/internal/workers/register", json=worker_reg, headers=internal_headers)
    assert res_w.status_code == 200
    worker_id = res_w.json()["id"]
    logger.info(f"Worker registered: ID {worker_id}")

    hb_payload = {
        "status": "ACTIVE",
        "active_jobs": 0,
        "max_concurrency": 10,
        "available_capacity": 10
    }
    res_hb = client.post(f"/api/v1/internal/workers/{worker_id}/heartbeat", json=hb_payload, headers=internal_headers)
    assert res_hb.status_code == 200
    logger.info("Worker heartbeat recorded successfully.")

    logger.info("\n=== 6. WORKER POLLING & EXECUTION ===")
    res_poll = client.post(f"/api/v1/internal/workers/{worker_id}/poll", headers=internal_headers)
    assert res_poll.status_code == 200
    claimed_job = res_poll.json()
    logger.info(f"Worker claimed Job ID: {claimed_job['id']} - Status: {claimed_job['status']}")

    res_start = client.post(f"/api/v1/internal/jobs/{claimed_job['id']}/start", json={"worker_id": worker_id}, headers=internal_headers)
    assert res_start.status_code == 200
    running_job = res_start.json()
    assert running_job["status"] == "RUNNING"
    logger.info(f"Worker started Job ID: {running_job['id']} - Status: {running_job['status']}")

    res_complete = client.post(
        f"/api/v1/internal/jobs/{claimed_job['id']}/complete",
        json={"worker_id": worker_id, "result": {"output": "SUCCESS_DEMO_COMPLETED"}},
        headers=internal_headers
    )
    assert res_complete.status_code == 200
    completed_job = res_complete.json()
    assert completed_job["status"] == "COMPLETED"
    logger.info(f"Worker completed Job ID: {completed_job['id']} - Status: {completed_job['status']}")

    logger.info("\n=== 7. RETRY & DLQ PATH VERIFICATION ===")
    # 7a. Retry Path (max_retries = 3 -> transition to RETRY_WAITING on first failure)
    retry_job_payload = {
        "queue_id": queue_id,
        "task_type": "demo.retry",
        "payload": {"fail_until_attempt": 2},
        "max_retries": 3,
        "priority": 1
    }
    res_retry_job = client.post("/api/v1/jobs", json=retry_job_payload, headers=headers)
    assert res_retry_job.status_code == 201
    retry_job_id = res_retry_job.json()["id"]

    res_poll_retry = client.post(f"/api/v1/internal/workers/{worker_id}/poll", headers=internal_headers)
    assert res_poll_retry.status_code == 200
    res_start_retry = client.post(f"/api/v1/internal/jobs/{retry_job_id}/start", json={"worker_id": worker_id}, headers=internal_headers)
    assert res_start_retry.status_code == 200

    res_fail_retry = client.post(
        f"/api/v1/internal/jobs/{retry_job_id}/fail",
        json={"worker_id": worker_id, "error_message": "Transient error simulation"},
        headers=internal_headers
    )
    assert res_fail_retry.status_code == 200
    retry_job_state = res_fail_retry.json()
    assert retry_job_state["status"] == "RETRY_WAITING"
    logger.info(f"Verified Retry transition: Job ID {retry_job_id} -> Status: {retry_job_state['status']}")

    # 7b. DLQ Path (max_retries = 1 -> direct to DLQ on attempt 1 failure)
    import os
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker
    from backend.app.models import RetryPolicy
    
    db_url = os.getenv("DATABASE_URL", "postgresql://lumina:lumina123@localhost:5433/lumina_db")
    engine = create_engine(db_url)
    SessionLocalDocker = sessionmaker(bind=engine)
    db = SessionLocalDocker()
    dlq_policy_id = None
    try:
        policy = RetryPolicy(id=uuid.uuid4(), name=f"dlq-policy-{uuid.uuid4().hex[:4]}", max_retries=1, base_delay=1, strategy="fixed")
        db.add(policy)
        db.commit()
        dlq_policy_id = str(policy.id)
    finally:
        db.close()

    dlq_job_payload = {
        "queue_id": queue_id,
        "task_type": "demo.failure",
        "payload": {"error_type": "permanent_fatal_error"},
        "retry_policy_id": dlq_policy_id,
        "priority": 1
    }
    res_dlq_job = client.post("/api/v1/jobs", json=dlq_job_payload, headers=headers)
    assert res_dlq_job.status_code == 201
    dlq_job_id = res_dlq_job.json()["id"]

    # Poll and fail job
    res_poll_dlq = client.post(f"/api/v1/internal/workers/{worker_id}/poll", headers=internal_headers)
    assert res_poll_dlq.status_code == 200
    res_start_dlq = client.post(f"/api/v1/internal/jobs/{dlq_job_id}/start", json={"worker_id": worker_id}, headers=internal_headers)
    assert res_start_dlq.status_code == 200

    res_fail_dlq = client.post(
        f"/api/v1/internal/jobs/{dlq_job_id}/fail",
        json={"worker_id": worker_id, "error_message": "Fatal simulated task error"},
        headers=internal_headers
    )
    assert res_fail_dlq.status_code == 200
    failed_job_state = res_fail_dlq.json()
    assert failed_job_state["status"] == "DEAD_LETTER"
    logger.info(f"Verified DLQ transition: Job ID {dlq_job_id} -> Status: {failed_job_state['status']}")

    logger.info("\n=== 8. METRICS VERIFICATION ===")
    res_metrics = client.get("/api/v1/metrics", headers=headers)
    assert res_metrics.status_code == 200
    metrics = res_metrics.json()
    logger.info("System Metrics Overview:")
    logger.info(f"  Total Jobs: {metrics['jobs']['total']}")
    logger.info(f"  Completed Jobs: {metrics['jobs']['completed']}")
    logger.info(f"  Dead Letter Jobs: {metrics['jobs']['dead_letter']}")
    logger.info(f"  Active Workers: {metrics['workers']['active_workers']}")

    logger.info("\n=======================================================")
    logger.info(" SUCCESS: ALL SYSTEM & DLQ LIFECYCLE FLOWS VERIFIED ")
    logger.info("=======================================================")

if __name__ == "__main__":
    url = sys.argv[1] if len(sys.argv) > 1 else "http://localhost:8000"
    run_demo(url)
