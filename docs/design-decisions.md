# RunGrid — Key Engineering Design Decisions

This document records the foundational architectural decisions, rationale, and trade-offs made in designing and implementing **RunGrid**.

---

### 1. PostgreSQL as Single Source of Truth vs. Redis Queue
- **Decision**: Use PostgreSQL with `FOR UPDATE SKIP LOCKED` for task queues, job states, and execution histories rather than Redis/Celery.
- **Rationale**: Guarantees ACID transactional safety for multi-tenant organizations, projects, queues, and retries. Eliminates state drift between cache and database.
- **Trade-off**: Requires proper database index tuning (`(status, priority, available_at)`), but modern PostgreSQL handles thousands of skips/locks per second cleanly.

---

### 2. Atomic Row-Level Job Claiming (`FOR UPDATE SKIP LOCKED`)
- **Decision**: Avoid global application-level locks during worker queue polling by using SQL row-level skip locks.
- **Rationale**: Allows multiple workers across multiple nodes to poll the same queue concurrently without lock contention or thread blocking.
- **Trade-off**: Requires explicit order-by clauses and transaction boundaries to release locks promptly.

---

### 3. Decoupled REST Worker Protocol vs. Shared Direct Database Access
- **Decision**: Workers communicate with the backend control plane exclusively via authenticated REST API endpoints (`/poll`, `/start`, `/complete`, `/fail`).
- **Rationale**: Isolates workers from raw database schema changes, simplifies worker deployment, and enables zero-trust worker authentication via `X-Internal-Key`.
- **Trade-off**: Introduces minor HTTP overhead per task claim/completion compared to direct socket or IPC calls.

---

### 4. Lease-Based Execution Recovery (Reaper Daemon)
- **Decision**: Attach `lease_expires_at` timestamps to claimed/running job records and run a background Reaper task to reclaim expired jobs.
- **Rationale**: Automatically recovers jobs stranded by crashed worker nodes or network dropouts without manual operator intervention.
- **Trade-off**: At-least-once execution guarantee means task handlers must be written to be idempotent.

---

### 5. Predefined Task Handlers (TaskRegistry) vs. Arbitrary Remote Execution
- **Decision**: Workers maintain a statically registered `TaskRegistry` of Python functions matched against job `task_type` strings.
- **Rationale**: Prevents Remote Code Execution (RCE) vulnerabilities and malicious arbitrary code injection.
- **Trade-off**: New task handler types must be deployed as part of worker codebase updates.

---

### 6. Hybrid Metrics Engine (Database Telemetry + Prometheus Exposition)
- **Decision**: Expose standard `/metrics` endpoint using `prometheus-client` while also maintaining SQL-aggregated metrics for instantaneous dashboard REST queries.
- **Rationale**: Gives operators immediate real-time dashboard UI responses while supporting standard enterprise Prometheus scraping and Grafana alerting.
- **Trade-off**: Telemetry logic is maintained in both database aggregation views and Prometheus counters.
