from fastapi import APIRouter
from app.api.v1.endpoints import auth, customers, documents, kyc, sync, risk_scores
from app.api.v1.endpoints import (
    transactions,
    alerts,
    cases,
    screening,
    audit_logs,
    dashboard,
    regulations,
    policy_rules,
    monitoring,
)

api_router = APIRouter()

api_router.include_router(auth.router, prefix="/auth", tags=["authentication"])
api_router.include_router(customers.router, prefix="/customers", tags=["customers"])
api_router.include_router(documents.router, prefix="/documents", tags=["documents"])
api_router.include_router(kyc.router, prefix="/kyc", tags=["kyc"])
api_router.include_router(sync.router, prefix="/sync", tags=["sync"])
api_router.include_router(risk_scores.router, prefix="/risk-scores", tags=["risk-scores"])

# Phase 8 — Compliance Operations
api_router.include_router(
    transactions.router, prefix="/transactions", tags=["transactions"]
)
api_router.include_router(alerts.router, prefix="/alerts", tags=["alerts"])
api_router.include_router(cases.router, prefix="/cases", tags=["cases"])
api_router.include_router(screening.router, prefix="/screening", tags=["screening"])
api_router.include_router(audit_logs.router, prefix="/audit-logs", tags=["audit-logs"])


# Phase 9 — Dashboard
api_router.include_router(dashboard.router, prefix="/dashboard", tags=["dashboard"])

# Phase 10 — Regulations & Policy Rules
api_router.include_router(
    regulations.router, prefix="/regulations", tags=["regulations"]
)
api_router.include_router(
    policy_rules.router, prefix="/policy-rules", tags=["policy-rules"]
)

# Phase 11 — Continuous Monitoring & Re-Screening
api_router.include_router(monitoring.router, prefix="/monitoring", tags=["monitoring"])

# Phase 12 — Investigation Workspace
from app.api.v1.endpoints import investigations

api_router.include_router(
    investigations.router, prefix="/investigations", tags=["investigations"]
)

# Phase 13 — Executive BI & Reporting
from app.api.v1.endpoints import reports, analytics

api_router.include_router(reports.router, prefix="/reports", tags=["reports"])
api_router.include_router(analytics.router, prefix="/analytics", tags=["analytics"])

# Phase 14 — External Integrations & Notification System
from app.api.v1.endpoints import integrations

api_router.include_router(
    integrations.router, prefix="/integrations", tags=["integrations"]
)

# Phase 15 — Enterprise Hardening & Observability
from app.api.v1.endpoints import health, system

api_router.include_router(health.router, prefix="/health", tags=["health"])
api_router.include_router(system.router, prefix="/system", tags=["system"])

# Phase 16 — Enterprise DevOps & Deployment
from app.api.v1.endpoints import devops

api_router.include_router(devops.router, prefix="/devops", tags=["devops"])

# Phase 17 — AI Governance & Explainability
from app.api.v1.endpoints import ai_governance

api_router.include_router(ai_governance.router, prefix="/ai", tags=["ai"])
