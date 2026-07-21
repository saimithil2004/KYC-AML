import sys
sys.path.insert(0, '.')
print('Testing Phase 8 backend imports...')
from app.services.audit_service import AuditService
print('  AuditService: OK')
from app.services.transaction_monitoring_service import analyse_and_alert
print('  TransactionMonitoringService: OK')
from app.schemas.schemas import (
    TransactionCreate, TransactionResponse, TransactionUpdate, PaginatedTransactions,
    AlertCreate, AlertUpdate, AlertResponse, PaginatedAlerts,
    CaseCreate, CaseUpdate, CaseDecision, CaseResponse, PaginatedCases,
    AuditLogResponse, PaginatedAuditLogs, RescreeningResponse
)
print('  All Phase 8 schemas: OK')
from app.api.v1.endpoints.transactions import router as tx_router
print('  Transactions router: OK')
from app.api.v1.endpoints.alerts import router as alert_router
print('  Alerts router: OK')
from app.api.v1.endpoints.cases import router as cases_router
print('  Cases router: OK')
from app.api.v1.endpoints.screening import router as screening_router
print('  Screening router: OK')
from app.api.v1.endpoints.audit_logs import router as audit_router
print('  AuditLogs router: OK')
from app.api.v1.api import api_router
print('  Main API router: OK')
print('All Phase 8 backend imports PASSED')
