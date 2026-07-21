# UK Compliance Platform — Production Deployment Guide

This document details the production-ready procedures and verification checklists for deploying the KYC & AML Platform.

## 1. Production Architecture Overview
In production, the platform operates as a distributed microservices stack:
- **Load Balancer / Reverse Proxy:** NGINX or Traefik handles TLS termination, secure HTTP headers, and compression.
- **Backend API:** FastAPI services running under uvicorn behind the load balancer, scaling horizontally.
- **Async Workers:** Celery worker pools executing long-running KYC orchestrator screenings, rescreening monitoring schedules, and scheduled exports.
- **Primary Database:** PostgreSQL with transaction logging, connection pooling, and replication enabled.
- **Read Replica:** Secondary PostgreSQL replica database capturing read traffic for BI reports, analytics, and history dashboard tables.
- **Cache cluster:** Redis Master-Slave nodes managed by Redis Sentinel for failover caching.

---

## 2. Secrets Management & Storage Hardening
Do **NOT** store plaintext secrets in repositories or Docker Compose files.
- Enforce secret injection via AWS Secrets Manager, HashiCorp Vault, or Kubernetes Secrets.
- Sensitive environment variables that **MUST** be rotated frequently:
  - `SECRET_KEY`: JWT authentication signature key.
  - `ENCRYPTION_KEY`: AES-256 GCM key (Base64 string) used to encrypt PII database attributes.
  - `DATABASE_URL`: Connection string containing database credentials.
  - `REDIS_URL`: Cache connection endpoint.

---

## 3. High Availability Checklist
1. **Multi-Region Replica Databases:** Ensure the database has at least one warm read-replica in a separate region/zone.
2. **Redis Sentinel Clustering:** Configure at least 3 Redis Sentinel instances monitoring the Master node to ensure automatic failover without service disruption.
3. **API Scalability:** Deploy backend API containers across multiple availability zones.
4. **Volume Mounts:** Document files must be stored on persistent shared mounts like AWS EFS, Google Filestore, or persistent volumes with standard storage classes.

---

## 4. Run Production Compose Stack Locally
To run the production architecture locally for sanity validation:
```bash
docker-compose -f docker-compose.prod.yml up -d
```
Verify all services are green:
```bash
docker-compose -f docker-compose.prod.yml ps
```
To launch the monitoring dashboard stack (Prometheus, Grafana):
```bash
docker-compose -f docker-compose.monitoring.yml up -d
```
To scale up instances:
```bash
docker-compose -f docker-compose.prod.yml -f docker-compose.scaling.yml up -d --scale backend_api=3 --scale celery_worker_transactions=2
```
