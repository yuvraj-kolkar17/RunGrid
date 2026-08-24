# RunGrid

## Distributed Job Orchestration Platform

![Python](https://img.shields.io/badge/Python-3.12-blue.svg)
![FastAPI](https://img.shields.io/badge/FastAPI-0.109-009688.svg)
![PostgreSQL](https://img.shields.io/badge/PostgreSQL-15-336791.svg)
![React](https://img.shields.io/badge/React-19-61DAFB.svg)
![TypeScript](https://img.shields.io/badge/TypeScript-5.0-3178C6.svg)
![Docker](https://img.shields.io/badge/Docker-Compose-2496ED.svg)
![Prometheus](https://img.shields.io/badge/Prometheus-Observability-E6522C.svg)

RunGrid is a production-inspired distributed job orchestration platform for scheduling, executing, monitoring, retrying, and recovering background workloads across multiple workers.

---

## Table of Contents

- [Product Overview](#1-product-overview)
- [Key Features](#2-key-features)
- [Product Screenshots](#3-product-screenshots)
- [Demo Login](#4-demo-login)
- [Architecture](#5-architecture)
- [Job Lifecycle & State Machine](#6-job-lifecycle--state-machine)
- [Atomic Claiming](#7-atomic-claiming-via-for-update-skip-locked)
- [Retry System](#8-retry-system--backoff-strategies)
- [Worker Architecture](#9-worker-architecture--safety)
- [Prometheus Observability](#10-prometheus-observability)
- [Platform Operations Center](#11-platform-operations-center)
- [Database Schema Overview](#12-database-schema-overview)
- [Project Structure](#13-project-structure)
- [Local Development Setup](#14-local-development-setup)
- [Docker Deployment](#15-docker-deployment)
- [Demo Environment](#16-demo-environment-acme-cloud)
- [Testing & Verification](#17-testing--verification)
- [Documentation](#18-documentation)
- [Security Policy](#19-security-policy)
- [System Trade-offs & Limitations](#20-system-trade-offs--limitations)
- [Future Roadmap](#21-future-roadmap)
- [License](#22-license)

---

## 1. Product Overview

In modern application engineering, background processes such as sending transactional emails, generating PDF reports, processing video/image assets, calculating invoices, or synchronizing third-party APIs must be offloaded from web request threads to maintain fast UI responsiveness and system reliability.

RunGrid manages background work that should not block an application. Jobs are placed into prioritized queues, distributed workers claim them safely via PostgreSQL row locking, execute task logic, report telemetry, and recover failed or stranded work through automated leases and exponential retries.

### Example Real-World Use Case

An e-commerce platform processing a customer checkout:
1. **Immediate Job**: Generate invoice PDF and send welcome email.
2. **Delayed Job**: Trigger fulfillment notification 10 minutes later.
3. **Workflow DAG**: Process item images → Update inventory → Sync CRM profile.
4. **Batch Jobs**: Atomic bulk import of 500 customer records in a single transaction.

Instead of running these tasks synchronously inside the web request, RunGrid schedules the work, guarantees at-least-once execution, and exposes real-time telemetry through an operator dashboard.

---

## 2. Key Features

### Core Execution Engine
- **Multi-Tenant Isolation**: Multi-organization boundary isolation across projects, users, and queues.
- **Priority Queuing**: Multi-queue prioritization with configurable per-queue concurrency limits.
- **Queue Controls**: Pause and resume processing on specific queues dynamically.
- **Execution Modes**: Immediate execution, delayed execution offsets (`delay` seconds), cron recurring schedules, and atomic batch jobs.
- **Atomic Claiming**: Zero global locks using PostgreSQL `FOR UPDATE SKIP LOCKED`.
- **Worker Management**: Dynamic worker registration, capacity reporting, and 5-second periodic heartbeats.
- **Lease-Based Fault Recovery**: Automated Reaper daemon that re-queues expired or stranded jobs.
- **Retry Policies**: Fixed, Linear, and Exponential backoff strategies with Dead Letter Queue (DLQ) routing.
- **Workflow DAG Dependencies**: Cycle detection via DFS with parent-child dependency tracking.

### Security & Access Control
- **Authentication**: OAuth2 Password Bearer JWT tokens with `bcrypt` password hashing.
- **Role-Based Access Control (RBAC)**: Enforced role hierarchy (`OWNER`, `ADMIN`, `MEMBER`, `VIEWER`).
- **Internal Worker Auth**: Authenticated worker REST protocol using `X-Internal-Key` headers.
- **API Rate Limiting**: In-memory sliding-window rate limiting on public endpoints.

### Production Observability
- **Prometheus Metrics**: Built-in `prometheus-client` exporter tracking HTTP rates, job execution counts, queue utilization, reaper recoveries, and latency percentiles (`p50`, `p95`, `p99`).
- **Real-Time Telemetry Dashboard**: Continuously updating area charts, active worker topography maps, and dynamic reliability feeds.

---

## 3. Product Screenshots

RunGrid provides an operations-focused interface for managing distributed background workloads, queues, workers, workflows, failures, and system observability.

### Authentication
<p align="center">
  <img src="docs/screenshots/01-login.png" alt="RunGrid Authentication" width="100%">
</p>

*Secure JWT-based authentication with role-aware access and persona quick-fill for testing.*

---

### Operations Dashboard
<p align="center">
  <img src="docs/screenshots/02-dashboard.png" alt="RunGrid Operations Dashboard" width="100%">
</p>

*The dashboard provides a high-level view of workload execution, queue health, worker capacity, throughput, reliability activity, and system metrics.*

---

### Job Submission
<p align="center">
  <img src="docs/screenshots/03-job-creation.png" alt="RunGrid Job Submission" width="100%">
</p>

*Jobs can be submitted as immediate, delayed, scheduled, recurring, or batch workloads through the RunGrid API and dashboard.*

---

### Platform Operations Center
<p align="center">
  <img src="docs/screenshots/08-platform-overview.png" alt="RunGrid Platform Operations Overview" width="100%">
</p>

*The Platform Operations Center provides centralized control and operational tooling for batch jobs, workflow DAGs, API rate limits, and failure diagnostics.*

---

### API Rate Limiting
<p align="center">
  <img src="docs/screenshots/12-rate-limiting.png" alt="RunGrid API Rate Limiting" width="100%">
</p>

*RunGrid exposes operational visibility into API rate limiting, including thread-safe sliding window metrics, endpoint policies, and interactive limit testing.*

---

## 4. Demo Login

To explore the pre-seeded **Acme Cloud** multi-tenant demo environment:

- **Email**: `owner@demo.com`
- **Password**: `Password123!`
- **Role**: `OWNER`
- **Organization**: `Acme Cloud`
- **Project**: `Customer Operations`

> **Note**: `Password123!` is an intentional pre-configured demo credential provisioned by `scripts/seed_demo.py` for local application evaluation and UI testing.

---

## 5. Architecture

```
                    ┌─────────────────────────┐
                    │     React UI / CLI      │
                    │   RunGrid Dashboard     │
                    └────────────┬────────────┘
                                 │ REST (JWT Auth)
                                 ▼
                    ┌─────────────────────────┐
                    │     FastAPI Backend     │
                    │ (Auth / Jobs / Queues)  │
                    └────────────┬────────────┘
                                 │
              ┌──────────────────┼──────────────────┐
              ▼                  ▼                  ▼
     ┌────────────────┐  ┌───────────────┐  ┌────────────────┐
     │   PostgreSQL   │  │  Prometheus   │  │   Scheduler &  │
     │ FOR UPDATE SKIP│  │ Metrics Store │  │ Reaper Service │
     │     LOCKED     │  └───────▲───────┘  └────────────────┘
     └───────▲────────┘          │
             │                   │ Expose Metrics
             └───────────┬───────┴────────┐
                         │ REST           │
                         ▼                ▼
                  ┌────────────┐   ┌────────────┐
                  │ Worker 1   │   │ Worker 2   │
                  └────────────┘   └────────────┘
```

- **React Dashboard**: Modern web console for job management, queue monitoring, batch submission, and Prometheus telemetry.
- **FastAPI Control Plane**: Python REST API enforcing tenant isolation, RBAC, state transitions, and metrics export.
- **PostgreSQL Database**: Single source of truth for jobs, queues, locks, leases, and worker registries.
- **Distributed Worker Daemons**: Stateless multi-threaded processes that claim and execute task handlers.
- **Scheduler & Reaper**: Control daemons managing cron promotions and recovering stranded jobs.
- **Prometheus**: Monitoring infrastructure scraping operational metrics every 5 seconds.

---

## 6. Job Lifecycle & State Machine

```
                  ┌───────────────┐
                  │   SCHEDULED   │ (Cron / Delayed)
                  └───────┬───────┘
                          │ (Scheduler / Delay Elapsed)
                          ▼
                  ┌───────────────┐
                  │    QUEUED     │ <────────────┐
                  └───────┬───────┘              │
                          │ (Worker Claim)       │
                          ▼                      │
                  ┌───────────────┐              │ (Reaper Recovery /
                  │    CLAIMED    │              │  Retry Backoff)
                  └───────┬───────┘              │
                          │ (Worker Start)       │
                          ▼                      │
                  ┌───────────────┐              │
                  │    RUNNING    ├──────────────┘
                  └───┬───────┬───┘
                      │       │
            (Success) │       │ (Max Retries Exceeded)
                      ▼       ▼
           ┌───────────┐     ┌───────────────┐
           │ COMPLETED │     │  DEAD_LETTER  │
           └───────────┘     └───────────────┘
```

### Attempt Semantics & Lease Expiration

- **`QUEUED` → `CLAIMED`**: Worker claims job row. `lease_expires_at` is set. Attempt counter remains `N`.
- **`CLAIMED` → `RUNNING`**: Worker begins task execution. Attempt counter increments (`attempt += 1`).
- **`RUNNING` → `COMPLETED`**: Successful completion. Result saved, lease cleared.
- **`RUNNING` → `RETRY_WAITING`**: Execution failure with retries remaining. Backoff delay calculated and `available_at` updated.
- **`RUNNING` → `DEAD_LETTER`**: Execution failure with max retries exceeded. Job archived in DLQ.
- **Lease Expiration**: If worker crashes, Reaper re-queues expired jobs without double-incrementing attempt counters.

---

## 7. Atomic Claiming via `FOR UPDATE SKIP LOCKED`

RunGrid handles concurrent worker polling across queues using PostgreSQL row-level skip locks:

```sql
SELECT j.id
FROM jobs j
JOIN queues q ON j.queue_id = q.id
WHERE j.status = 'QUEUED'
  AND j.available_at <= NOW()
  AND q.is_paused = FALSE
ORDER BY q.priority DESC, j.priority DESC, j.created_at ASC
FOR UPDATE SKIP LOCKED
LIMIT 1;
```

This prevents race conditions and lock contention, allowing multiple worker threads to poll simultaneously without blocking.

---

## 8. Retry System & Backoff Strategies

RunGrid supports three configurable retry strategies:

1. **Fixed Backoff**: Constant delay between retries.
   - Example (`base_delay = 5s`): `5s, 5s, 5s`
2. **Linear Backoff**: Delay increases linearly with attempts.
   - Example (`base_delay = 5s`): `5s, 10s, 15s`
3. **Exponential Backoff**: Delay doubles exponentially with attempts.
   - Example (`base_delay = 5s`): `5s, 10s, 20s, 40s`

---

## 9. Worker Architecture & Safety

- **Task Registry**: Predefined Python functions mapped to `task_type` strings. No dynamic code evaluation (`eval`/`exec`) is permitted.
- **Heartbeats**: Workers report active concurrency capacity every 5 seconds.
- **Graceful Shutdown**: On `SIGINT`/`SIGTERM`, workers finish running tasks before exiting.

---

## 10. Prometheus Observability

Backend metrics exported at `/metrics`:
- `rungrid_http_requests_total`: Counter by route, method, status code.
- `rungrid_jobs_total`: Gauge by status.
- `rungrid_job_execution_duration_seconds`: Histogram of task latency.
- `rungrid_reaper_recovered_jobs_total`: Counter of recovered jobs.

---

## 11. Platform Operations Center

Accessible via the React Dashboard:
- **Dashboard Overview**: KPI cards, recent workloads table, reliability feed.
- **Prometheus Telemetry**: Live throughput charts, latency percentiles, queue saturation gauges.
- **Batch Jobs**: Atomic multi-task submission and history.
- **Workflow DAG**: Visual tree of dependent jobs and cycle detection.
- **Failure Analysis**: Root-cause categorization of DLQ jobs.

---

## 12. Database Schema Overview

Primary database tables:
- `organizations`, `users`, `projects`
- `queues`, `retry_policies`, `jobs`
- `scheduled_jobs`, `workers`, `worker_heartbeats`
- `job_executions`, `job_logs`, `dead_letter_jobs`
- `job_dependencies`, `batch_submissions`

---

## 13. Project Structure

```text
RunGrid/
├── backend/
│   ├── app/
│   │   ├── core/         # Config, Database, Security, Rate Limiting
│   │   ├── models/       # SQLAlchemy Data Models
│   │   ├── routers/      # REST API Routers (Auth, Jobs, Queues, Metrics)
│   │   ├── schemas/      # Pydantic Request/Response Models
│   │   ├── services/     # Claiming, Transitions, Scheduler, Reaper
│   │   └── main.py       # FastAPI Application Entrypoint
│   └── tests/            # Pytest Suite
├── worker/
│   ├── app/              # Worker Daemon, Polling Loop, Task Registry
│   └── tests/            # Worker Unit Tests
├── frontend/             # React 19 + TypeScript + Tailwind CSS UI
├── database/             # Alembic Database Migrations
├── docs/
│   └── screenshots/      # Product Screenshots
├── monitoring/           # Prometheus Scraping Configuration
├── scripts/              # Demo Seeding & Benchmark Utilities
└── docker-compose.yml    # Container Orchestration Specification
```

---

## 14. Local Development Setup

### Prerequisites
- Python 3.12+
- Node.js 18+ & npm
- PostgreSQL 15+ (if running without Docker)

### Installation Steps

1. **Clone Repository**:
   ```bash
   git clone https://github.com/yuvraj-kolkar17/RunGrid.git
   cd RunGrid
   ```

2. **Backend Setup**:
   ```bash
   python -m venv .venv
   source .venv/bin/activate
   pip install -r backend/requirements.txt
   ```

3. **Frontend Setup**:
   ```bash
   cd frontend
   npm install
   ```

4. **Environment File**:
   ```bash
   cp .env.example .env
   ```

---

## 15. Docker Deployment

Launch the complete stack with Docker Compose:

```bash
docker compose up -d --build
```

Services started:
- `postgres` (PostgreSQL 15 on port `5432` / host `5433`)
- `backend` (FastAPI Control Plane on port `8000`)
- `worker-1`, `worker-2` (Distributed Workers)
- `prometheus` (Prometheus Server on port `9090`)

Shutdown containers:
```bash
docker compose down
```

---

## 16. Demo Environment (Acme Cloud)

Seed the Acme Cloud dataset with sample jobs, queues, cron schedules, and workflows:

```bash
.venv/bin/python scripts/seed_demo.py
```

Verify dataset summary:
```bash
.venv/bin/python scripts/seed_demo.py --check
```

Access the UI at `http://localhost:3000` and sign in with the **Owner Persona** (`owner@demo.com` / `Password123!`).

---

## 17. Testing & Verification

Run the backend test suite inside the container environment:

```bash
# Run pytest backend test suite
docker compose exec backend pytest backend/tests/

# Type checking
mypy --explicit-package-bases backend worker

# Compile python source
python -m compileall backend worker scripts

# Build frontend production bundle
cd frontend && npm run build
```

---

## 18. Documentation

- [System Architecture](docs/architecture.md)
- [Database Schema & State Machine](docs/database.md)
- [REST API Specification](docs/api.md)
- [Worker Architecture](docs/worker.md)
- [Reliability & Fault Tolerance](docs/reliability.md)
- [Prometheus Observability](docs/observability.md)
- [Key Engineering Design Decisions](docs/design-decisions.md)
- [Acme Cloud Demo Guide](docs/demo.md)
- [Deployment & Operations Guide](docs/deployment.md)
- [Security Architecture](docs/security.md)

---

## 19. Security Policy

- OAuth2 Bearer Tokens (JWT) for authentication.
- Scoped tenant isolation via `organization_id`.
- Secret sanitization in JSON logs.
- Never commit `.env` files or real production credentials.

---

## 20. System Trade-offs & Limitations

- **At-Least-Once Execution**: Handlers must be written to be idempotent.
- **In-Memory Rate Limiting**: Default rate limiter operates process-locally.
- **Predefined Task Handlers**: Dynamic unvetted code execution is rejected by design for security.

---

## 21. Future Roadmap

- Redis-backed distributed rate limiting.
- WebSocket / Server-Sent Events (SSE) live updates.
- Kubernetes Helm Charts & HPA autoscaling.
- OpenTelemetry distributed tracing.

---

## 22. License

License: To be determined.
