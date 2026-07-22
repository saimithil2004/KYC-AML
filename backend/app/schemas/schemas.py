from datetime import date, datetime
from typing import List, Optional
from pydantic import BaseModel, EmailStr, Field, field_validator
from uuid import UUID


# AUTHENTICATION
class UserRegister(BaseModel):
    email: EmailStr
    password: str = Field(..., min_length=8)
    role: str = Field("customer", description="customer, compliance_officer, admin")

    @field_validator("role")
    @classmethod
    def validate_role(cls, value: str) -> str:
        allowed = {"customer", "compliance_officer", "admin"}
        if value not in allowed:
            raise ValueError(f"role must be one of: {', '.join(sorted(allowed))}")
        return value


class UserLogin(BaseModel):
    email: EmailStr
    password: str
    mfa_code: Optional[str] = None


class UserResponse(BaseModel):
    id: UUID
    email: EmailStr
    role: str
    is_active: bool
    created_at: datetime

    mfa_enabled: bool = False

    class Config:
        from_attributes = True


class Token(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    user: UserResponse


# CORPORATE STRUCTURES
class DirectorCreate(BaseModel):
    first_name: str
    last_name: str
    dob: Optional[date] = None
    nationality: Optional[str] = None
    appointment_date: Optional[date] = None


class UboCreate(BaseModel):
    first_name: str
    last_name: str
    dob: Optional[date] = None
    nationality: Optional[str] = None
    ownership_percentage: float = Field(..., ge=0.0, le=100.0)
    control_type: str


class CompanyCreate(BaseModel):
    company_name: str
    registration_number: str
    registered_address: str
    trading_address: Optional[str] = None
    country_of_incorporation: str
    incorporation_date: Optional[date] = None
    sic_code: Optional[str] = None


# CUSTOMERS
class CustomerCreate(BaseModel):
    customer_type: str = Field(..., description="individual or corporate")
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    dob: Optional[date] = None
    nationality: Optional[str] = None
    phone_number: Optional[str] = None
    street_address: Optional[str] = None
    city: Optional[str] = None
    postal_code: Optional[str] = None
    country: Optional[str] = None

    # Corporate payloads
    company: Optional[CompanyCreate] = None
    directors: Optional[List[DirectorCreate]] = []
    ubos: Optional[List[UboCreate]] = []

    @field_validator("customer_type")
    @classmethod
    def validate_customer_type(cls, value: str) -> str:
        allowed = {"individual", "corporate"}
        if value not in allowed:
            raise ValueError("customer_type must be individual or corporate")
        return value


class CustomerUpdate(BaseModel):
    customer_type: Optional[str] = None
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    dob: Optional[date] = None
    nationality: Optional[str] = None
    phone_number: Optional[str] = None
    street_address: Optional[str] = None
    city: Optional[str] = None
    postal_code: Optional[str] = None
    country: Optional[str] = None
    status: Optional[str] = None

    @field_validator("customer_type")
    @classmethod
    def validate_optional_customer_type(cls, value: Optional[str]) -> Optional[str]:
        if value is None:
            return value
        allowed = {"individual", "corporate"}
        if value not in allowed:
            raise ValueError("customer_type must be individual or corporate")
        return value


class CustomerResponse(BaseModel):
    id: UUID
    customer_type: str
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    dob: Optional[date] = None
    nationality: Optional[str] = None
    phone_number: Optional[str] = None
    street_address: Optional[str] = None
    city: Optional[str] = None
    postal_code: Optional[str] = None
    country: Optional[str] = None
    status: str
    created_at: datetime

    class Config:
        from_attributes = True


# KYC PROFILE
class KYCProfileCreate(BaseModel):
    customer_id: UUID
    full_name: str
    dob: date
    nationality: str
    tax_residency: Optional[str] = None
    address: str
    occupation: str
    source_of_funds: str
    source_of_wealth: str
    annual_income_range: Optional[str] = None
    risk_category: Optional[str] = "low"
    expected_activity_desc: Optional[str] = None

    @field_validator("risk_category")
    @classmethod
    def validate_risk_category(cls, value: Optional[str]) -> Optional[str]:
        if value is None:
            return value
        allowed = {"low", "medium", "high"}
        if value not in allowed:
            raise ValueError("risk_category must be low, medium, or high")
        return value


class KYCProfileUpdate(BaseModel):
    full_name: Optional[str] = None
    dob: Optional[date] = None
    nationality: Optional[str] = None
    tax_residency: Optional[str] = None
    address: Optional[str] = None
    occupation: Optional[str] = None
    source_of_funds: Optional[str] = None
    source_of_wealth: Optional[str] = None
    annual_income_range: Optional[str] = None
    risk_category: Optional[str] = None
    expected_activity_desc: Optional[str] = None

    @field_validator("risk_category")
    @classmethod
    def validate_optional_risk_category(cls, value: Optional[str]) -> Optional[str]:
        if value is None:
            return value
        allowed = {"low", "medium", "high"}
        if value not in allowed:
            raise ValueError("risk_category must be low, medium, or high")
        return value


class KYCProfileResponse(BaseModel):
    id: UUID
    customer_id: UUID
    full_name: Optional[str] = None
    dob: Optional[date] = None
    nationality: Optional[str] = None
    tax_residency: Optional[str] = None
    address: Optional[str] = None
    occupation: str
    source_of_funds: str
    source_of_wealth: str
    annual_income_range: Optional[str] = None
    risk_category: str
    expected_activity_desc: Optional[str] = None
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


# DOCUMENTS
class DocumentResponse(BaseModel):
    id: UUID
    customer_id: UUID
    document_type: str
    file_name: str
    file_path: str
    content_type: Optional[str] = None
    file_size: Optional[int] = None
    verification_status: str
    created_at: datetime

    class Config:
        from_attributes = True


# TRANSACTIONS
class TransactionCreate(BaseModel):
    sender_account_number: str
    sender_sort_code: str
    receiver_account_number: str
    receiver_sort_code: str
    receiver_name: str
    receiver_country: str
    amount: float = Field(..., gt=0)
    currency: str = "GBP"
    transaction_type: str  # credit, debit, transfer, cash
    reference: Optional[str] = None
    channel: Optional[str] = None


class TransactionUpdate(BaseModel):
    status: Optional[str] = None
    reference: Optional[str] = None
    completed_at: Optional[datetime] = None


class TransactionResponse(BaseModel):
    id: UUID
    sender_account_id: UUID
    receiver_account_number: str
    receiver_sort_code: str
    receiver_name: str
    receiver_country: str
    amount: float
    currency: str
    transaction_type: str
    status: str
    reference: Optional[str] = None
    completed_at: Optional[datetime] = None
    created_at: datetime

    class Config:
        from_attributes = True


class PaginatedTransactions(BaseModel):
    total: int
    page: int
    page_size: int
    items: List[TransactionResponse]


# ALERTS
class AlertCreate(BaseModel):
    customer_id: UUID
    transaction_id: Optional[UUID] = None
    alert_type: str
    risk_score: float = Field(..., ge=0, le=100)
    status: str = "open"
    alert_metadata: Optional[dict] = None


class AlertUpdate(BaseModel):
    status: Optional[str] = None
    alert_metadata: Optional[dict] = None


class AlertResponse(BaseModel):
    id: UUID
    customer_id: UUID
    transaction_id: Optional[UUID] = None
    alert_type: str
    risk_score: float
    status: str
    alert_metadata: Optional[dict] = None
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class PaginatedAlerts(BaseModel):
    total: int
    page: int
    page_size: int
    items: List[AlertResponse]


# CASES
class CaseCreate(BaseModel):
    customer_id: UUID
    priority: str = "medium"
    status: str = "open"
    investigation_notes: Optional[str] = None
    assigned_to: Optional[UUID] = None


class CaseUpdate(BaseModel):
    priority: Optional[str] = None
    status: Optional[str] = None
    investigation_notes: Optional[str] = None
    assigned_to: Optional[UUID] = None
    sar_filed: Optional[bool] = None


class CaseDecision(BaseModel):
    decision: str  # APPROVE, REJECT, EDD_REQUIRED, MANUAL_REVIEW
    notes: str
    reason: Optional[str] = None
    sar_filed: Optional[bool] = False


class CaseResponse(BaseModel):
    id: UUID
    customer_id: UUID
    assigned_to: Optional[UUID] = None
    priority: str
    status: str
    investigation_notes: Optional[str] = None
    sar_filed: bool
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class PaginatedCases(BaseModel):
    total: int
    page: int
    page_size: int
    items: List[CaseResponse]


# AUDIT LOGS
class AuditLogResponse(BaseModel):
    id: UUID
    user_id: Optional[UUID] = None
    action: str
    entity_name: str
    entity_id: UUID
    old_values: Optional[dict] = None
    new_values: Optional[dict] = None
    ip_address: Optional[str] = None
    created_at: datetime

    class Config:
        from_attributes = True


class PaginatedAuditLogs(BaseModel):
    total: int
    page: int
    page_size: int
    items: List[AuditLogResponse]


# RE-SCREENING
class RescreeningResponse(BaseModel):
    status: str
    customer_id: str
    case_id: Optional[str] = None
    score: Optional[float] = None
    tier: Optional[str] = None
    decision: Optional[str] = None
    message: str


# ─── Phase 10: Regulations & Policy Management ───────────────────────────────


class RegulationCreate(BaseModel):
    title: str = Field(..., max_length=255)
    authority: str = Field(..., max_length=100)
    description: Optional[str] = None
    country: Optional[str] = None
    jurisdiction: Optional[str] = None
    regulator: Optional[str] = None
    regulation_type: Optional[str] = None
    version: Optional[str] = "1.0.0"
    effective_date: Optional[date] = None
    expiry_date: Optional[date] = None


class RegulationUpdate(BaseModel):
    title: Optional[str] = None
    authority: Optional[str] = None
    description: Optional[str] = None
    country: Optional[str] = None
    jurisdiction: Optional[str] = None
    regulator: Optional[str] = None
    regulation_type: Optional[str] = None
    version: Optional[str] = None
    effective_date: Optional[date] = None
    expiry_date: Optional[date] = None
    status: Optional[str] = None  # active, archived, draft, pending_review
    extracted_text: Optional[str] = None


class RegulationResponse(BaseModel):
    id: UUID
    title: str
    authority: str
    upload_path: str
    uploaded_by_id: Optional[UUID] = None
    created_at: datetime
    description: Optional[str] = None
    country: Optional[str] = None
    jurisdiction: Optional[str] = None
    regulator: Optional[str] = None
    regulation_type: Optional[str] = None
    version: str
    effective_date: Optional[date] = None
    expiry_date: Optional[date] = None
    status: str
    extracted_text: Optional[str] = None
    document_metadata: Optional[dict] = None

    class Config:
        from_attributes = True


class PaginatedRegulations(BaseModel):
    total: int
    page: int
    page_size: int
    items: List[RegulationResponse]


class PolicyRuleCreate(BaseModel):
    regulation_id: UUID
    rule_name: str = Field(..., max_length=255)
    rule_type: str = Field(
        ..., max_length=100
    )  # threshold, block, edd, aml, kyc, internal
    conditions: dict
    severity: str = "medium"
    description: Optional[str] = None
    expression: Optional[str] = None
    threshold: Optional[float] = None
    country: Optional[str] = None
    version: Optional[str] = "1.0.0"


class PolicyRuleUpdate(BaseModel):
    rule_name: Optional[str] = None
    rule_type: Optional[str] = None
    conditions: Optional[dict] = None
    is_active: Optional[bool] = None
    severity: Optional[str] = None
    description: Optional[str] = None
    expression: Optional[str] = None
    threshold: Optional[float] = None
    country: Optional[str] = None
    version: Optional[str] = None


class PolicyRuleResponse(BaseModel):
    id: UUID
    regulation_id: UUID
    rule_name: str
    rule_type: str
    conditions: dict
    is_active: bool
    created_at: datetime
    severity: str
    description: Optional[str] = None
    expression: Optional[str] = None
    threshold: Optional[float] = None
    country: Optional[str] = None
    version: str

    class Config:
        from_attributes = True


class PaginatedPolicyRules(BaseModel):
    total: int
    page: int
    page_size: int
    items: List[PolicyRuleResponse]


class RegulationVersionResponse(BaseModel):
    id: UUID
    regulation_id: UUID
    version: str
    title: str
    extracted_text: str
    rules_snapshot: dict
    change_description: Optional[str] = None
    author_id: Optional[UUID] = None
    created_at: datetime

    class Config:
        from_attributes = True


class RollbackRequest(BaseModel):
    version_id: UUID
    reason: str


# ─── Phase 11: Continuous Monitoring & Re-Screening ─────────────────────────


class MonitoringScheduleResponse(BaseModel):
    id: UUID
    customer_id: UUID
    next_review_date: date
    review_frequency_months: int
    last_review_date: Optional[date] = None
    status: str
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class PaginatedMonitoringSchedules(BaseModel):
    total: int
    page: int
    page_size: int
    items: List[MonitoringScheduleResponse]


class MonitoringJobResponse(BaseModel):
    id: UUID
    customer_id: UUID
    status: str
    trigger_reason: str
    retry_count: int
    execution_time_ms: Optional[int] = None
    worker_name: Optional[str] = None
    error_message: Optional[str] = None
    case_id: Optional[UUID] = None
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class PaginatedMonitoringJobs(BaseModel):
    total: int
    page: int
    page_size: int
    items: List[MonitoringJobResponse]


class MonitoringHistoryResponse(BaseModel):
    id: UUID
    customer_id: UUID
    screening_date: datetime
    trigger_reason: str
    old_score: float
    new_score: float
    old_decision: str
    new_decision: str
    risk_delta: float
    new_alerts_count: int
    resolved_alerts_count: int
    risk_trend: str
    agents_executed: List[str]
    execution_time_ms: int
    case_id: Optional[UUID] = None
    risk_score_id: Optional[UUID] = None
    created_at: datetime

    class Config:
        from_attributes = True


class PaginatedMonitoringHistory(BaseModel):
    total: int
    page: int
    page_size: int
    items: List[MonitoringHistoryResponse]


class MonitoringStatistics(BaseModel):
    customers_under_monitoring: int
    todays_screenings: int
    queued_jobs: int
    running_jobs: int
    failed_jobs: int
    upcoming_reviews: int
    risk_changes_today: int
    completed_reviews: int


class RiskDeltaResponse(BaseModel):
    customer_id: UUID
    latest_score: float
    previous_score: float
    delta: float
    risk_trend: str
    new_alerts_count: int


# --- PHASE 12: INVESTIGATION WORKSPACE SCHEMAS ---


class InvestigationUpdate(BaseModel):
    status: Optional[str] = None
    risk_level: Optional[str] = None


class AssignmentCreate(BaseModel):
    assigned_to: UUID
    role: str = "investigator"  # investigator, supervisor


class CaseNoteCreate(BaseModel):
    note_text: str


class CaseNoteUpdate(BaseModel):
    note_text: str


class SARCreate(BaseModel):
    narrative: str
    reason: str
    risk_indicators: List[str]
    recommendation: str


class SARUpdate(BaseModel):
    status: str  # submitted, approved, rejected, archived


class CaseActionRequest(BaseModel):
    action: str  # close, reopen, escalate, return, edd_required


class EvidenceResponse(BaseModel):
    id: UUID
    investigation_id: UUID
    file_name: str
    evidence_type: str
    file_path: str
    description: Optional[str] = None
    uploaded_by: Optional[UUID] = None
    timestamp: datetime
    file_hash: str

    class Config:
        from_attributes = True


class CaseNoteResponse(BaseModel):
    id: UUID
    investigation_id: UUID
    author_id: Optional[UUID] = None
    note_text: str
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class SARResponse(BaseModel):
    id: UUID
    investigation_id: UUID
    sar_number: str
    narrative: str
    reason: str
    risk_indicators: List[str]
    recommendation: str
    status: str
    created_by: Optional[UUID] = None
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class TimelineEventResponse(BaseModel):
    id: UUID
    investigation_id: UUID
    event_type: str
    title: str
    description: str
    actor_id: Optional[UUID] = None
    timestamp: datetime

    class Config:
        from_attributes = True


class AssignmentResponse(BaseModel):
    id: UUID
    investigation_id: UUID
    assigned_by: Optional[UUID] = None
    assigned_to: Optional[UUID] = None
    role: str
    assigned_at: datetime

    class Config:
        from_attributes = True


class InvestigationResponse(BaseModel):
    id: UUID
    case_id: UUID
    customer_id: UUID
    assigned_to: Optional[UUID] = None
    assigned_supervisor_id: Optional[UUID] = None
    status: str
    risk_level: str
    ai_summary: Optional[dict] = None
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class PaginatedInvestigations(BaseModel):
    total: int
    page: int
    page_size: int
    items: List[InvestigationResponse]


class InvestigationWorkspacePayload(BaseModel):
    investigation: InvestigationResponse
    customer: Optional[dict] = None
    kyc_profile: Optional[dict] = None
    documents: List[dict] = []
    alerts: List[dict] = []
    transactions: List[dict] = []
    risk_scores: List[dict] = []
    monitoring_history: List[dict] = []
    notes: List[CaseNoteResponse]
    evidence: List[EvidenceResponse]
    sars: List[SARResponse]
    timeline: List[TimelineEventResponse]
    assignments: List[AssignmentResponse]


class InvestigatorWorkloadSchema(BaseModel):
    user_id: str
    email: str
    active_cases: int


class InvestigationDashboardMetrics(BaseModel):
    open_investigations: int
    pending_sar: int
    sar_submitted: int
    evidence_uploaded: int
    average_investigation_time_hours: float
    investigator_workload: List[InvestigatorWorkloadSchema]
    recently_assigned_cases: List[dict]


# --- PHASE 13: REPORTING & BI SCHEMAS ---


class ReportTemplateCreate(BaseModel):
    name: str
    description: Optional[str] = None
    config: dict


class ReportTemplateResponse(BaseModel):
    id: UUID
    name: str
    description: Optional[str] = None
    config: dict
    created_by: Optional[UUID] = None
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class ReportCreate(BaseModel):
    name: str
    template_id: Optional[UUID] = None
    format: str = "pdf"
    filters: dict = {}


class ReportResponse(BaseModel):
    id: UUID
    name: str
    template_id: Optional[UUID] = None
    generated_by: Optional[UUID] = None
    status: str
    format: str
    file_path: Optional[str] = None
    filters: dict
    created_at: datetime

    class Config:
        from_attributes = True


class ScheduledReportCreate(BaseModel):
    name: str
    template_id: UUID
    cron_expression: str


class ScheduledReportResponse(BaseModel):
    id: UUID
    name: str
    template_id: UUID
    cron_expression: str
    next_run: datetime
    status: str
    created_by: Optional[UUID] = None
    created_at: datetime

    class Config:
        from_attributes = True


class ScheduledReportUpdate(BaseModel):
    status: Optional[str] = None
    cron_expression: Optional[str] = None


class DashboardWidgetCreate(BaseModel):
    widget_type: str
    title: str
    config: dict
    position_x: int = 0
    position_y: int = 0
    width: int = 3
    height: int = 2


class DashboardWidgetResponse(BaseModel):
    id: UUID
    layout_id: UUID
    widget_type: str
    title: str
    config: dict
    position_x: int
    position_y: int
    width: int
    height: int

    class Config:
        from_attributes = True


class DashboardLayoutCreate(BaseModel):
    name: str
    is_default: bool = False
    config: dict = {}
    widgets: List[DashboardWidgetCreate] = []


class DashboardLayoutResponse(BaseModel):
    id: UUID
    name: str
    user_id: Optional[UUID] = None
    is_default: bool
    config: dict
    created_at: datetime
    widgets: List[DashboardWidgetResponse] = []

    class Config:
        from_attributes = True


# ─── PHASE 14 — EXTERNAL INTEGRATIONS & NOTIFICATIONS ────────────────────────


class IntegrationSettingCreate(BaseModel):
    provider_name: str
    provider_type: str
    base_url: Optional[str] = None
    api_key: Optional[str] = None
    api_secret: Optional[str] = None
    enabled: bool = True
    timeout: int = 30
    configuration: dict = {}


class IntegrationSettingUpdate(BaseModel):
    base_url: Optional[str] = None
    api_key: Optional[str] = None
    api_secret: Optional[str] = None
    enabled: Optional[bool] = None
    timeout: Optional[int] = None
    configuration: Optional[dict] = None


class IntegrationSettingResponse(BaseModel):
    id: UUID
    provider_name: str
    provider_type: str
    base_url: Optional[str] = None
    enabled: bool
    timeout: int
    configuration: dict
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class SyncHistoryResponse(BaseModel):
    id: UUID
    provider: str
    sync_type: str
    started_at: datetime
    completed_at: Optional[datetime] = None
    records_processed: int
    records_added: int
    records_updated: int
    records_failed: int
    status: str
    error_message: Optional[str] = None

    class Config:
        from_attributes = True


class NotificationTemplateCreate(BaseModel):
    name: str
    event_type: str
    channel: str
    subject: Optional[str] = None
    body: str
    variables: List[str] = []
    active: bool = True


class NotificationTemplateResponse(BaseModel):
    id: UUID
    name: str
    event_type: str
    channel: str
    subject: Optional[str] = None
    body: str
    variables: Optional[List] = []
    active: bool
    created_at: datetime

    class Config:
        from_attributes = True


class NotificationResponse(BaseModel):
    id: UUID
    user_id: Optional[UUID] = None
    template_id: Optional[UUID] = None
    channel: str
    title: str
    message: str
    priority: str
    status: str
    sent_at: Optional[datetime] = None
    retry_count: int
    created_at: datetime

    class Config:
        from_attributes = True


class WebhookEndpointCreate(BaseModel):
    name: str
    url: str
    secret: str
    enabled: bool = True
    events: List[str] = []
    retries: int = 3


class WebhookEndpointUpdate(BaseModel):
    name: Optional[str] = None
    url: Optional[str] = None
    enabled: Optional[bool] = None
    events: Optional[List[str]] = None
    retries: Optional[int] = None


class WebhookEndpointResponse(BaseModel):
    id: UUID
    name: str
    url: str
    enabled: bool
    events: Optional[List] = []
    retries: int
    created_at: datetime

    class Config:
        from_attributes = True


class WebhookLogResponse(BaseModel):
    id: UUID
    endpoint_id: UUID
    event: str
    signature: Optional[str] = None
    response_code: Optional[int] = None
    response_body: Optional[str] = None
    status: str
    retry_count: int
    created_at: datetime

    class Config:
        from_attributes = True


class ManualSyncRequest(BaseModel):
    provider: str
    sync_type: str = "manual"


class SendNotificationRequest(BaseModel):
    event_type: str
    channels: List[str] = ["in_app"]
    variables: dict = {}
    to_email: Optional[str] = None
    priority: str = "medium"
    user_id: Optional[UUID] = None


# ═══════════════════════════════════════════════════════════════════════════════
# PHASE 15 — ENTERPRISE SECURITY & OBSERVABILITY SCHEMAS
# ═══════════════════════════════════════════════════════════════════════════════


class MFAEnrollResponse(BaseModel):
    secret: str
    qr_code_base64: str
    backup_codes: List[str]
    otpauth_uri: str


class MFAVerifyRequest(BaseModel):
    code: str


class MFASetupResponse(BaseModel):
    success: bool
    message: str


class ChangePasswordRequest(BaseModel):
    old_password: str
    new_password: str


class LoginHistoryResponse(BaseModel):
    id: UUID
    user_id: Optional[UUID]
    email: Optional[str]
    ip_address: Optional[str]
    user_agent: Optional[str]
    success: bool
    failure_reason: Optional[str]
    country: Optional[str]
    created_at: datetime

    class Config:
        from_attributes = True


class BackupRecordResponse(BaseModel):
    id: UUID
    backup_type: str
    file_name: str
    file_size_bytes: Optional[int]
    sha256_checksum: Optional[str]
    status: str
    triggered_by: str
    error_message: Optional[str]
    expires_at: Optional[datetime]
    created_at: datetime
    completed_at: Optional[datetime]

    class Config:
        from_attributes = True


class SystemMetricResponse(BaseModel):
    metric_name: str
    metric_value: float
    unit: Optional[str]
    timestamp: datetime

    class Config:
        from_attributes = True


class HealthResponse(BaseModel):
    status: str
    latency_ms: float
    version: str
    timestamp: datetime
    details: Optional[dict] = None
