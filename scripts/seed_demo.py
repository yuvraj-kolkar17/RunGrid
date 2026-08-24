#!/usr/bin/env python3
"""
Phase 8 — Reproducible & Idempotent Demo Seeding Script.

Scenario: "Acme Cloud" (Customer Operations)

Usage:
  python scripts/seed_demo.py          # Seeds the Phase 8 Acme Cloud demo dataset
  python scripts/seed_demo.py --check  # Reports whether Phase 8 dataset exists without making changes
"""

import sys
import argparse
import logging
import httpx

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("seed_demo")

DEMO_MARKER = "phase8-v1"
DEMO_ORG_NAME = "Acme Cloud"
DEMO_PROJECT_NAME = "Customer Operations"
DEMO_EMAIL = "owner@demo.com"
DEMO_PASS = "Password123!"

import os

INTERNAL_KEY = os.getenv("INTERNAL_API_KEY", "internal-worker-secret-key")
BASE_URL = "http://localhost:8000"

def get_auth_token(client: httpx.Client) -> str:
    # 1. Try login first
    login_resp = client.post("/api/v1/auth/token", data={"username": DEMO_EMAIL, "password": DEMO_PASS})
    if login_resp.status_code == 200:
        return login_resp.json()["access_token"]
    
    # 2. Register if user doesn't exist
    reg_resp = client.post("/api/v1/auth/register", json={
        "email": DEMO_EMAIL,
        "password": DEMO_PASS,
        "organization_name": DEMO_ORG_NAME
    })
    if reg_resp.status_code in (200, 201):
        login_resp = client.post("/api/v1/auth/token", data={"username": DEMO_EMAIL, "password": DEMO_PASS})
        if login_resp.status_code == 200:
            return login_resp.json()["access_token"]
            
    raise RuntimeError(f"Authentication failed: {login_resp.text}")

def check_demo_dataset(client: httpx.Client, headers: dict) -> bool:
    """Checks if Phase 8 dataset exists and prints a status summary."""
    logger.info("=== CHECKING PHASE 8 DEMO DATASET STATUS ===")
    
    # Check queues
    queues_resp = client.get("/api/v1/queues", headers=headers)
    raw_q = queues_resp.json() if queues_resp.status_code == 200 else {}
    queues = raw_q.get("items", raw_q) if isinstance(raw_q, dict) else raw_q
    queue_names = [q["name"] for q in queues if isinstance(q, dict)]
    
    # Check jobs
    jobs_resp = client.get("/api/v1/jobs?page_size=100", headers=headers)
    raw_j = jobs_resp.json() if jobs_resp.status_code == 200 else {}
    jobs = raw_j.get("items", raw_j) if isinstance(raw_j, dict) else raw_j
    
    demo_jobs = [j for j in jobs if isinstance(j, dict) and ((j.get("payload") or {}).get("demo_marker") == DEMO_MARKER or (j.get("payload") or {}).get("demo_id") == DEMO_MARKER)]
    
    target_queues = {"emails", "reports", "media-processing", "notifications"}
    has_target_queues = target_queues.issubset(set(queue_names))
    
    status_counts = {}
    for j in demo_jobs:
        st = j["status"]
        status_counts[st] = status_counts.get(st, 0) + 1
        
    print(f"\n--- Phase 8 Dataset Summary ({DEMO_MARKER}) ---")
    print(f"Organization: {DEMO_ORG_NAME}")
    print(f"Project:      {DEMO_PROJECT_NAME}")
    print(f"Queues Found: {len(queues)} ({', '.join(queue_names)})")
    print(f"Total Seeded Jobs: {len(demo_jobs)}")
    for st, count in status_counts.items():
        print(f"  - {st}: {count}")
    print("-------------------------------------------\n")
    
    return has_target_queues and len(demo_jobs) >= 15

def run_seed(base_url: str = BASE_URL):
    with httpx.Client(base_url=base_url, timeout=15.0) as client:
        # Check backend readiness
        health = client.get("/health")
        if health.status_code != 200:
            logger.error("Backend health check failed. Ensure FastAPI is running on port 8000.")
            sys.exit(1)
            
        token = get_auth_token(client)
        headers = {"Authorization": f"Bearer {token}"}
        internal_headers = {"X-Internal-Key": INTERNAL_KEY}
        
        # 1. Project Creation / Discovery
        proj_id = None
        projects_resp = client.get("/api/v1/projects", headers=headers)
        if projects_resp.status_code == 200:
            raw_p = projects_resp.json()
            proj_items = raw_p.get("items", raw_p) if isinstance(raw_p, dict) else raw_p
            if isinstance(proj_items, list):
                for p in proj_items:
                    if p.get("name") == DEMO_PROJECT_NAME:
                        proj_id = p["id"]
                        break
                    
        if not proj_id:
            res_p = client.post("/api/v1/projects", json={"name": DEMO_PROJECT_NAME}, headers=headers)
            proj_id = res_p.json()["id"]
            logger.info(f"Created Project '{DEMO_PROJECT_NAME}' (ID: {proj_id})")
        else:
            logger.info(f"Reusing existing Project '{DEMO_PROJECT_NAME}' (ID: {proj_id})")
            
        # 2. Queues Setup
        desired_queues = [
            {"name": "emails", "priority": 10, "concurrency_limit": 3},
            {"name": "reports", "priority": 7, "concurrency_limit": 2},
            {"name": "media-processing", "priority": 5, "concurrency_limit": 4},
            {"name": "notifications", "priority": 8, "concurrency_limit": 3},
        ]
        
        queues_by_name = {}
        existing_q_resp = client.get("/api/v1/queues", headers=headers)
        if existing_q_resp.status_code == 200:
            raw_q = existing_q_resp.json()
            existing_qs = raw_q.get("items", raw_q) if isinstance(raw_q, dict) else raw_q
            if isinstance(existing_qs, list):
                for q in existing_qs:
                    queues_by_name[q["name"]] = q["id"]
            
        for dq in desired_queues:
            if dq["name"] not in queues_by_name:
                res_q = client.post("/api/v1/queues", json={
                    "project_id": proj_id,
                    "name": dq["name"],
                    "priority": dq["priority"],
                    "concurrency_limit": dq["concurrency_limit"]
                }, headers=headers)
                queues_by_name[dq["name"]] = res_q.json()["id"]
                logger.info(f"Created Queue '{dq['name']}' (ID: {queues_by_name[dq['name']]})")
            else:
                logger.info(f"Reusing existing Queue '{dq['name']}' (ID: {queues_by_name[dq['name']]})")
                
        # 3. Check if demo jobs are already seeded
        jobs_check = client.get("/api/v1/jobs?page_size=100", headers=headers)
        raw_j = jobs_check.json() if jobs_check.status_code == 200 else {}
        existing_jobs = raw_j.get("items", raw_j) if isinstance(raw_j, dict) else raw_j
        existing_demo_jobs = [j for j in existing_jobs if isinstance(j, dict) and ((j.get("payload") or {}).get("demo_marker") == DEMO_MARKER or (j.get("payload") or {}).get("demo_id") == DEMO_MARKER)]
        
        if len(existing_demo_jobs) >= 15:
            logger.info(f"Phase 8 dataset already seeded ({len(existing_demo_jobs)} jobs found). Skipping re-creation.")
            return
            
        logger.info("=== SEEDING PHASE 8 DEMO DATASET ===")
        
        # Helper worker for lifecycle transitions
        worker_reg = client.post("/api/v1/internal/workers/register", json={
            "hostname": "seed-worker-daemon",
            "ip_address": "127.0.0.1"
        }, headers=internal_headers)
        seed_worker_id = worker_reg.json()["id"]
        
        # ----------------------------------------------------
        # A. COMPLETED JOBS (8 jobs)
        # ----------------------------------------------------
        completed_defs = [
            ("emails", "email.send", {"recipient": "alex@example.com", "template": "welcome", "customer_id": "CUS-1001", "demo_marker": DEMO_MARKER}),
            ("emails", "email.send", {"recipient": "sarah@example.com", "template": "password_reset", "customer_id": "CUS-1002", "demo_marker": DEMO_MARKER}),
            ("notifications", "notification.send", {"customer_id": "CUS-1042", "order_id": "ORD-7821", "channel": "email", "demo_marker": DEMO_MARKER}),
            ("reports", "report.generate", {"report": "daily_sales", "date": "2026-08-23", "demo_marker": DEMO_MARKER}),
            ("reports", "report.generate", {"report": "monthly_revenue", "month": "2026-08", "demo_marker": DEMO_MARKER}),
            ("media-processing", "image.process", {"operation": "resize", "image_count": 24, "target_size": "1200x1200", "demo_marker": DEMO_MARKER}),
            ("emails", "customer.sync", {"customer_id": "CUS-1088", "source": "crm", "demo_marker": DEMO_MARKER}),
            ("reports", "invoice.generate", {"invoice_id": "INV-8801", "amount": 1250.00, "demo_marker": DEMO_MARKER}),
        ]
        
        for q_name, task_type, payload in completed_defs:
            q_id = queues_by_name[q_name]
            j = client.post("/api/v1/jobs", json={
                "queue_id": q_id,
                "task_type": task_type,
                "payload": payload,
                "priority": 5
            }, headers=headers).json()
            
            # Execute through real API transitions
            client.post(f"/api/v1/internal/jobs/{j['id']}/start", json={"worker_id": seed_worker_id}, headers=internal_headers)
            client.post(f"/api/v1/internal/jobs/{j['id']}/complete", json={
                "worker_id": seed_worker_id,
                "result": {"status": "simulated", "message": f"{task_type} completed successfully", "data": payload}
            }, headers=internal_headers)
            
        logger.info("Successfully seeded 8 COMPLETED jobs.")
        
        # ----------------------------------------------------
        # B. RETRY_WAITING JOBS (2 jobs)
        # ----------------------------------------------------
        retry_defs = [
            ("reports", "report.generate", {"report": "customer_audit", "simulate_failure": "transient", "demo_marker": DEMO_MARKER}),
            ("emails", "customer.sync", {"customer_id": "CUS-2040", "simulate_failure": "transient", "demo_marker": DEMO_MARKER}),
        ]
        
        for q_name, task_type, payload in retry_defs:
            q_id = queues_by_name[q_name]
            j = client.post("/api/v1/jobs", json={
                "queue_id": q_id,
                "task_type": task_type,
                "payload": payload,
                "max_retries": 3,
                "priority": 5
            }, headers=headers).json()
            
            client.post(f"/api/v1/internal/jobs/{j['id']}/start", json={"worker_id": seed_worker_id}, headers=internal_headers)
            client.post(f"/api/v1/internal/jobs/{j['id']}/fail", json={
                "worker_id": seed_worker_id,
                "error_message": "Transient database timeout (attempt 1 failed)"
            }, headers=internal_headers)
            
        logger.info("Successfully seeded 2 RETRY_WAITING jobs.")
        
        # ----------------------------------------------------
        # C. DEAD_LETTER JOB (1 job)
        # ----------------------------------------------------
        dlq_payload = {"customer_id": "INVALID-DEMO-CUSTOMER", "simulate_failure": "permanent", "demo_marker": DEMO_MARKER}
        j_dlq = client.post("/api/v1/jobs", json={
            "queue_id": queues_by_name["emails"],
            "task_type": "customer.sync",
            "payload": dlq_payload,
            "max_retries": 1,
            "priority": 5
        }, headers=headers).json()
        
        client.post(f"/api/v1/internal/jobs/{j_dlq['id']}/start", json={"worker_id": seed_worker_id}, headers=internal_headers)
        client.post(f"/api/v1/internal/jobs/{j_dlq['id']}/fail", json={
            "worker_id": seed_worker_id,
            "error_message": "Fatal: Invalid customer schema record (retries exhausted)"
        }, headers=internal_headers)
        
        logger.info("Successfully seeded 1 DEAD_LETTER job.")
        
        # ----------------------------------------------------
        # D. RUNNING JOB (1 job)
        # ----------------------------------------------------
        j_run = client.post("/api/v1/jobs", json={
            "queue_id": queues_by_name["reports"],
            "task_type": "report.generate",
            "payload": {"report": "quarterly_financial_consolidation", "duration": 120, "demo_marker": DEMO_MARKER},
            "priority": 5
        }, headers=headers).json()
        
        client.post(f"/api/v1/internal/jobs/{j_run['id']}/start", json={"worker_id": seed_worker_id}, headers=internal_headers)
        logger.info("Successfully seeded 1 RUNNING job.")
        
        # ----------------------------------------------------
        # E. QUEUED JOBS (4 jobs)
        # ----------------------------------------------------
        queued_defs = [
            ("emails", "email.send", {"recipient": "david@example.com", "template": "onboarding_step_1", "demo_marker": DEMO_MARKER}),
            ("notifications", "notification.send", {"customer_id": "CUS-9912", "channel": "push", "demo_marker": DEMO_MARKER}),
            ("media-processing", "image.process", {"operation": "watermark", "image_count": 50, "demo_marker": DEMO_MARKER}),
            ("reports", "report.generate", {"report": "weekly_analytics", "demo_marker": DEMO_MARKER}),
        ]
        
        for q_name, task_type, payload in queued_defs:
            client.post("/api/v1/jobs", json={
                "queue_id": queues_by_name[q_name],
                "task_type": task_type,
                "payload": payload,
                "priority": 3
            }, headers=headers)
            
        logger.info("Successfully seeded 4 QUEUED jobs.")
        
        # ----------------------------------------------------
        # F. SCHEDULED / CRON JOBS (3 jobs)
        # ----------------------------------------------------
        # Delayed job
        client.post("/api/v1/jobs", json={
            "queue_id": queues_by_name["emails"],
            "task_type": "email.send",
            "payload": {"recipient": "scheduled_user@example.com", "template": "followup", "demo_marker": DEMO_MARKER},
            "delay": 3600
        }, headers=headers)
        
        # Cron recurring schedules
        cron_defs = [
            ("Daily Sales Report Cron", "0 0 * * *", "report.generate", {"report": "daily_sales"}),
            ("Nightly Customer Synchronization Cron", "0 2 * * *", "customer.sync", {"source": "nightly_batch"}),
        ]
        
        for cron_name, expr, task_type, p in cron_defs:
            client.post("/api/v1/jobs/scheduled", json={
                "project_id": proj_id,
                "queue_id": queues_by_name["reports"],
                "name": cron_name,
                "cron_expression": expr,
                "payload": {**p, "demo_marker": DEMO_MARKER, "task_type": task_type}
            }, headers=headers)
            
        logger.info("Successfully seeded 3 SCHEDULED / Cron jobs.")
        
        # ----------------------------------------------------
        # G. WORKFLOW DEPENDENCY CHAIN (A -> B -> C)
        # ----------------------------------------------------
        job_a = client.post("/api/v1/jobs", json={
            "queue_id": queues_by_name["reports"],
            "task_type": "report.generate",
            "payload": {"report": "sales_data_extract", "demo_marker": DEMO_MARKER},
            "priority": 5
        }, headers=headers).json()
        
        job_b = client.post("/api/v1/jobs", json={
            "queue_id": queues_by_name["reports"],
            "task_type": "report.generate",
            "payload": {"report": "management_summary", "demo_marker": DEMO_MARKER},
            "priority": 5
        }, headers=headers).json()
        
        job_c = client.post("/api/v1/jobs", json={
            "queue_id": queues_by_name["notifications"],
            "task_type": "notification.send",
            "payload": {"channel": "slack", "customer_id": "EXEC-99", "demo_marker": DEMO_MARKER},
            "priority": 5
        }, headers=headers).json()
        
        # B depends on A
        client.post(f"/api/v1/jobs/{job_b['id']}/dependencies", json={"depends_on_job_id": job_a["id"]}, headers=headers)
        # C depends on B
        client.post(f"/api/v1/jobs/{job_c['id']}/dependencies", json={"depends_on_job_id": job_b["id"]}, headers=headers)
        
        logger.info(f"Successfully created workflow dependency chain: Job A ({job_a['id'][:8]}) -> Job B ({job_b['id'][:8]}) -> Job C ({job_c['id'][:8]}).")
        
        # ----------------------------------------------------
        # H. ATOMIC BATCH JOB SUBMISSION
        # ----------------------------------------------------
        client.post("/api/v1/jobs/batch", json={
            "jobs": [
                {"queue_id": queues_by_name["emails"], "task_type": "email.send", "payload": {"template": "welcome", "recipient": "onboarding_1@example.com", "demo_marker": DEMO_MARKER}, "priority": 5, "max_retries": 3},
                {"queue_id": queues_by_name["emails"], "task_type": "customer.sync", "payload": {"customer_id": "ONBD-101", "demo_marker": DEMO_MARKER}, "priority": 5, "max_retries": 3},
                {"queue_id": queues_by_name["notifications"], "task_type": "notification.send", "payload": {"channel": "sms", "customer_id": "ONBD-101", "demo_marker": DEMO_MARKER}, "priority": 5, "max_retries": 3},
                {"queue_id": queues_by_name["reports"], "task_type": "report.generate", "payload": {"report": "initial_account_audit", "demo_marker": DEMO_MARKER}, "priority": 5, "max_retries": 3},
            ]
        }, headers=headers)
        
        logger.info("Successfully submitted Onboarding Atomic Batch Jobs (4 tasks).")
        
        logger.info("=== PHASE 8 DEMO SEEDING COMPLETED SUCCESSFULLY ===")

def main():
    parser = argparse.ArgumentParser(description="Phase 8 Acme Cloud Demo Data Seeder")
    parser.add_argument("--check", action="store_true", help="Check if Phase 8 dataset exists without making changes")
    parser.add_argument("--url", default=BASE_URL, help="Backend API base URL (default: http://localhost:8000)")
    args = parser.parse_args()
    
    if args.check:
        with httpx.Client(base_url=args.url, timeout=10.0) as client:
            token = get_auth_token(client)
            headers = {"Authorization": f"Bearer {token}"}
            check_demo_dataset(client, headers)
    else:
        run_seed(args.url)

if __name__ == "__main__":
    main()
