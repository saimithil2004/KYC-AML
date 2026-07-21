# UK Compliance Platform — Containerization & Docker Guide

This document describes how the platform's Dockerfiles are structured and optimized for production.

## 1. Multi-Stage Build Strategy
To reduce the production container size and limit the attack surface, the Dockerfiles use multi-stage builds.

### Backend Dockerfile (`backend/Dockerfile`)
1. **Build Stage (`builder`):**
   - Uses `python:3.12-slim` base image.
   - Installs system packages (`build-essential`, `libpq-dev`).
   - Installs python packages onto the `--user` space (`/root/.local`).
2. **Run Stage (`runner`):**
   - Uses clean `python:3.12-slim`.
   - Copies `/root/.local` from builder, keeping the image clean of compiler dependencies.
   - Creates a non-root system user `compliance_user` (UID: 10001) for runtime processes.
   - Configures a curl-based container HEALTHCHECK on `/health/live`.

### Frontend Dockerfile (`frontend/Dockerfile`)
1. **Build Stage (`builder`):**
   - Uses `node:20-alpine`.
   - Runs `npm ci` for lockfile dependency parity.
   - Compiles static Next.js build.
2. **Run Stage (`runner`):**
   - Uses lightweight `node:20-alpine`.
   - Copies only built `.next` folder and `node_modules` required to run production server.
   - Configures a non-root user `nextjs` (UID: 10001) to serve application pages.

---

## 2. Docker Compose Profiles
Three configuration files are provided:
- **`docker-compose.prod.yml`:** The core production definition (Primary database, Replica database, Redis master/sentinels, celery workers/beat, backend api, frontend nextjs, and load-balancing Nginx).
- **`docker-compose.monitoring.yml`:** Metric exporter and observability services (Prometheus, Grafana, Loki, AlertManager, Node Exporter, cAdvisor).
- **`docker-compose.scaling.yml`:** Replica scales and target queues definition (scaling backend/frontend replicas and assigning dedicated queues to celery worker nodes).

### Execution Commands:
- Build and boot base production stack:
  ```bash
  docker-compose -f docker-compose.prod.yml up --build -d
  ```
- Build and boot combined stack with monitoring:
  ```bash
  docker-compose -f docker-compose.prod.yml -f docker-compose.monitoring.yml up -d
  ```
- Scale up worker pools:
  ```bash
  docker-compose -f docker-compose.prod.yml -f docker-compose.scaling.yml up -d
  ```
