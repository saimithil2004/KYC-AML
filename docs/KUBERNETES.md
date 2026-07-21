# UK Compliance Platform — Kubernetes Deployment Manual

This document details deploying the platform into a production-grade Kubernetes cluster.

## 1. Kubernetes Resource Architecture
The cluster is isolated under the `aml-compliance` namespace. Core components:
- **`namespace.yaml`:** Isolation namespace boundary.
- **`configmap.yaml` & `secrets.yaml`:** Common variables and base64 encoded secrets configuration.
- **`postgres.yaml`:** StatefulSet for PostgreSQL (1 primary + 1 replica) with Persistent Volume Claims mapping to persistent storage backends.
- **`redis.yaml`:** Redis Master-Sentinel deployment layout with internal service endpoints.
- **`backend.yaml`:** Deployment for API server pods, managing CPU/Memory requests/limits, mounting startup/liveness/readiness probes, and HorizontalPodAutoscaler scaling configurations.
- **`celery.yaml`:** Background tasks processing deployments (beat scheduler set as single `Recreate` strategy replica; workers running HPAs).
- **`frontend.yaml`:** Next.js deployment node layout.
- **`ingress.yaml`:** Nginx ingress controller path-based request routing.
- **`network-policy.yaml`:** Isolating firewall boundaries to deny direct cross-component container access.

---

## 2. Apply Manifests Order
Execute the kubectl commands in the following logical sequence:

1. **Create Namespace:**
   ```bash
   kubectl apply -f namespace.yaml
   ```

2. **Apply Configs and Secrets:**
   ```bash
   kubectl apply -f configmap.yaml
   kubectl apply -f secrets.yaml
   ```

3. **Apply Stateful Storage (Databases & Caches):**
   ```bash
   kubectl apply -f postgres.yaml
   kubectl apply -f redis.yaml
   ```

4. **Apply Network Firewalls:**
   ```bash
   kubectl apply -f network-policy.yaml
   ```

5. **Deploy Applications:**
   ```bash
   kubectl apply -f backend.yaml
   kubectl apply -f celery.yaml
   kubectl apply -f frontend.yaml
   ```

6. **Expose Ingress Routing Rules:**
   ```bash
   kubectl apply -f ingress.yaml
   ```

---

## 3. Rolling Updates & Deployment Strategy
The backend and frontend deployments are configured with a `RollingUpdate` strategy:
```yaml
strategy:
  type: RollingUpdate
  rollingUpdate:
    maxSurge: 25%
    maxUnavailable: 25%
```
- **Zero-Downtime Releases:** On tag updates, Kubernetes provisions a new container, waits for its `startupProbe` to succeed, routes traffic to it, and then terminates the legacy pod instance.
- **Probes Configured:**
  - **`startupProbe`:** Queries `/api/v1/health/startup` to allow compilation time.
  - **`livenessProbe`:** Queries `/api/v1/health/live` every 10 seconds.
  - **`readinessProbe`:** Queries `/api/v1/health/ready` to ensure database/Redis connections are active before accepting requests.
