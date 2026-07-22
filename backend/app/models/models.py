from datetime import date, datetime
from typing import List, Optional
from sqlalchemy import (
    String,
    Text,
    Boolean,
    Integer,
    Numeric,
    Date,
    DateTime,
    ForeignKey,
    UUID,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.dialects.postgresql import JSONB
from uuid import uuid4
from app.core.database import Base


# 1. USERS TABLE
class User(Base):
    __tablename__ = "users"

    id: Mapped[UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid4
    )
    email: Mapped[str] = mapped_column(
        String(255), unique=True, nullable=False, index=True
    )
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    role: Mapped[str] = mapped_column(
        String(50), nullable=False
    )  # 'customer', 'compliance_officer', 'admin'
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow
    )
    failed_login_count: Mapped[int] = mapped_column(Integer, default=0, nullable=True)
    locked_until: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    password_changed_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, nullable=True
    )
    last_login_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    mfa_secret: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)

    @property
    def mfa_enabled(self) -> bool:
        return self.mfa_secret is not None

    # Relationships
    mfa_settings: Mapped[Optional["MFASettings"]] = relationship(
        back_populates="user", uselist=False
    )
    customer: Mapped[Optional["Customer"]] = relationship(
        back_populates="user", uselist=False
    )
    audit_logs: Mapped[List["AuditLog"]] = relationship(back_populates="user")
    regulations: Mapped[List["Regulation"]] = relationship(back_populates="uploaded_by")


# 2. CUSTOMERS TABLE
class Customer(Base):
    __tablename__ = "customers"

    id: Mapped[UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid4
    )
    user_id: Mapped[UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=True
    )
    customer_type: Mapped[str] = mapped_column(
        String(20), nullable=False
    )  # 'individual', 'corporate'
    first_name: Mapped[Optional[str]] = mapped_column(String(100))
    last_name: Mapped[Optional[str]] = mapped_column(String(100))
    dob: Mapped[Optional[date]] = mapped_column(Date)
    nationality: Mapped[Optional[str]] = mapped_column(String(100))
    phone_number: Mapped[Optional[str]] = mapped_column(String(50))
    street_address: Mapped[Optional[str]] = mapped_column(Text)
    city: Mapped[Optional[str]] = mapped_column(String(100))
    postal_code: Mapped[Optional[str]] = mapped_column(String(20))
    country: Mapped[Optional[str]] = mapped_column(String(100))
    status: Mapped[str] = mapped_column(String(50), default="onboarding")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow
    )

    # Relationships
    user: Mapped[Optional["User"]] = relationship(back_populates="customer")
    kyc_profile: Mapped[Optional["KYCProfile"]] = relationship(
        back_populates="customer", uselist=False
    )
    companies: Mapped[List["Company"]] = relationship(back_populates="customer")
    documents: Mapped[List["Document"]] = relationship(back_populates="customer")
    accounts: Mapped[List["Account"]] = relationship(back_populates="customer")
    risk_scores: Mapped[List["RiskScore"]] = relationship(back_populates="customer")
    monitoring_schedules: Mapped[List["MonitoringSchedule"]] = relationship(
        back_populates="customer"
    )
    alerts: Mapped[List["Alert"]] = relationship(back_populates="customer")
    cases: Mapped[List["Case"]] = relationship(back_populates="customer")
    monitoring_jobs: Mapped[List["MonitoringJob"]] = relationship(
        back_populates="customer", cascade="all, delete-orphan"
    )
    monitoring_histories: Mapped[List["MonitoringHistory"]] = relationship(
        back_populates="customer", cascade="all, delete-orphan"
    )
    investigations: Mapped[List["Investigation"]] = relationship(
        back_populates="customer", cascade="all, delete-orphan"
    )


# 3. COMPANIES TABLE
class Company(Base):
    __tablename__ = "companies"

    id: Mapped[UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid4
    )
    customer_id: Mapped[UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("customers.id", ondelete="CASCADE"),
        nullable=False,
    )
    company_name: Mapped[str] = mapped_column(String(255), nullable=False)
    registration_number: Mapped[str] = mapped_column(
        String(100), unique=True, nullable=False, index=True
    )
    registered_address: Mapped[str] = mapped_column(Text, nullable=False)
    trading_address: Mapped[Optional[str]] = mapped_column(Text)
    country_of_incorporation: Mapped[str] = mapped_column(String(100), nullable=False)
    incorporation_date: Mapped[Optional[date]] = mapped_column(Date)
    sic_code: Mapped[Optional[str]] = mapped_column(String(20))
    status: Mapped[str] = mapped_column(String(50), default="active")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow
    )

    # Relationships
    customer: Mapped["Customer"] = relationship(back_populates="companies")
    directors: Mapped[List["Director"]] = relationship(back_populates="company")
    ubos: Mapped[List["UBO"]] = relationship(back_populates="company")


# 4. DIRECTORS TABLE
class Director(Base):
    __tablename__ = "directors"

    id: Mapped[UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid4
    )
    company_id: Mapped[UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("companies.id", ondelete="CASCADE"),
        nullable=False,
    )
    first_name: Mapped[str] = mapped_column(String(100), nullable=False)
    last_name: Mapped[str] = mapped_column(String(100), nullable=False)
    dob: Mapped[Optional[date]] = mapped_column(Date)
    nationality: Mapped[Optional[str]] = mapped_column(String(100))
    appointment_date: Mapped[Optional[date]] = mapped_column(Date)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    verification_status: Mapped[str] = mapped_column(String(50), default="unverified")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    # Relationships
    company: Mapped["Company"] = relationship(back_populates="directors")


# 5. UBOS TABLE
class UBO(Base):
    __tablename__ = "ubos"

    id: Mapped[UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid4
    )
    company_id: Mapped[UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("companies.id", ondelete="CASCADE"),
        nullable=False,
    )
    first_name: Mapped[str] = mapped_column(String(100), nullable=False)
    last_name: Mapped[str] = mapped_column(String(100), nullable=False)
    dob: Mapped[Optional[date]] = mapped_column(Date)
    nationality: Mapped[Optional[str]] = mapped_column(String(100))
    ownership_percentage: Mapped[float] = mapped_column(Numeric(5, 2), nullable=False)
    control_type: Mapped[str] = mapped_column(String(100), nullable=False)
    verification_status: Mapped[str] = mapped_column(String(50), default="unverified")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    # Relationships
    company: Mapped["Company"] = relationship(back_populates="ubos")


# 6. KYC_PROFILES TABLE
class KYCProfile(Base):
    __tablename__ = "kyc_profiles"
    __table_args__ = (
        UniqueConstraint("customer_id", name="uq_kyc_profiles_customer_id"),
    )

    id: Mapped[UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid4
    )
    customer_id: Mapped[UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("customers.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    full_name: Mapped[str] = mapped_column(String(255), nullable=False)
    date_of_birth: Mapped[date] = mapped_column(Date, nullable=False)
    nationality: Mapped[str] = mapped_column(String(100), nullable=False)
    address: Mapped[str] = mapped_column(Text, nullable=False)
    source_of_funds: Mapped[str] = mapped_column(String(255), nullable=False)
    source_of_wealth: Mapped[str] = mapped_column(String(255), nullable=False)
    occupation: Mapped[Optional[str]] = mapped_column(String(100))
    risk_category: Mapped[str] = mapped_column(String(50), default="low")
    annual_income_range: Mapped[Optional[str]] = mapped_column(String(100))
    tax_residency: Mapped[Optional[str]] = mapped_column(String(100))
    expected_activity_desc: Mapped[Optional[str]] = mapped_column(Text)
    screening_completed_at: Mapped[Optional[datetime]] = mapped_column(DateTime)
    notes: Mapped[Optional[str]] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow
    )

    # Relationships
    customer: Mapped["Customer"] = relationship(back_populates="kyc_profile")


# 7. DOCUMENTS TABLE
class Document(Base):
    __tablename__ = "documents"

    id: Mapped[UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid4
    )
    customer_id: Mapped[UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("customers.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    document_type: Mapped[str] = mapped_column(String(100), nullable=False)
    file_name: Mapped[str] = mapped_column(String(255), nullable=False)
    file_path: Mapped[str] = mapped_column(Text, nullable=False)
    content_type: Mapped[Optional[str]] = mapped_column(String(100))
    file_size: Mapped[Optional[int]] = mapped_column(Integer)
    ocr_data: Mapped[Optional[dict]] = mapped_column(JSONB)
    verification_status: Mapped[str] = mapped_column(String(50), default="uploaded")
    verification_metadata: Mapped[Optional[dict]] = mapped_column(JSONB)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow
    )

    # Relationships
    customer: Mapped["Customer"] = relationship(back_populates="documents")


# 8. ACCOUNTS TABLE
class Account(Base):
    __tablename__ = "accounts"

    id: Mapped[UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid4
    )
    customer_id: Mapped[UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("customers.id", ondelete="CASCADE"),
        nullable=False,
    )
    account_number: Mapped[str] = mapped_column(
        String(50), unique=True, nullable=False, index=True
    )
    sort_code: Mapped[str] = mapped_column(String(20), nullable=False)
    currency: Mapped[str] = mapped_column(String(10), default="GBP")
    balance: Mapped[float] = mapped_column(Numeric(15, 4), default=0.0000)
    status: Mapped[str] = mapped_column(String(50), default="active")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow
    )

    # Relationships
    customer: Mapped["Customer"] = relationship(back_populates="accounts")
    transactions: Mapped[List["Transaction"]] = relationship(
        back_populates="sender_account"
    )


# 9. TRANSACTIONS TABLE
class Transaction(Base):
    __tablename__ = "transactions"

    id: Mapped[UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid4
    )
    sender_account_id: Mapped[UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("accounts.id", ondelete="CASCADE"),
        nullable=False,
    )
    receiver_account_number: Mapped[str] = mapped_column(String(50), nullable=False)
    receiver_sort_code: Mapped[str] = mapped_column(String(20), nullable=False)
    receiver_name: Mapped[str] = mapped_column(String(255), nullable=False)
    receiver_country: Mapped[str] = mapped_column(String(100), nullable=False)
    amount: Mapped[float] = mapped_column(Numeric(15, 4), nullable=False)
    currency: Mapped[str] = mapped_column(String(10), default="GBP")
    transaction_type: Mapped[str] = mapped_column(String(50), nullable=False)
    status: Mapped[str] = mapped_column(String(50), default="pending")
    reference: Mapped[Optional[str]] = mapped_column(String(255))
    completed_at: Mapped[Optional[datetime]] = mapped_column(DateTime)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    # Relationships
    sender_account: Mapped["Account"] = relationship(back_populates="transactions")
    alerts: Mapped[List["Alert"]] = relationship(back_populates="transaction")


# 10. ALERTS TABLE
class Alert(Base):
    __tablename__ = "alerts"

    id: Mapped[UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid4
    )
    customer_id: Mapped[UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("customers.id", ondelete="CASCADE"),
        nullable=False,
    )
    transaction_id: Mapped[Optional[UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("transactions.id", ondelete="SET NULL")
    )
    alert_type: Mapped[str] = mapped_column(String(100), nullable=False)
    risk_score: Mapped[float] = mapped_column(Numeric(5, 2), nullable=False)
    status: Mapped[str] = mapped_column(String(50), default="open")
    alert_metadata: Mapped[Optional[dict]] = mapped_column(JSONB)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow
    )

    # Relationships
    customer: Mapped["Customer"] = relationship(back_populates="alerts")
    transaction: Mapped[Optional["Transaction"]] = relationship(back_populates="alerts")


# 11. CASES TABLE
class Case(Base):
    __tablename__ = "cases"

    id: Mapped[UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid4
    )
    customer_id: Mapped[UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("customers.id", ondelete="CASCADE"),
        nullable=False,
    )
    assigned_to: Mapped[Optional[UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL")
    )
    priority: Mapped[str] = mapped_column(String(20), default="medium")
    status: Mapped[str] = mapped_column(String(50), default="new")
    investigation_notes: Mapped[Optional[str]] = mapped_column(Text)
    sar_filed: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow
    )

    # Relationships
    customer: Mapped["Customer"] = relationship(back_populates="cases")
    agent_logs: Mapped[List["AgentLog"]] = relationship(back_populates="case")
    investigation: Mapped[Optional["Investigation"]] = relationship(
        back_populates="case", uselist=False
    )


# 12. RISK_SCORES TABLE
class RiskScore(Base):
    __tablename__ = "risk_scores"

    id: Mapped[UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid4
    )
    customer_id: Mapped[UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("customers.id", ondelete="CASCADE"),
        nullable=False,
    )
    overall_score: Mapped[float] = mapped_column(Numeric(5, 2), nullable=False)
    risk_tier: Mapped[str] = mapped_column(String(20), nullable=False)
    breakdown: Mapped[dict] = mapped_column(JSONB, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    # Relationships
    customer: Mapped["Customer"] = relationship(back_populates="risk_scores")


# 13. MONITORING_SCHEDULE TABLE
class MonitoringSchedule(Base):
    __tablename__ = "monitoring_schedule"

    id: Mapped[UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid4
    )
    customer_id: Mapped[UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("customers.id", ondelete="CASCADE"),
        nullable=False,
    )
    next_review_date: Mapped[date] = mapped_column(Date, nullable=False)
    review_frequency_months: Mapped[int] = mapped_column(Integer, nullable=False)
    last_review_date: Mapped[Optional[date]] = mapped_column(Date)
    status: Mapped[str] = mapped_column(String(50), default="scheduled")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow
    )

    # Relationships
    customer: Mapped["Customer"] = relationship(back_populates="monitoring_schedules")


# 14. AUDIT_LOGS TABLE
class AuditLog(Base):
    __tablename__ = "audit_logs"

    id: Mapped[UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid4
    )
    user_id: Mapped[Optional[UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL")
    )
    action: Mapped[str] = mapped_column(String(255), nullable=False)
    entity_name: Mapped[str] = mapped_column(String(100), nullable=False)
    entity_id: Mapped[UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    old_values: Mapped[Optional[dict]] = mapped_column(JSONB)
    new_values: Mapped[Optional[dict]] = mapped_column(JSONB)
    ip_address: Mapped[Optional[str]] = mapped_column(String(45))
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    # Relationships
    user: Mapped[Optional["User"]] = relationship(back_populates="audit_logs")


# 15. AGENT_LOGS TABLE
class AgentLog(Base):
    __tablename__ = "agent_logs"

    id: Mapped[UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid4
    )
    case_id: Mapped[UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("cases.id", ondelete="CASCADE"), nullable=False
    )
    agent_name: Mapped[str] = mapped_column(String(100), nullable=False)
    step_name: Mapped[str] = mapped_column(String(100), nullable=False)
    input_state: Mapped[Optional[dict]] = mapped_column(JSONB)
    output_state: Mapped[Optional[dict]] = mapped_column(JSONB)
    execution_time_ms: Mapped[Optional[int]] = mapped_column(Integer)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    # Relationships
    case: Mapped["Case"] = relationship(back_populates="agent_logs")


from sqlalchemy import Date, Numeric


# 16. REGULATIONS TABLE
class Regulation(Base):
    __tablename__ = "regulations"

    id: Mapped[UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid4
    )
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    authority: Mapped[str] = mapped_column(String(100), nullable=False)
    upload_path: Mapped[str] = mapped_column(Text, nullable=False)
    uploaded_by_id: Mapped[Optional[UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL")
    )
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    # Phase 10 Extended Fields
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    country: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    jurisdiction: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    regulator: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    regulation_type: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    version: Mapped[Optional[str]] = mapped_column(String(50), default="1.0.0")
    effective_date: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    expiry_date: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    status: Mapped[str] = mapped_column(
        String(50), default="active"
    )  # active, archived, draft, pending_review
    extracted_text: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    document_metadata: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)

    # Relationships
    uploaded_by: Mapped[Optional["User"]] = relationship(back_populates="regulations")
    policy_rules: Mapped[List["PolicyRule"]] = relationship(back_populates="regulation")
    versions: Mapped[List["RegulationVersion"]] = relationship(
        back_populates="regulation", cascade="all, delete-orphan"
    )


# 17. POLICY_RULES TABLE
class PolicyRule(Base):
    __tablename__ = "policy_rules"

    id: Mapped[UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid4
    )
    regulation_id: Mapped[UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("regulations.id", ondelete="CASCADE"),
        nullable=False,
    )
    rule_name: Mapped[str] = mapped_column(String(255), nullable=False)
    rule_type: Mapped[str] = mapped_column(
        String(100), nullable=False
    )  # 'threshold', 'block', 'edd', 'aml', 'kyc', 'internal'
    conditions: Mapped[dict] = mapped_column(JSONB, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    # Phase 10 Extended Fields
    severity: Mapped[str] = mapped_column(
        String(50), default="medium"
    )  # critical, high, medium, low
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    expression: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    threshold: Mapped[Optional[float]] = mapped_column(Numeric(15, 4), nullable=True)
    country: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    version: Mapped[str] = mapped_column(String(50), default="1.0.0")

    # Relationships
    regulation: Mapped["Regulation"] = relationship(back_populates="policy_rules")


# 18. REGULATION_VERSIONS TABLE (Phase 10)
class RegulationVersion(Base):
    __tablename__ = "regulation_versions"

    id: Mapped[UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid4
    )
    regulation_id: Mapped[UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("regulations.id", ondelete="CASCADE"),
        nullable=False,
    )
    version: Mapped[str] = mapped_column(String(50), nullable=False)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    extracted_text: Mapped[str] = mapped_column(Text, nullable=False)
    rules_snapshot: Mapped[dict] = mapped_column(JSONB, nullable=False)
    change_description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    author_id: Mapped[Optional[UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    # Relationships
    regulation: Mapped["Regulation"] = relationship(back_populates="versions")


# 19. MONITORING_JOBS TABLE (Phase 11)
class MonitoringJob(Base):
    __tablename__ = "monitoring_jobs"

    id: Mapped[UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid4
    )
    customer_id: Mapped[UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("customers.id", ondelete="CASCADE"),
        nullable=False,
    )
    status: Mapped[str] = mapped_column(
        String(50), default="queued"
    )  # queued, running, completed, failed
    trigger_reason: Mapped[str] = mapped_column(String(100), nullable=False)
    retry_count: Mapped[int] = mapped_column(Integer, default=0)
    execution_time_ms: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    worker_name: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    error_message: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    case_id: Mapped[Optional[UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("cases.id", ondelete="SET NULL"), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow
    )

    # Relationships
    customer: Mapped["Customer"] = relationship(back_populates="monitoring_jobs")
    case: Mapped[Optional["Case"]] = relationship()


# 20. MONITORING_HISTORY TABLE (Phase 11)
class MonitoringHistory(Base):
    __tablename__ = "monitoring_history"

    id: Mapped[UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid4
    )
    customer_id: Mapped[UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("customers.id", ondelete="CASCADE"),
        nullable=False,
    )
    screening_date: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    trigger_reason: Mapped[str] = mapped_column(String(100), nullable=False)
    old_score: Mapped[float] = mapped_column(Numeric(5, 2), nullable=False)
    new_score: Mapped[float] = mapped_column(Numeric(5, 2), nullable=False)
    old_decision: Mapped[str] = mapped_column(String(50), nullable=False)
    new_decision: Mapped[str] = mapped_column(String(50), nullable=False)
    risk_delta: Mapped[float] = mapped_column(Numeric(5, 2), nullable=False)
    new_alerts_count: Mapped[int] = mapped_column(Integer, default=0)
    resolved_alerts_count: Mapped[int] = mapped_column(Integer, default=0)
    risk_trend: Mapped[str] = mapped_column(
        String(50), default="stable"
    )  # improving, stable, deteriorating
    agents_executed: Mapped[dict] = mapped_column(
        JSONB, nullable=False
    )  # stores list of agent names as json array
    execution_time_ms: Mapped[int] = mapped_column(Integer, default=0)
    case_id: Mapped[Optional[UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("cases.id", ondelete="SET NULL"), nullable=True
    )
    risk_score_id: Mapped[Optional[UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("risk_scores.id", ondelete="SET NULL"),
        nullable=True,
    )
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    # Relationships
    customer: Mapped["Customer"] = relationship(back_populates="monitoring_histories")
    case: Mapped[Optional["Case"]] = relationship()
    risk_score: Mapped[Optional["RiskScore"]] = relationship()


# 21. INVESTIGATIONS TABLE (Phase 12)
class Investigation(Base):
    __tablename__ = "investigations"

    id: Mapped[UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid4
    )
    case_id: Mapped[UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("cases.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
    )
    customer_id: Mapped[UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("customers.id", ondelete="CASCADE"),
        nullable=False,
    )
    assigned_to: Mapped[Optional[UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    assigned_supervisor_id: Mapped[Optional[UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    status: Mapped[str] = mapped_column(
        String(50), default="open"
    )  # open, under_review, escalated, edd_required, closed
    risk_level: Mapped[str] = mapped_column(String(50), default="medium")
    ai_summary: Mapped[Optional[dict]] = mapped_column(
        JSONB
    )  # case_summary, suspicious_behaviour_analysis, recommended_next_actions, questions_for_investigator, missing_evidence_suggestions, risk_explanation
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow
    )

    # Relationships
    case: Mapped["Case"] = relationship(back_populates="investigation")
    customer: Mapped["Customer"] = relationship(back_populates="investigations")
    assigned_officer: Mapped[Optional["User"]] = relationship(
        foreign_keys=[assigned_to]
    )
    supervisor: Mapped[Optional["User"]] = relationship(
        foreign_keys=[assigned_supervisor_id]
    )
    evidences: Mapped[List["Evidence"]] = relationship(
        back_populates="investigation", cascade="all, delete-orphan"
    )
    notes: Mapped[List["CaseNote"]] = relationship(
        back_populates="investigation", cascade="all, delete-orphan"
    )
    sars: Mapped[List["SAR"]] = relationship(
        back_populates="investigation", cascade="all, delete-orphan"
    )
    timeline_events: Mapped[List["TimelineEvent"]] = relationship(
        back_populates="investigation", cascade="all, delete-orphan"
    )
    assignments: Mapped[List["Assignment"]] = relationship(
        back_populates="investigation", cascade="all, delete-orphan"
    )


# 22. EVIDENCE TABLE (Phase 12)
class Evidence(Base):
    __tablename__ = "evidences"

    id: Mapped[UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid4
    )
    investigation_id: Mapped[UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("investigations.id", ondelete="CASCADE"),
        nullable=False,
    )
    file_name: Mapped[str] = mapped_column(String(255), nullable=False)
    evidence_type: Mapped[str] = mapped_column(
        String(50), nullable=False
    )  # pdf, docx, image, csv, zip, audio, video
    file_path: Mapped[str] = mapped_column(Text, nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text)
    uploaded_by: Mapped[Optional[UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    timestamp: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    file_hash: Mapped[str] = mapped_column(String(64), nullable=False)

    # Relationships
    investigation: Mapped["Investigation"] = relationship(back_populates="evidences")
    uploader: Mapped[Optional["User"]] = relationship()


# 23. CASENOTE TABLE (Phase 12)
class CaseNote(Base):
    __tablename__ = "case_notes"

    id: Mapped[UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid4
    )
    investigation_id: Mapped[UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("investigations.id", ondelete="CASCADE"),
        nullable=False,
    )
    author_id: Mapped[Optional[UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    note_text: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow
    )

    # Relationships
    investigation: Mapped["Investigation"] = relationship(back_populates="notes")
    author: Mapped[Optional["User"]] = relationship()


# 24. SAR TABLE (Phase 12)
class SAR(Base):
    __tablename__ = "sars"

    id: Mapped[UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid4
    )
    investigation_id: Mapped[UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("investigations.id", ondelete="CASCADE"),
        nullable=False,
    )
    sar_number: Mapped[str] = mapped_column(String(50), nullable=False, unique=True)
    narrative: Mapped[str] = mapped_column(Text, nullable=False)
    reason: Mapped[str] = mapped_column(Text, nullable=False)
    risk_indicators: Mapped[dict] = mapped_column(
        JSONB, nullable=False
    )  # JSON list of risk indicator tags
    recommendation: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(
        String(50), default="draft"
    )  # draft, submitted, approved, rejected, archived
    created_by: Mapped[Optional[UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow
    )

    # Relationships
    investigation: Mapped["Investigation"] = relationship(back_populates="sars")
    creator: Mapped[Optional["User"]] = relationship()


# 25. TIMELINEEVENT TABLE (Phase 12)
class TimelineEvent(Base):
    __tablename__ = "timeline_events"

    id: Mapped[UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid4
    )
    investigation_id: Mapped[UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("investigations.id", ondelete="CASCADE"),
        nullable=False,
    )
    event_type: Mapped[str] = mapped_column(String(100), nullable=False)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    actor_id: Mapped[Optional[UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    timestamp: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    # Relationships
    investigation: Mapped["Investigation"] = relationship(
        back_populates="timeline_events"
    )
    actor: Mapped[Optional["User"]] = relationship()


# 26. ASSIGNMENT TABLE (Phase 12)
class Assignment(Base):
    __tablename__ = "assignments"

    id: Mapped[UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid4
    )
    investigation_id: Mapped[UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("investigations.id", ondelete="CASCADE"),
        nullable=False,
    )
    assigned_by: Mapped[Optional[UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    assigned_to: Mapped[Optional[UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    role: Mapped[str] = mapped_column(
        String(50), default="investigator"
    )  # investigator, supervisor
    assigned_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    # Relationships
    investigation: Mapped["Investigation"] = relationship(back_populates="assignments")
    assigner: Mapped[Optional["User"]] = relationship(foreign_keys=[assigned_by])
    assignee: Mapped[Optional["User"]] = relationship(foreign_keys=[assigned_to])


# --- PHASE 13: REPORTING & BI SYSTEM MODELS ---


class ReportTemplate(Base):
    __tablename__ = "report_templates"

    id: Mapped[UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid4
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    config: Mapped[dict] = mapped_column(
        JSONB, nullable=False
    )  # fields, charts, tables config
    created_by: Mapped[Optional[UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow
    )

    # Relationships
    creator: Mapped[Optional["User"]] = relationship()


class Report(Base):
    __tablename__ = "reports"

    id: Mapped[UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid4
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    template_id: Mapped[Optional[UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("report_templates.id", ondelete="SET NULL"),
        nullable=True,
    )
    generated_by: Mapped[Optional[UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    status: Mapped[str] = mapped_column(
        String(50), default="pending"
    )  # pending, completed, failed
    format: Mapped[str] = mapped_column(
        String(20), default="pdf"
    )  # pdf, excel, csv, json
    file_path: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    filters: Mapped[dict] = mapped_column(
        JSONB, nullable=False, default=dict
    )  # date range, customer, countries, etc.
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    # Relationships
    template: Mapped[Optional["ReportTemplate"]] = relationship()
    generator: Mapped[Optional["User"]] = relationship()


class ScheduledReport(Base):
    __tablename__ = "scheduled_reports"

    id: Mapped[UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid4
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    template_id: Mapped[UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("report_templates.id", ondelete="CASCADE"),
        nullable=False,
    )
    cron_expression: Mapped[str] = mapped_column(
        String(100), nullable=False
    )  # daily, weekly, etc. or standard cron
    next_run: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    status: Mapped[str] = mapped_column(
        String(50), default="active"
    )  # active, paused, deleted
    created_by: Mapped[Optional[UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    # Relationships
    template: Mapped["ReportTemplate"] = relationship()
    creator: Mapped[Optional["User"]] = relationship()


class ReportExecution(Base):
    __tablename__ = "report_executions"

    id: Mapped[UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid4
    )
    schedule_id: Mapped[UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("scheduled_reports.id", ondelete="CASCADE"),
        nullable=False,
    )
    report_id: Mapped[Optional[UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("reports.id", ondelete="SET NULL"), nullable=True
    )
    status: Mapped[str] = mapped_column(
        String(50), default="success"
    )  # success, failed
    error_message: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    executed_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    # Relationships
    schedule: Mapped["ScheduledReport"] = relationship()
    report: Mapped[Optional["Report"]] = relationship()


class DashboardLayout(Base):
    __tablename__ = "dashboard_layouts"

    id: Mapped[UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid4
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    user_id: Mapped[Optional[UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=True
    )
    is_default: Mapped[bool] = mapped_column(Boolean, default=False)
    config: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    # Relationships
    user: Mapped[Optional["User"]] = relationship()
    widgets: Mapped[List["DashboardWidget"]] = relationship(
        back_populates="layout", cascade="all, delete-orphan"
    )


class DashboardWidget(Base):
    __tablename__ = "dashboard_widgets"

    id: Mapped[UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid4
    )
    layout_id: Mapped[UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("dashboard_layouts.id", ondelete="CASCADE"),
        nullable=False,
    )
    widget_type: Mapped[str] = mapped_column(
        String(100), nullable=False
    )  # chart_bar, chart_pie, kpi_card, etc.
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    config: Mapped[dict] = mapped_column(JSONB, nullable=False)
    position_x: Mapped[int] = mapped_column(Integer, default=0)
    position_y: Mapped[int] = mapped_column(Integer, default=0)
    width: Mapped[int] = mapped_column(Integer, default=3)
    height: Mapped[int] = mapped_column(Integer, default=2)

    # Relationships
    layout: Mapped["DashboardLayout"] = relationship(back_populates="widgets")


# ─── PHASE 14 — EXTERNAL INTEGRATIONS & NOTIFICATIONS ──────────────────────


class IntegrationSetting(Base):
    """Stores configuration for external compliance providers and channel integrations."""

    __tablename__ = "integration_settings"

    id: Mapped[UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid4
    )
    provider_name: Mapped[str] = mapped_column(String(100), nullable=False, unique=True)
    provider_type: Mapped[str] = mapped_column(
        String(50), nullable=False
    )  # sanctions, pep, company, notification
    base_url: Mapped[Optional[str]] = mapped_column(String(500))
    api_key: Mapped[Optional[str]] = mapped_column(Text)
    api_secret: Mapped[Optional[str]] = mapped_column(Text)
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    timeout: Mapped[int] = mapped_column(Integer, default=30)
    configuration: Mapped[dict] = mapped_column(JSONB, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow
    )


class SyncHistory(Base):
    """Tracks each synchronization attempt against an external compliance provider."""

    __tablename__ = "sync_history"

    id: Mapped[UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid4
    )
    provider: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    sync_type: Mapped[str] = mapped_column(
        String(50), nullable=False
    )  # manual, scheduled, incremental
    started_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    completed_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    records_processed: Mapped[int] = mapped_column(Integer, default=0)
    records_added: Mapped[int] = mapped_column(Integer, default=0)
    records_updated: Mapped[int] = mapped_column(Integer, default=0)
    records_failed: Mapped[int] = mapped_column(Integer, default=0)
    status: Mapped[str] = mapped_column(
        String(50), default="started"
    )  # started, completed, failed
    error_message: Mapped[Optional[str]] = mapped_column(Text, nullable=True)


class NotificationTemplate(Base):
    """Defines reusable notification templates with channel-specific formatting."""

    __tablename__ = "notification_templates"

    id: Mapped[UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid4
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    event_type: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    channel: Mapped[str] = mapped_column(
        String(50), nullable=False
    )  # email, slack, teams, in_app
    subject: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    body: Mapped[str] = mapped_column(Text, nullable=False)
    variables: Mapped[dict] = mapped_column(JSONB, default=list)
    active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow
    )

    # Relationships
    notifications: Mapped[List["Notification"]] = relationship(
        back_populates="template"
    )


class Notification(Base):
    """Records every dispatched notification across all channels."""

    __tablename__ = "notifications"

    id: Mapped[UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid4
    )
    user_id: Mapped[Optional[UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    template_id: Mapped[Optional[UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("notification_templates.id", ondelete="SET NULL"),
        nullable=True,
    )
    channel: Mapped[str] = mapped_column(
        String(50), nullable=False
    )  # email, slack, teams, in_app, webhook
    title: Mapped[str] = mapped_column(String(500), nullable=False)
    message: Mapped[str] = mapped_column(Text, nullable=False)
    priority: Mapped[str] = mapped_column(
        String(20), default="medium"
    )  # low, medium, high, urgent
    status: Mapped[str] = mapped_column(
        String(50), default="pending"
    )  # pending, sent, failed, retry
    sent_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    retry_count: Mapped[int] = mapped_column(Integer, default=0)
    metadata_: Mapped[dict] = mapped_column("metadata", JSONB, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    # Relationships
    user: Mapped[Optional["User"]] = relationship()
    template: Mapped[Optional["NotificationTemplate"]] = relationship(
        back_populates="notifications"
    )


class WebhookEndpoint(Base):
    """Defines outgoing webhook targets that receive compliance event payloads."""

    __tablename__ = "webhook_endpoints"

    id: Mapped[UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid4
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    url: Mapped[str] = mapped_column(String(1000), nullable=False)
    secret: Mapped[str] = mapped_column(String(500), nullable=False)
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    events: Mapped[dict] = mapped_column(JSONB, default=list)
    retries: Mapped[int] = mapped_column(Integer, default=3)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow
    )

    # Relationships
    logs: Mapped[List["WebhookLog"]] = relationship(
        back_populates="endpoint", cascade="all, delete-orphan"
    )


class WebhookLog(Base):
    """Tracks every webhook dispatch attempt including signatures and response codes."""

    __tablename__ = "webhook_logs"

    id: Mapped[UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid4
    )
    endpoint_id: Mapped[UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("webhook_endpoints.id", ondelete="CASCADE"),
        nullable=False,
    )
    event: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    payload: Mapped[dict] = mapped_column(JSONB, default=dict)
    signature: Mapped[Optional[str]] = mapped_column(String(256), nullable=True)
    response_code: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    response_body: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(
        String(50), default="pending"
    )  # success, failed, retry
    retry_count: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    # Relationships
    endpoint: Mapped["WebhookEndpoint"] = relationship(back_populates="logs")


# ═══════════════════════════════════════════════════════════════════════════════
# PHASE 15 — ENTERPRISE SECURITY & OBSERVABILITY MODELS
# ═══════════════════════════════════════════════════════════════════════════════


class LoginHistory(Base):
    """Tracks every login attempt (success or failure) for audit and security analysis."""

    __tablename__ = "login_history"

    id: Mapped[UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid4
    )
    user_id: Mapped[Optional[UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    email: Mapped[Optional[str]] = mapped_column(
        String(255), nullable=True, index=True
    )  # Store email even if user not found
    ip_address: Mapped[Optional[str]] = mapped_column(
        String(45), nullable=True
    )  # IPv4 or IPv6
    user_agent: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    device_fingerprint: Mapped[Optional[str]] = mapped_column(
        String(255), nullable=True
    )
    success: Mapped[bool] = mapped_column(Boolean, default=False)
    failure_reason: Mapped[Optional[str]] = mapped_column(
        String(200), nullable=True
    )  # wrong_password, account_locked, etc.
    country: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, index=True
    )


class RevokedToken(Base):
    """Token revocation list — prevents reuse of logged-out or compromised JWTs."""

    __tablename__ = "revoked_tokens"

    id: Mapped[UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid4
    )
    jti: Mapped[str] = mapped_column(
        String(255), unique=True, nullable=False, index=True
    )  # JWT ID
    user_id: Mapped[Optional[UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=True
    )
    token_type: Mapped[str] = mapped_column(
        String(20), default="access"
    )  # access / refresh
    reason: Mapped[Optional[str]] = mapped_column(
        String(200), nullable=True
    )  # logout, password_changed, admin_revoke
    revoked_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, index=True
    )
    expires_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime, nullable=True
    )  # Auto-cleanup after expiry


class PasswordHistory(Base):
    """Stores previous password hashes to prevent re-use (configurable history count)."""

    __tablename__ = "password_history"

    id: Mapped[UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid4
    )
    user_id: Mapped[UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class MFASettings(Base):
    """Stores TOTP MFA configuration per user including backup codes."""

    __tablename__ = "mfa_settings"

    id: Mapped[UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid4
    )
    user_id: Mapped[UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        unique=True,
        nullable=False,
    )
    enabled: Mapped[bool] = mapped_column(Boolean, default=False)
    secret: Mapped[Optional[str]] = mapped_column(
        String(500), nullable=True
    )  # Encrypted TOTP secret
    backup_codes: Mapped[Optional[str]] = mapped_column(
        Text, nullable=True
    )  # JSON list of hashed backup codes
    setup_completed: Mapped[bool] = mapped_column(Boolean, default=False)
    last_used_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow
    )

    # Relationships
    user: Mapped["User"] = relationship(back_populates="mfa_settings")


class SecurityEvent(Base):
    """Records significant security events separate from general audit logs."""

    __tablename__ = "security_events"

    id: Mapped[UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid4
    )
    event_type: Mapped[str] = mapped_column(
        String(100), nullable=False, index=True
    )  # ACCOUNT_LOCKED, BRUTE_FORCE, etc.
    severity: Mapped[str] = mapped_column(
        String(20), default="medium"
    )  # low, medium, high, critical
    user_id: Mapped[Optional[UUID]] = mapped_column(UUID(as_uuid=True), nullable=True)
    ip_address: Mapped[Optional[str]] = mapped_column(String(45), nullable=True)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    metadata_: Mapped[dict] = mapped_column("metadata", JSONB, default=dict)
    resolved: Mapped[bool] = mapped_column(Boolean, default=False)
    resolved_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, index=True
    )


class SystemMetric(Base):
    """Time-series system performance metrics (CPU, memory, disk, latencies)."""

    __tablename__ = "system_metrics"

    id: Mapped[UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid4
    )
    metric_name: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    metric_value: Mapped[float] = mapped_column(Numeric(20, 6), nullable=False)
    unit: Mapped[Optional[str]] = mapped_column(
        String(50), nullable=True
    )  # %, ms, MB, req/s, etc.
    tags: Mapped[dict] = mapped_column(JSONB, default=dict)  # {host, service, env}
    timestamp: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, index=True
    )


class BackupRecord(Base):
    """Records of all database and document backups."""

    __tablename__ = "backup_records"

    id: Mapped[UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid4
    )
    backup_type: Mapped[str] = mapped_column(
        String(50), nullable=False
    )  # database, documents, config, full
    file_path: Mapped[str] = mapped_column(String(1000), nullable=False)
    file_name: Mapped[str] = mapped_column(String(500), nullable=False)
    file_size_bytes: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    sha256_checksum: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    status: Mapped[str] = mapped_column(
        String(50), default="pending"
    )  # pending, completed, failed, verified
    triggered_by: Mapped[str] = mapped_column(
        String(50), default="scheduled"
    )  # scheduled, manual, admin
    error_message: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    compressed: Mapped[bool] = mapped_column(Boolean, default=True)
    expires_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, index=True
    )
    completed_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)


class CacheStatistic(Base):
    """Periodic snapshots of cache hit/miss rates for trend analysis."""

    __tablename__ = "cache_statistics"

    id: Mapped[UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid4
    )
    backend: Mapped[str] = mapped_column(String(20), default="redis")  # redis, memory
    hits: Mapped[int] = mapped_column(Integer, default=0)
    misses: Mapped[int] = mapped_column(Integer, default=0)
    sets: Mapped[int] = mapped_column(Integer, default=0)
    deletes: Mapped[int] = mapped_column(Integer, default=0)
    hit_rate: Mapped[Optional[float]] = mapped_column(Numeric(5, 2), nullable=True)
    recorded_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, index=True
    )


# ─── PHASE 17: AI GOVERNANCE & EXPLAINABILITY MODELS ───────────────────────────

from sqlalchemy import JSON


class AIModel(Base):
    """Registry of AI models and provider details."""

    __tablename__ = "ai_models"

    id: Mapped[UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid4
    )
    name: Mapped[str] = mapped_column(
        String(100), unique=True, nullable=False, index=True
    )
    provider: Mapped[str] = mapped_column(
        String(50), nullable=False
    )  # 'gemini', 'openai', etc.
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow
    )

    versions: Mapped[List["ModelVersion"]] = relationship(
        back_populates="model", cascade="all, delete-orphan"
    )


class ModelVersion(Base):
    """Tracks specific version snapshots of registered AI models."""

    __tablename__ = "model_versions"

    id: Mapped[UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid4
    )
    model_id: Mapped[UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("ai_models.id", ondelete="CASCADE"),
        nullable=False,
    )
    version: Mapped[str] = mapped_column(String(50), nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    metadata_json: Mapped[dict] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    model: Mapped["AIModel"] = relationship(back_populates="versions")
    executions: Mapped[List["AIExecution"]] = relationship(
        back_populates="model_version"
    )
    evaluations: Mapped[List["ModelEvaluation"]] = relationship(
        back_populates="model_version", cascade="all, delete-orphan"
    )


class PromptTemplate(Base):
    """Logical grouping for versioned LLM prompt configurations."""

    __tablename__ = "prompt_templates"

    id: Mapped[UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid4
    )
    name: Mapped[str] = mapped_column(
        String(255), unique=True, nullable=False, index=True
    )
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow
    )

    versions: Mapped[List["PromptVersion"]] = relationship(
        back_populates="template", cascade="all, delete-orphan"
    )


class PromptVersion(Base):
    """Specific revision histories of Prompt Templates."""

    __tablename__ = "prompt_versions"

    id: Mapped[UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid4
    )
    template_id: Mapped[UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("prompt_templates.id", ondelete="CASCADE"),
        nullable=False,
    )
    version: Mapped[str] = mapped_column(String(50), nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=False)
    approved_status: Mapped[str] = mapped_column(
        String(50), default="pending"
    )  # 'draft', 'pending', 'approved', 'rejected', 'deprecated'
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow
    )

    template: Mapped["PromptTemplate"] = relationship(back_populates="versions")
    executions: Mapped[List["AIExecution"]] = relationship(
        back_populates="prompt_version"
    )
    tests: Mapped[List["PromptTest"]] = relationship(
        back_populates="prompt_version", cascade="all, delete-orphan"
    )
    approvals: Mapped[List["AIApproval"]] = relationship(
        back_populates="prompt_version", cascade="all, delete-orphan"
    )


class AIExecution(Base):
    """Individual execution records capturing prompt, response, latency, costs and entity scopes."""

    __tablename__ = "ai_executions"

    id: Mapped[UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid4
    )
    model_version_id: Mapped[Optional[UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("model_versions.id", ondelete="SET NULL"),
        nullable=True,
    )
    prompt_version_id: Mapped[Optional[UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("prompt_versions.id", ondelete="SET NULL"),
        nullable=True,
    )
    customer_id: Mapped[Optional[UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("customers.id", ondelete="SET NULL"),
        nullable=True,
    )
    case_id: Mapped[Optional[UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("cases.id", ondelete="SET NULL"), nullable=True
    )
    investigation_id: Mapped[Optional[UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("investigations.id", ondelete="SET NULL"),
        nullable=True,
    )
    sar_id: Mapped[Optional[UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("sars.id", ondelete="SET NULL"), nullable=True
    )
    risk_score_id: Mapped[Optional[UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("risk_scores.id", ondelete="SET NULL"),
        nullable=True,
    )
    monitoring_job_id: Mapped[Optional[UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("monitoring_jobs.id", ondelete="SET NULL"),
        nullable=True,
    )
    report_id: Mapped[Optional[UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("reports.id", ondelete="SET NULL"), nullable=True
    )
    audit_log_id: Mapped[Optional[UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("audit_logs.id", ondelete="SET NULL"),
        nullable=True,
    )

    prompt_content: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    response_content: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    cost: Mapped[float] = mapped_column(Numeric(10, 6), default=0.0)
    latency_ms: Mapped[int] = mapped_column(Integer, default=0)
    tokens_used: Mapped[int] = mapped_column(Integer, default=0)
    input_tokens: Mapped[int] = mapped_column(Integer, default=0)
    output_tokens: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    model_version: Mapped[Optional["ModelVersion"]] = relationship(
        back_populates="executions"
    )
    prompt_version: Mapped[Optional["PromptVersion"]] = relationship(
        back_populates="executions"
    )
    feedbacks: Mapped[List["AIFeedback"]] = relationship(
        back_populates="execution", cascade="all, delete-orphan"
    )
    explanation: Mapped[Optional["AIExplanation"]] = relationship(
        back_populates="execution", uselist=False, cascade="all, delete-orphan"
    )


class AIFeedback(Base):
    """Captures human in the loop reviews and decisions overrides."""

    __tablename__ = "ai_feedbacks"

    id: Mapped[UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid4
    )
    execution_id: Mapped[UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("ai_executions.id", ondelete="CASCADE"),
        nullable=False,
    )
    user_id: Mapped[Optional[UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    rating: Mapped[int] = mapped_column(Integer, default=0)  # 1–5
    is_correct: Mapped[bool] = mapped_column(Boolean, default=True)
    is_helpful: Mapped[bool] = mapped_column(Boolean, default=True)
    comments: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    decision_override: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    escalation_reason: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    execution: Mapped["AIExecution"] = relationship(back_populates="feedbacks")


class AIExplanation(Base):
    """Structured decision explainability report mappings."""

    __tablename__ = "ai_explanations"

    id: Mapped[UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid4
    )
    execution_id: Mapped[UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("ai_executions.id", ondelete="CASCADE"),
        nullable=False,
    )
    decision_summary: Mapped[str] = mapped_column(Text, nullable=False)
    reasoning_tree: Mapped[dict] = mapped_column(JSON, default=dict)
    confidence: Mapped[float] = mapped_column(Numeric(5, 2), default=0.0)
    supporting_evidence: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    matched_rules: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    matched_entities: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    missing_evidence: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    recommended_actions: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    execution: Mapped["AIExecution"] = relationship(back_populates="explanation")


class ModelEvaluation(Base):
    """Performance evaluation history metrics."""

    __tablename__ = "model_evaluations"

    id: Mapped[UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid4
    )
    model_version_id: Mapped[UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("model_versions.id", ondelete="CASCADE"),
        nullable=False,
    )
    evaluator_name: Mapped[str] = mapped_column(String(100), nullable=False)
    metrics_json: Mapped[dict] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    model_version: Mapped["ModelVersion"] = relationship(back_populates="evaluations")


class PromptTest(Base):
    """Pre-approval test run mappings."""

    __tablename__ = "prompt_tests"

    id: Mapped[UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid4
    )
    prompt_version_id: Mapped[UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("prompt_versions.id", ondelete="CASCADE"),
        nullable=False,
    )
    test_input: Mapped[str] = mapped_column(Text, nullable=False)
    expected_output: Mapped[str] = mapped_column(Text, nullable=False)
    actual_output: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    is_passed: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    prompt_version: Mapped["PromptVersion"] = relationship(back_populates="tests")


class AIPolicy(Base):
    """Compliance guidelines and safety policy rules."""

    __tablename__ = "ai_policies"

    id: Mapped[UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid4
    )
    name: Mapped[str] = mapped_column(
        String(255), unique=True, nullable=False, index=True
    )
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    rules_json: Mapped[dict] = mapped_column(JSON, default=dict)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class AIApproval(Base):
    """Audit logging workflow tracking reviews decisions."""

    __tablename__ = "ai_approvals"

    id: Mapped[UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid4
    )
    prompt_version_id: Mapped[UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("prompt_versions.id", ondelete="CASCADE"),
        nullable=False,
    )
    reviewer_id: Mapped[Optional[UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    status: Mapped[str] = mapped_column(
        String(50), nullable=False
    )  # approved, rejected
    comments: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    prompt_version: Mapped["PromptVersion"] = relationship(back_populates="approvals")


class AIUsageStatistics(Base):
    """Aggregated token consumption logs and cost trends."""

    __tablename__ = "ai_usage_statistics"

    id: Mapped[UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid4
    )
    date: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    model_name: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    total_calls: Mapped[int] = mapped_column(Integer, default=0)
    total_tokens: Mapped[int] = mapped_column(Integer, default=0)
    input_tokens: Mapped[int] = mapped_column(Integer, default=0)
    output_tokens: Mapped[int] = mapped_column(Integer, default=0)
    total_cost: Mapped[float] = mapped_column(Numeric(10, 6), default=0.0)
    average_latency_ms: Mapped[float] = mapped_column(Numeric(10, 2), default=0.0)
