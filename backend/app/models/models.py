from datetime import date, datetime
from typing import List, Optional
from sqlalchemy import String, Text, Boolean, Integer, Numeric, Date, DateTime, ForeignKey, UUID, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.dialects.postgresql import JSONB
from uuid import uuid4
from app.core.database import Base

# 1. USERS TABLE
class User(Base):
    __tablename__ = "users"
    
    id: Mapped[UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    email: Mapped[str] = mapped_column(String(255), unique=True, nullable=False, index=True)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    role: Mapped[str] = mapped_column(String(50), nullable=False)  # 'customer', 'compliance_officer', 'admin'
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    customer: Mapped[Optional["Customer"]] = relationship(back_populates="user", uselist=False)
    audit_logs: Mapped[List["AuditLog"]] = relationship(back_populates="user")
    regulations: Mapped[List["Regulation"]] = relationship(back_populates="uploaded_by")

# 2. CUSTOMERS TABLE
class Customer(Base):
    __tablename__ = "customers"
    
    id: Mapped[UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    user_id: Mapped[UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=True)
    customer_type: Mapped[str] = mapped_column(String(20), nullable=False)  # 'individual', 'corporate'
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
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    user: Mapped[Optional["User"]] = relationship(back_populates="customer")
    kyc_profile: Mapped[Optional["KYCProfile"]] = relationship(back_populates="customer", uselist=False)
    companies: Mapped[List["Company"]] = relationship(back_populates="customer")
    documents: Mapped[List["Document"]] = relationship(back_populates="customer")
    accounts: Mapped[List["Account"]] = relationship(back_populates="customer")
    risk_scores: Mapped[List["RiskScore"]] = relationship(back_populates="customer")
    monitoring_schedules: Mapped[List["MonitoringSchedule"]] = relationship(back_populates="customer")
    alerts: Mapped[List["Alert"]] = relationship(back_populates="customer")
    cases: Mapped[List["Case"]] = relationship(back_populates="customer")

# 3. COMPANIES TABLE
class Company(Base):
    __tablename__ = "companies"
    
    id: Mapped[UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    customer_id: Mapped[UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("customers.id", ondelete="CASCADE"), nullable=False)
    company_name: Mapped[str] = mapped_column(String(255), nullable=False)
    registration_number: Mapped[str] = mapped_column(String(100), unique=True, nullable=False, index=True)
    registered_address: Mapped[str] = mapped_column(Text, nullable=False)
    trading_address: Mapped[Optional[str]] = mapped_column(Text)
    country_of_incorporation: Mapped[str] = mapped_column(String(100), nullable=False)
    incorporation_date: Mapped[Optional[date]] = mapped_column(Date)
    sic_code: Mapped[Optional[str]] = mapped_column(String(20))
    status: Mapped[str] = mapped_column(String(50), default="active")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    customer: Mapped["Customer"] = relationship(back_populates="companies")
    directors: Mapped[List["Director"]] = relationship(back_populates="company")
    ubos: Mapped[List["UBO"]] = relationship(back_populates="company")

# 4. DIRECTORS TABLE
class Director(Base):
    __tablename__ = "directors"
    
    id: Mapped[UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    company_id: Mapped[UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("companies.id", ondelete="CASCADE"), nullable=False)
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
    
    id: Mapped[UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    company_id: Mapped[UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("companies.id", ondelete="CASCADE"), nullable=False)
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
    __table_args__ = (UniqueConstraint("customer_id", name="uq_kyc_profiles_customer_id"),)
    
    id: Mapped[UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    customer_id: Mapped[UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("customers.id", ondelete="CASCADE"), nullable=False, index=True)
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
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    customer: Mapped["Customer"] = relationship(back_populates="kyc_profile")

# 7. DOCUMENTS TABLE
class Document(Base):
    __tablename__ = "documents"
    
    id: Mapped[UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    customer_id: Mapped[UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("customers.id", ondelete="CASCADE"), nullable=False, index=True)
    document_type: Mapped[str] = mapped_column(String(100), nullable=False)
    file_name: Mapped[str] = mapped_column(String(255), nullable=False)
    file_path: Mapped[str] = mapped_column(Text, nullable=False)
    content_type: Mapped[Optional[str]] = mapped_column(String(100))
    file_size: Mapped[Optional[int]] = mapped_column(Integer)
    ocr_data: Mapped[Optional[dict]] = mapped_column(JSONB)
    verification_status: Mapped[str] = mapped_column(String(50), default="uploaded")
    verification_metadata: Mapped[Optional[dict]] = mapped_column(JSONB)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    customer: Mapped["Customer"] = relationship(back_populates="documents")

# 8. ACCOUNTS TABLE
class Account(Base):
    __tablename__ = "accounts"
    
    id: Mapped[UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    customer_id: Mapped[UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("customers.id", ondelete="CASCADE"), nullable=False)
    account_number: Mapped[str] = mapped_column(String(50), unique=True, nullable=False, index=True)
    sort_code: Mapped[str] = mapped_column(String(20), nullable=False)
    currency: Mapped[str] = mapped_column(String(10), default="GBP")
    balance: Mapped[float] = mapped_column(Numeric(15, 4), default=0.0000)
    status: Mapped[str] = mapped_column(String(50), default="active")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    customer: Mapped["Customer"] = relationship(back_populates="accounts")
    transactions: Mapped[List["Transaction"]] = relationship(back_populates="sender_account")

# 9. TRANSACTIONS TABLE
class Transaction(Base):
    __tablename__ = "transactions"
    
    id: Mapped[UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    sender_account_id: Mapped[UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("accounts.id", ondelete="CASCADE"), nullable=False)
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
    
    id: Mapped[UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    customer_id: Mapped[UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("customers.id", ondelete="CASCADE"), nullable=False)
    transaction_id: Mapped[Optional[UUID]] = mapped_column(UUID(as_uuid=True), ForeignKey("transactions.id", ondelete="SET NULL"))
    alert_type: Mapped[str] = mapped_column(String(100), nullable=False)
    risk_score: Mapped[float] = mapped_column(Numeric(5, 2), nullable=False)
    status: Mapped[str] = mapped_column(String(50), default="open")
    alert_metadata: Mapped[Optional[dict]] = mapped_column(JSONB)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    customer: Mapped["Customer"] = relationship(back_populates="alerts")
    transaction: Mapped[Optional["Transaction"]] = relationship(back_populates="alerts")

# 11. CASES TABLE
class Case(Base):
    __tablename__ = "cases"
    
    id: Mapped[UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    customer_id: Mapped[UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("customers.id", ondelete="CASCADE"), nullable=False)
    assigned_to: Mapped[Optional[UUID]] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"))
    priority: Mapped[str] = mapped_column(String(20), default="medium")
    status: Mapped[str] = mapped_column(String(50), default="new")
    investigation_notes: Mapped[Optional[str]] = mapped_column(Text)
    sar_filed: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    customer: Mapped["Customer"] = relationship(back_populates="cases")
    agent_logs: Mapped[List["AgentLog"]] = relationship(back_populates="case")

# 12. RISK_SCORES TABLE
class RiskScore(Base):
    __tablename__ = "risk_scores"
    
    id: Mapped[UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    customer_id: Mapped[UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("customers.id", ondelete="CASCADE"), nullable=False)
    overall_score: Mapped[float] = mapped_column(Numeric(5, 2), nullable=False)
    risk_tier: Mapped[str] = mapped_column(String(20), nullable=False)
    breakdown: Mapped[dict] = mapped_column(JSONB, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    # Relationships
    customer: Mapped["Customer"] = relationship(back_populates="risk_scores")

# 13. MONITORING_SCHEDULE TABLE
class MonitoringSchedule(Base):
    __tablename__ = "monitoring_schedule"
    
    id: Mapped[UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    customer_id: Mapped[UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("customers.id", ondelete="CASCADE"), nullable=False)
    next_review_date: Mapped[date] = mapped_column(Date, nullable=False)
    review_frequency_months: Mapped[int] = mapped_column(Integer, nullable=False)
    last_review_date: Mapped[Optional[date]] = mapped_column(Date)
    status: Mapped[str] = mapped_column(String(50), default="scheduled")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    customer: Mapped["Customer"] = relationship(back_populates="monitoring_schedules")

# 14. AUDIT_LOGS TABLE
class AuditLog(Base):
    __tablename__ = "audit_logs"
    
    id: Mapped[UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    user_id: Mapped[Optional[UUID]] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"))
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
    
    id: Mapped[UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    case_id: Mapped[UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("cases.id", ondelete="CASCADE"), nullable=False)
    agent_name: Mapped[str] = mapped_column(String(100), nullable=False)
    step_name: Mapped[str] = mapped_column(String(100), nullable=False)
    input_state: Mapped[Optional[dict]] = mapped_column(JSONB)
    output_state: Mapped[Optional[dict]] = mapped_column(JSONB)
    execution_time_ms: Mapped[Optional[int]] = mapped_column(Integer)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    # Relationships
    case: Mapped["Case"] = relationship(back_populates="agent_logs")

# 16. REGULATIONS TABLE
class Regulation(Base):
    __tablename__ = "regulations"
    
    id: Mapped[UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    authority: Mapped[str] = mapped_column(String(100), nullable=False)
    upload_path: Mapped[str] = mapped_column(Text, nullable=False)
    uploaded_by_id: Mapped[Optional[UUID]] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"))
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    # Relationships
    uploaded_by: Mapped[Optional["User"]] = relationship(back_populates="regulations")
    policy_rules: Mapped[List["PolicyRule"]] = relationship(back_populates="regulation")

# 17. POLICY_RULES TABLE
class PolicyRule(Base):
    __tablename__ = "policy_rules"
    
    id: Mapped[UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    regulation_id: Mapped[UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("regulations.id", ondelete="CASCADE"), nullable=False)
    rule_name: Mapped[str] = mapped_column(String(255), nullable=False)
    rule_type: Mapped[str] = mapped_column(String(100), nullable=False)  # 'threshold', 'block', 'edd'
    conditions: Mapped[dict] = mapped_column(JSONB, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    # Relationships
    regulation: Mapped["Regulation"] = relationship(back_populates="policy_rules")
