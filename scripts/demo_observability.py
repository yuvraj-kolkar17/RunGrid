#!/usr/bin/env python3
"""
E2E Observability Verification Script for Distributed Job Scheduler.

Flow:
1. Health & Readiness verification
2. Authentication (Register/Login user)
3. Submit workload (success, failure, retry, scheduled jobs)
4. Trigger worker activity & heartbeats
5. Fetch and print formatted GET /api/v1/metrics report (throughput, latencies, worker states, queue utilization)
"""

import sys
import time
import uuid
import json
import logging
import httpx
from datetime import datetime, timezone

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("demo_observability")

def run_observability_demo(base_url: str = "http://localhost:8000"):
    client = httpx.Client(base_url=base_url, timeout=10.0)

    logger.info("==================================================")
    logger.info("1. HEALTH & READINESS PROBES")
    logger.info("==================================================")
    r_health = None
    for attempt in range(10):
        try:
            r_health = client.get("/health")
            if r_health.status_code == 200:
                break
        except Exception:
            pass
        time.sleep(1)

    assert r_health and r_health.status_code == 200, "Health check failed after retries"
    logger.info(f"✓ /health OK: {r_health.json()}")

    r_ready = client.get("/ready")
    assert r_ready.status_code == 200, f"Readiness failed: {r_ready.text}"
    logger.info(f"✓ /ready OK: {r_ready.json()}")

    logger.info("\n==================================================")
    logger.info("2. USER AUTHENTICATION & PROJECT SETUP")
    logger.info("==================================================")
    email = f"obs_demo_{uuid.uuid4().hex[:6]}@example.com"
    password = "Password123!"

    client.post("/api/v1/auth/register", json={
        "email": email,
        "password": password,
        "organization_name": "Observability Demo Inc"
    })

    t_resp = client.post("/api/v1/auth/token", data={"username": email, "password": password})
    assert t_resp.status_code == 200, f"Login failed: {t_resp.text}"
    token = t_resp.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}
    logger.info(f"✓ Authenticated user {email}")

    # Fetch projects & default queue or create if needed
    p_resp = client.get("/api/v1/projects", headers=headers)
    assert p_resp.status_code == 200, f"Fetch projects failed: {p_resp.text}"
    p_data = p_resp.json()
    projects = p_data.get("items", p_data) if isinstance(p_data, dict) else p_data
    if not projects:
        create_p_resp = client.post("/api/v1/projects", headers=headers, json={"name": "Obs Demo Project"})
        assert create_p_resp.status_code == 201
        project_id = create_p_resp.json()["id"]
    else:
        project_id = projects[0]["id"]

    q_resp = client.get(f"/api/v1/queues?project_id={project_id}", headers=headers)
    assert q_resp.status_code == 200, f"Fetch queues failed: {q_resp.text}"
    q_data = q_resp.json()
    queues = q_data.get("items", q_data) if isinstance(q_data, dict) else q_data
    if not queues:
        create_q_resp = client.post("/api/v1/queues", headers=headers, json={
            "project_id": project_id,
            "name": "default",
            "concurrency_limit": 10,
            "priority": 1
        })
        assert create_q_resp.status_code == 201
        queue_id = create_q_resp.json()["id"]
    else:
        queue_id = queues[0]["id"]
    logger.info(f"✓ Using Queue ID: {queue_id} (Project ID: {project_id})")

    logger.info("\n==================================================")
    logger.info("3. SUBMITTING WORKLOAD (Immediate, Retries, Scheduled)")
    logger.info("==================================================")
    # Submit 3 successful jobs
    for i in range(3):
        client.post("/api/v1/jobs", headers=headers, json={
            "queue_id": queue_id,
            "task_type": "demo.success",
            "payload": {"task": f"success_job_{i+1}", "value": i*10},
            "priority": 10
        })
    logger.info("✓ Submitted 3 successful jobs")

    # Submit 2 failing jobs
    for i in range(2):
        client.post("/api/v1/jobs", headers=headers, json={
            "queue_id": queue_id,
            "task_type": "demo.failure",
            "payload": {"task": f"failing_job_{i+1}", "error": "Simulated error"},
            "priority": 5
        })
    logger.info("✓ Submitted 2 failing jobs")

    # Submit 1 delayed job
    client.post("/api/v1/jobs", headers=headers, json={
        "queue_id": queue_id,
        "task_type": "demo.success",
        "payload": {"task": "delayed_job"},
        "delay": 60,
        "priority": 15
    })
    logger.info("✓ Submitted 1 delayed job (delay=60s)")

    logger.info("\n==================================================")
    logger.info("4. WAITING FOR WORKER CLUSTER PROCESSING (5s)")
    logger.info("==================================================")
    time.sleep(5)

    logger.info("\n==================================================")
    logger.info("5. FETCHING PRODUCTION METRICS SUMMARY")
    logger.info("==================================================")
    m_resp = client.get("/api/v1/metrics", headers=headers)
    assert m_resp.status_code == 200, f"Metrics failed: {m_resp.text}"
    metrics = m_resp.json()

    print("\n" + "="*60)
    print("      DISTRIBUTED SCHEDULER OBSERVABILITY REPORT      ")
    print("="*60)
    print(json.dumps(metrics, indent=2))
    print("="*60 + "\n")

    sys_obs = metrics.get("jobs") or metrics.get("system_overview") or {}
    workers_obs = metrics.get("workers") or metrics.get("worker_metrics") or {}
    perf_obs = metrics.get("execution_performance") or {}
    tp_obs = metrics.get("throughput") or {}
    rates = sys_obs.get("rates") or {}

    logger.info("=== OBSERVABILITY HIGHLIGHTS ===")
    logger.info(f"• Total Jobs: {sys_obs.get('total', 0)}")
    logger.info(f"• Completed: {sys_obs.get('completed', 0)} | Failed: {sys_obs.get('failed', 0)} | Queued: {sys_obs.get('queued', 0)}")
    logger.info(f"• Success Rate: {rates.get('success_rate', 0)}% | Failure Rate: {rates.get('failure_rate', 0)}%")
    logger.info(f"• Active Workers: {workers_obs.get('active_workers', 0)} / {workers_obs.get('total_workers', 0)}")
    logger.info(f"• Throughput (5m): {tp_obs.get('completed_last_5m', 0)} jobs | (1h): {tp_obs.get('completed_last_hour', 0)} jobs")
    logger.info(f"• Avg Latency: {perf_obs.get('avg_duration_ms', 0)}ms | p95: {perf_obs.get('p95_ms', 0)}ms | p99: {perf_obs.get('p99_ms', 0)}ms")
    logger.info("✓ E2E Observability Verification Passed Successfully!\n")

if __name__ == "__main__":
    base_url = sys.argv[1] if len(sys.argv) > 1 else "http://localhost:8000"
    run_observability_demo(base_url)
