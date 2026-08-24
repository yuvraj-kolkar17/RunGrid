# RunGrid — Reliability & Fault Tolerance Specification

## Reliability Guarantees

RunGrid is designed to withstand node failures, network partitions, worker crashes, database connection drops, and transient downstream service outages.

### 1. At-Least-Once Execution Semantics
Every job submitted to RunGrid is guaranteed to be processed at least once. Because distributed networks can experience partitions or crash failures after task completion but prior to ack acknowledgment, task handlers must be written to be **idempotent**.

### 2. Lease-Based Recovery & Reaper Daemon
When a worker claims a job, a lease timestamp (`lease_expires_at`) is written to the `jobs` row in PostgreSQL (default lease: 60 seconds).
- While executing, active workers regularly refresh their node heartbeat.
- If a worker process crashes, loses connectivity, or gets OOM-killed, its heartbeat lapses.
- The background **Reaper service** (`backend/app/services/reaper.py`) queries for jobs with expired leases (`lease_expires_at < NOW()`) and automatically recovers them back to `QUEUED` or `RETRY_WAITING`.

### 3. Retry System & Backoff Strategies

RunGrid supports three configurable backoff strategies defined per project or queue via `retry_policies`:

- **FIXED**: Delay between retries remains constant.
  - Formula: `delay = base_delay_seconds`
  - Example (`base_delay = 5s`): `5s, 5s, 5s`
- **LINEAR**: Delay scales linearly with attempt count.
  - Formula: `delay = base_delay_seconds * attempt`
  - Example (`base_delay = 5s`): `5s, 10s, 15s, 20s`
- **EXPONENTIAL**: Delay scales exponentially with attempt count.
  - Formula: `delay = base_delay_seconds * (2 ^ (attempt - 1))`
  - Example (`base_delay = 5s`): `5s, 10s, 20s, 40s`

### 4. Dead Letter Queue (DLQ)
When a job fails and reaches its maximum retry threshold (`attempt >= max_retries`), RunGrid transitions the job to `DEAD_LETTER` state and writes a record to `dead_letter_jobs`. Operators can inspect dead-letter payloads, analyze error traces, and manually trigger job replay through the API or Web Dashboard.

### 5. Workflow Dependency Cycle Detection
For jobs linked via workflow dependencies (`parent_job_id` → `child_job_id`), RunGrid runs depth-first search (DFS) cycle detection during link insertion to ensure DAG (Directed Acyclic Graph) integrity. Dependency-blocked child jobs remain in `QUEUED` until all parent jobs achieve `COMPLETED` status.
