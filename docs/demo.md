# RunGrid — Acme Cloud Demo & Verification Guide

This guide provides step-by-step instructions for launching and demonstrating the **RunGrid** platform with the realistic **Acme Cloud** multi-tenant demo workload.

---

## 1. Quick Start with Docker Compose

Ensure Docker and Docker Compose are installed, then build and start all service containers:

```bash
# Build and launch PostgreSQL, FastAPI Backend, 2 Worker nodes, and Prometheus
docker compose up -d --build

# Verify container health status
docker compose ps
```

Services will be accessible at:
- **RunGrid Dashboard UI**: `http://localhost:3000` (or `http://localhost:5173`)
- **FastAPI Control Plane**: `http://localhost:8000`
- **Swagger API Docs**: `http://localhost:8000/docs`
- **Prometheus UI**: `http://localhost:9090`

---

## 2. Seed Acme Cloud Demo Dataset

Run the automated seeding script to populate the Acme Cloud organization with projects, queues, workers, recurring cron schedules, batch tasks, and 24 sample jobs spanning all states:

```bash
.venv/bin/python scripts/seed_demo.py
```

To verify dataset state at any time:

```bash
.venv/bin/python scripts/seed_demo.py --check
```

Expected output summary:
```text
Organization: Acme Cloud
Project:      Customer Operations
Queues Found: 5 (emails, notifications, reports, media-processing, default)
Total Seeded Jobs: 24
  - QUEUED: 11
  - SCHEDULED: 1
  - RUNNING: 1
  - RETRY_WAITING: 3
  - COMPLETED: 8
```

---

## 3. Demo Scenarios

### Scenario A: Login & Dashboard Overview
1. Open `http://localhost:3000/login`.
2. Click **Owner Persona** (`owner@demo.com` / `Password123!`).
3. Click **Sign In to Acme Cloud**.
4. Observe real-time job counters (Total Jobs: 24, Queued: 11, Completed: 8, Retrying: 3, Running: 1), Recent Workloads, and dynamic Reliability Feed.

### Scenario B: Prometheus Observability Telemetry
1. Navigate to **Platform → Observability** (`/platform/observability`).
2. Observe the live throughput waveform chart updating continuously.
3. View P50, P95, P99 execution latency percentiles and queue concurrency saturation meters.

### Scenario C: Workflows & Dependency DAG
1. Navigate to **Platform → Workflows** (`/platform/workflows`).
2. Inspect the dependency chain: `Send Welcome Email` → `Generate Operations Report` → `Sync Customer Profile`.
3. Verify that child jobs remain blocked until parent execution succeeds.

### Scenario D: Batch Job Submissions & Rollback
1. Navigate to **Platform → Batches** (`/platform/batches`).
2. Click **Submit New Atomic Batch**.
3. Submit 4 onboarding tasks simultaneously and verify atomic single-transaction commit.

---

## 4. Teardown

To gracefully stop running containers without losing database volume state:

```bash
docker compose down
```
