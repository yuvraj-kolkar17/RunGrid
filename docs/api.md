# RunGrid — REST API Specification

## Overview & Authentication

RunGrid provides a comprehensive RESTful API divided into two operational surfaces:

1. **Public/User Management API**: Authenticated via standard OAuth2 Bearer Tokens (`Authorization: Bearer <jwt_token>`).
2. **Internal Worker Protocol API**: Authenticated via internal worker header (`X-Internal-Key: <internal_key>`).

All API endpoints return standard JSON responses with structured HTTP status codes.

---

## Authentication Endpoints (`/api/v1/auth`)

| Method | Endpoint | Auth | Role | Description |
|---|---|---|---|---|
| `POST` | `/api/v1/auth/register` | None | Public | Register new user account and organization. |
| `POST` | `/api/v1/auth/token` | None | Public | Authenticate user credentials and return JWT token. |
| `GET` | `/api/v1/auth/me` | Bearer JWT | Any | Retrieve profile and role of authenticated user. |

---

## Organizations & Projects (`/api/v1/projects`)

| Method | Endpoint | Auth | Role | Description |
|---|---|---|---|---|
| `GET` | `/api/v1/projects` | Bearer JWT | VIEWER+ | List all projects belonging to user's organization. |
| `POST` | `/api/v1/projects` | Bearer JWT | ADMIN+ | Create a new project within the organization. |
| `GET` | `/api/v1/projects/{project_id}` | Bearer JWT | VIEWER+ | Retrieve project details and associated queue list. |

---

## Queue Management (`/api/v1/queues`)

| Method | Endpoint | Auth | Role | Description |
|---|---|---|---|---|
| `GET` | `/api/v1/queues` | Bearer JWT | VIEWER+ | List all queues across project queues with utilization stats. |
| `POST` | `/api/v1/queues` | Bearer JWT | ADMIN+ | Create a new queue (concurrency limit, priority). |
| `PATCH` | `/api/v1/queues/{queue_id}/pause` | Bearer JWT | ADMIN+ | Pause queue processing (workers skip polling paused queues). |
| `PATCH` | `/api/v1/queues/{queue_id}/resume` | Bearer JWT | ADMIN+ | Resume queue processing. |

---

## Job Management (`/api/v1/jobs`)

| Method | Endpoint | Auth | Role | Description |
|---|---|---|---|---|
| `GET` | `/api/v1/jobs` | Bearer JWT | VIEWER+ | List jobs with optional filtering (`status`, `queue_id`, `priority`, `page`). |
| `POST` | `/api/v1/jobs` | Bearer JWT | MEMBER+ | Submit job for execution (supports immediate or delayed). |
| `GET` | `/api/v1/jobs/{job_id}` | Bearer JWT | VIEWER+ | Get job detail including payload, attempts, and logs. |
| `POST` | `/api/v1/jobs/batch` | Bearer JWT | MEMBER+ | Atomically submit batch of jobs in a single transaction. |
| `POST` | `/api/v1/jobs/{job_id}/dependencies` | Bearer JWT | MEMBER+ | Add workflow dependency link (`parent_job_id` → `child_job_id`). |
| `POST` | `/api/v1/jobs/{job_id}/retry` | Bearer JWT | MEMBER+ | Manually retry a failed or dead-letter job. |
| `POST` | `/api/v1/jobs/{job_id}/cancel` | Bearer JWT | MEMBER+ | Cancel a queued or scheduled job. |

---

## Scheduled & Cron Jobs (`/api/v1/jobs/scheduled`)

| Method | Endpoint | Auth | Role | Description |
|---|---|---|---|---|
| `GET` | `/api/v1/jobs/scheduled` | Bearer JWT | VIEWER+ | List recurring cron job configurations. |
| `POST` | `/api/v1/jobs/scheduled` | Bearer JWT | MEMBER+ | Create recurring cron job schedule. |
| `DELETE` | `/api/v1/jobs/scheduled/{id}` | Bearer JWT | ADMIN+ | Remove a scheduled job definition. |

---

## Observability & Metrics (`/api/v1/metrics`, `/metrics`)

| Method | Endpoint | Auth | Description |
|---|---|---|---|
| `GET` | `/api/v1/metrics` | Bearer JWT | Returns system summary, job state distribution, queue utilization, worker node list, and latency percentiles. |
| `GET` | `/metrics` | None / Prometheus | Standard Prometheus exposition format for scraping counters and histograms. |
| `GET` | `/health` | None | System liveness health check. |
| `GET` | `/ready` | None | Readiness probe verifying PostgreSQL connection health. |

---

## Internal Worker Protocol (`/api/v1/internal`)

| Method | Endpoint | Header Auth | Description |
|---|---|---|---|
| `POST` | `/api/v1/internal/workers/register` | `X-Internal-Key` | Register or update worker node daemon state. |
| `POST` | `/api/v1/internal/workers/{id}/heartbeat` | `X-Internal-Key` | Emit periodic heartbeat and active job capacity. |
| `POST` | `/api/v1/internal/workers/{id}/poll` | `X-Internal-Key` | Claim eligible job across active queues (`FOR UPDATE SKIP LOCKED`). |
| `POST` | `/api/v1/internal/jobs/{id}/start` | `X-Internal-Key` | Transition claimed job to `RUNNING` state. |
| `POST` | `/api/v1/internal/jobs/{id}/complete` | `X-Internal-Key` | Report task success and output result. |
| `POST` | `/api/v1/internal/jobs/{id}/fail` | `X-Internal-Key` | Report task failure details, triggering retry backoff or DLQ transition. |
