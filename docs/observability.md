# RunGrid — Prometheus Observability & Metrics Architecture

## Observability Overview

RunGrid includes a full production-inspired observability stack powered by Prometheus and FastAPI telemetry integration.

```
┌─────────────────┐       ┌─────────────────┐       ┌─────────────────┐
│ Distributed     │──────►│  FastAPI /      │──────►│   Prometheus    │
│ Workers         │       │  /metrics       │       │   Server        │
└─────────────────┘       └────────┬────────┘       └────────┬────────┘
                                   │                         │
                                   ▼                         ▼
                          ┌─────────────────┐       ┌─────────────────┐
                          │ PostgreSQL DB   │       │ React Platform  │
                          │ Telemetry       │       │ Observability UI│
                          └─────────────────┘       └─────────────────┘
```

## Scrape Target & Configuration

Prometheus scrapes the `/metrics` endpoint exposed by the backend container every 5 seconds.
Configured in `monitoring/prometheus.yml`:

```yaml
global:
  scrape_interval: 5s
  evaluation_interval: 5s

scrape_configs:
  - job_name: 'rungrid-backend'
    metrics_path: '/metrics'
    static_configs:
      - targets: ['backend:8000']
```

## Key Exported Metrics

| Metric Name | Type | Description |
|---|---|---|
| `rungrid_http_requests_total` | Counter | Total HTTP requests categorized by `method`, `endpoint`, and `status_code`. |
| `rungrid_http_request_duration_seconds` | Histogram | Request latency distributions with percentiles (`p50`, `p95`, `p99`). |
| `rungrid_jobs_total` | Gauge | Total jobs in the database categorized by status (`queued`, `claimed`, `running`, `completed`, `failed`, `retry_waiting`, `dead_letter`, `scheduled`). |
| `rungrid_job_execution_duration_seconds` | Histogram | Task execution latency across worker nodes. |
| `rungrid_queue_concurrency_limit` | Gauge | Configured concurrency limit per queue. |
| `rungrid_queue_active_jobs` | Gauge | Active jobs currently in execution per queue. |
| `rungrid_workers_active` | Gauge | Number of healthy active worker daemons. |
| `rungrid_reaper_recovered_jobs_total` | Counter | Total stale jobs re-queued by the Reaper fault-recovery service. |

## Platform Observability Dashboard (`/platform/observability`)

The React frontend includes a real-time Observability Center providing:
- **Live Throughput Waveform**: Continuously updating area chart showing completion, retry, and failure rates over time.
- **Latency Percentiles (P50, P95, P99)**: Visual line chart tracking execution duration SLAs.
- **Queue Saturation & Concurrency Utilization**: Progress gauges monitoring per-queue capacity and backlog pressure.
- **Worker Node Topography**: Active worker count, heartbeat status, and concurrency slot utilization.
