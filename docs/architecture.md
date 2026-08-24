# RunGrid — System Architecture & Technical Specification

## Overview

**RunGrid** is a production-inspired, highly reliable, multi-tenant background task execution and job orchestration platform built with Python, FastAPI, PostgreSQL, and React. It decouples task management (REST API & control plane) from task execution (distributed worker daemon processes) to achieve high throughput, horizontal scalability, and strict fault tolerance.

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

## Architecture Guarantees

1. **At-Least-Once Execution**: Jobs are guaranteed to execute at least once. Jobs that stall due to worker crashes or network dropouts are automatically recovered by the Reaper daemon upon lease expiration.
2. **Zero Global Locks**: Multi-queue job claiming utilizes row-level locking (`FOR UPDATE SKIP LOCKED`) in PostgreSQL. Workers polling across queues operate concurrently without DB-level queue contention.
3. **Multi-Tenant & Organization Isolation**: Organizations, projects, queues, and users are strictly isolated through foreign keys and RBAC policies evaluated on every REST endpoint.
4. **Decoupled Worker Protocol**: Workers interact with backend services exclusively via authenticated internal REST APIs (`/poll`, `/start`, `/complete`, `/fail`, `/heartbeat`). Workers require no direct database access or shared disk space.
5. **Production Prometheus Observability**: Dedicated `/metrics` endpoint exports counter, gauge, and histogram telemetry for HTTP requests, job execution rates, queue saturation, lease reaper recoveries, and worker health.

## Core Subsystems

### 1. Control Plane & FastAPI Backend
- **Authentication & RBAC**: JWT bearer tokens with organization-scoped role enforcement (`OWNER`, `ADMIN`, `MEMBER`, `VIEWER`).
- **Job Submission Router**: Validates payloads, evaluates initial queue assignment, delayed execution offsets (`available_at`), batch transactions, and workflow dependencies.

### 2. Job Claiming Engine (`backend/app/services/claiming.py`)
- Evaluates active queues sorted by priority.
- Enforces per-queue concurrency limits by querying active (`CLAIMED` / `RUNNING`) job counts.
- Uses `FOR UPDATE SKIP LOCKED` to atomically claim candidate job rows without blocking concurrent worker threads.

### 3. State Transition Engine (`backend/app/services/transitions.py`)
- Strictly enforces valid job lifecycle state machine transitions (`QUEUED` → `CLAIMED` → `RUNNING` → `COMPLETED` / `FAILED` / `RETRY_WAITING` / `DEAD_LETTER`).
- Manages execution attempts and lease expiration times (`lease_expires_at`).

### 4. Background Scheduler Daemon (`backend/app/services/scheduler.py`)
- Evaluates cron schedules defined in `scheduled_jobs`.
- Calculates next execution timestamps using `croniter` and promotes due jobs to `QUEUED` state.

### 5. Reaper & Fault Recovery Service (`backend/app/services/reaper.py`)
- Identifies stale workers missing heartbeats past configurable thresholds.
- Re-queues expired `CLAIMED` or `RUNNING` jobs whose lease has lapsed, preserving attempt semantics.

### 6. Distributed Worker Processes (`worker/`)
- Multi-threaded worker daemons with configurable concurrency slots.
- Main loop polls backend internal API, executes registered Python task handlers, emits heartbeats, and reports outcomes.

### 7. Observability & Monitoring (`backend/app/routers/metrics.py`, `monitoring/prometheus.yml`)
- Integrates `prometheus-client` to record real-time operational telemetry.
- Exposes metrics to Prometheus and feeds the React Platform Observability Dashboard.
