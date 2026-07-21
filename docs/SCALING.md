# UK Compliance Platform — Scaling & Performance Optimization Guide

This document outlines options and procedures for scaling the AML/KYC Platform under enterprise workloads.

## 1. API Horizontal Autoscaling (HPA)
The API pods run inside Kubernetes behind HPAs:
```yaml
apiVersion: autoscaling/v2
kind: HorizontalPodAutoscaler
metadata:
  name: aml-backend-api-hpa
spec:
  minReplicas: 2
  maxReplicas: 10
  metrics:
    - type: Resource
      resource:
        name: cpu
        target:
          type: Utilization
          averageUtilization: 75
```
- **Scale-Up Trigger:** If average CPU utilization exceeds 75% across the replica set, Kubernetes provisions additional backend api pods.
- **Cool-Down Period:** Scaling down is delayed by 5 minutes to prevent rapid pod fluctuations ("thrashing").

---

## 2. Celery Worker Queue Routing
To prevent heavy tasks (like weekly rescreening batch runs) from blocking quick operations (like transaction screenings), we isolate tasks onto specific Celery queues:
- **`transactions`:** High priority queue, dedicated worker replicas scaled to handle instant API checks.
- **`monitoring` & `reports`:** Batch queue, workers run cron schedules and exports.
- **`default`:** Standard customer onboarding verification.

We scale worker replicas separately using the target scale profile:
```bash
docker-compose -f docker-compose.prod.yml -f docker-compose.scaling.yml up -d --scale celery_worker_transactions=4
```

---

## 3. Database Connection Pooling
We configure database pooling limits inside `backend/app/core/database.py` with the following parameters:
- **`pool_size`:** Sets the maximum base pool size (typically 20 connections per API worker node).
- **`max_overflow`:** Allows up to 10 additional temporary connections during load spikes.
- **`pool_pre_ping`:** Enforces connectivity check before issuing sessions, recycling stale connections automatically.
- **`DATABASE_REPLICA_URL`:** Configure replica routing inside BI services using the `get_read_db` dependency to keep analytical queries off the primary transactional DB.
