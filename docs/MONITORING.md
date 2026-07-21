# UK Compliance Platform — Observability & Monitoring Guide

This guide details configuring and accessing platform diagnostics via the Prometheus/Grafana/Loki observability stack.

## 1. System Metrics & Scraping
The backend API exposes a Prometheus-compatible metrics endpoint at `GET /api/v1/health/metrics` in plain-text format.
Scraped stats:
- `aml_cpu_percent`
- `aml_memory_percent`
- `aml_disk_percent`
- `aml_db_latency_ms`
- `aml_redis_latency_ms`
- `aml_celery_queue_depth`
- `aml_celery_active_workers`
- `aml_api_requests_count`
- `aml_api_latency_average_ms`
- `aml_api_error_rate_percent`

These are configured in `deployment/prometheus/prometheus.yml` under target `aml-backend-api` scraping every 15s.

---

## 2. Centralized Logs with Loki
The application uses a custom structured JSON Formatter configured in `backend/app/core/logging_config.py`.
- **Log properties:**
  - `timestamp`
  - `level`
  - `message`
  - `request_id`: Traced Request ID propagated by ASGI middleware.
  - `correlation_id`: Context correlation ID linking API calls to background Celery tasks.
  - `user_id`: Authenticated actor ID.
  - `customer_id` / `case_id`: Entities scope.

Loki processes these logs to enable structured searching inside Grafana using LogQL.
Example Grafana query:
```logql
{container_name="aml_prod_backend_api"} | json | request_id="req-9f3b7..."
```

---

## 3. Alerts Configuration (AlertManager)
AlertManager triggers notifications based on target thresholds:
- **API Error Spike:** Trigger alert if `aml_api_error_rate_percent > 5%` for 2 minutes.
- **Worker offline:** Trigger critical pager alerts if `aml_celery_active_workers == 0` for 1 minute.
- **DB Latency:** Trigger warnings if `aml_db_latency_ms > 200` for 3 minutes.
- **Queue Depth:** Trigger warning if `aml_celery_queue_depth > 50` indicating backup delay.
