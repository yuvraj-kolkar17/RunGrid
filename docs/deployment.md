# RunGrid — Deployment & Production Operations Guide

## Overview

This guide outlines production deployment strategies for **RunGrid**, covering single-node Docker Compose setups, multi-node VPS deployments, and cloud Kubernetes topologies.

---

## Deployment Architectures

### 1. Single VPS / Single-Host Deployment (Docker Compose)
Best suited for small-to-medium background workloads and staging environments.

- **Frontend**: Nginx serving compiled Vite static asset build (`frontend/dist`).
- **Backend API**: 2-4 Gunicorn/Uvicorn FastAPI worker processes.
- **Worker Daemons**: 2-8 multi-threaded Python worker containers.
- **Database**: Managed PostgreSQL 15+ (e.g. AWS RDS or GCP Cloud SQL).
- **Monitoring**: Prometheus container scraping `/metrics`.

### 2. Multi-Node Distributed Cloud Deployment (Kubernetes / ECS)
Designed for enterprise horizontal scaling and zero-downtime rolling upgrades.

- **API Layer**: Kubernetes Deployment with Horizontal Pod Autoscaler (HPA) targeting 70% CPU/Memory.
- **Worker Layer**: Independent Worker Deployment scaled horizontally based on queue backlog metrics exported to Prometheus.
- **Database**: High-Availability PostgreSQL cluster with primary-replica replication and connection pooling (PgBouncer).

---

## Production Environment Variables

Ensure all sensitive configuration values are set via environment variables in production:

```ini
# Production Environment
POSTGRES_USER=rungrid_prod
POSTGRES_PASSWORD=<SECURE_POSTGRES_PASSWORD>
POSTGRES_HOST=postgres-primary.internal
POSTGRES_PORT=5432
POSTGRES_DB=rungrid_prod
DATABASE_URL=postgresql://rungrid_prod:<SECURE_POSTGRES_PASSWORD>@postgres-primary.internal:5432/rungrid_prod

# Security Keys
SECRET_KEY=<RANDOM_64_BYTE_HEX_STRING>
JWT_SECRET=<RANDOM_64_BYTE_HEX_STRING>
INTERNAL_API_KEY=<RANDOM_32_BYTE_WORKER_KEY>

# Service Telemetry
PROMETHEUS_URL=http://prometheus:9090
VITE_API_URL=https://api.rungrid.yourdomain.com
```

---

## Health Checking & Readiness Probes

- **Liveness Probe**: `GET http://<backend_host>:8000/health` (Returns HTTP 200 `{"status": "healthy"}`)
- **Readiness Probe**: `GET http://<backend_host>:8000/ready` (Verifies active database connection pool)
