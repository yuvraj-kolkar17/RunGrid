# RunGrid — Distributed Worker Daemon Architecture

## Worker Daemon Overview

RunGrid workers are stateless, multi-threaded Python daemon processes designed to poll background tasks from the FastAPI control plane and execute them safely.

```
┌────────────────────────────────────────────────────────┐
│                     Worker Daemon                      │
│                                                        │
│  ┌──────────────┐   ┌───────────────────────────────┐  │
│  │ Registration │   │   Task Registry (Predefined)  │  │
│  └──────┬───────┘   │                               │  │
│         │           │  - send_welcome_email         │  │
│         ▼           │  - generate_report            │  │
│  ┌──────────────┐   │  - process_image              │  │
│  │ Polling Loop │──►│  - generate_invoice           │  │
│  └──────┬───────┘   │  - sync_customer_profile      │  │
│         │           │  - send_notification          │  │
│         ▼           └───────────────┬───────────────┘  │
│  ┌──────────────┐                   │                  │
│  │ Execution    │◄──────────────────┘                  │
│  │ Slot Manager │                                      │
│  └──────┬───────┘                                      │
│         │                                              │
│         ▼                                              │
│  ┌──────────────┐                                      │
│  │ Heartbeat    │                                      │
│  │ Thread       │                                      │
│  └──────────────┘                                      │
└────────────────────────────────────────────────────────┘
```

## Lifecycle States

```
REGISTER ──► POLL ──► CLAIM ──► START ──► EXECUTE ──► COMPLETE / FAIL
  │                                                        │
  └────────────────── HEARTBEAT (Background) ──────────────┘
```

1. **REGISTER**: On startup, the worker sends a `POST /api/v1/internal/workers/register` call registering its hostname, IP address, concurrency slots, and unique UUID.
2. **POLL & CLAIM**: The worker requests candidate jobs from `POST /api/v1/internal/workers/{id}/poll`. The backend evaluates queue priorities and concurrency limits, selecting candidate jobs via `FOR UPDATE SKIP LOCKED`.
3. **START**: Upon acquiring a job, the worker sends `POST /api/v1/internal/jobs/{id}/start` to transition the status from `CLAIMED` to `RUNNING` and increment the execution attempt count.
4. **EXECUTE**: The worker dispatches the job payload to a predefined Python task handler looked up in the `TaskRegistry`.
5. **COMPLETE / FAIL**:
   - On success: The worker invokes `POST /api/v1/internal/jobs/{id}/complete` with execution duration and output payload.
   - On exception: The worker invokes `POST /api/v1/internal/jobs/{id}/fail` with error type, stack trace, and execution time.
6. **HEARTBEAT**: A dedicated daemon thread periodically sends `POST /api/v1/internal/workers/{id}/heartbeat` every 5 seconds to report active concurrency capacity and refresh node health.

## Security & Safe Task Execution

- **No Remote Code Execution (`eval` / `exec`)**: RunGrid task handlers are strictly predefined in the codebase using Python functions decorated or registered in `TaskRegistry`. Workers reject unknown `task_type` identifiers.
- **Internal Authentication**: All worker API calls require an `X-Internal-Key` header header matching backend configuration.
- **Graceful Shutdown**: Workers listen for `SIGINT` / `SIGTERM` signals. Active tasks are allowed to complete within a configurable shutdown grace window before process termination.
