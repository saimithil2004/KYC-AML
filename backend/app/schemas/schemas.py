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

class UserResponse(BaseModel):
    id: UUID
    email: EmailStr
    role: str
    is_active: bool
    created_at: datetime

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
    address: str
    occupation: str
    source_of_funds: str
    source_of_wealth: str
    risk_category: Optional[str] = "low"

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
    address: Optional[str] = None
    occupation: Optional[str] = None
    source_of_funds: Optional[str] = None
    source_of_wealth: Optional[str] = None
    risk_category: Optional[str] = None

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
    address: Optional[str] = None
    occupation: str
    source_of_funds: str
    source_of_wealth: str
    risk_category: str
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
    amount: float
    currency: str = "GBP"
    transaction_type: str
    reference: Optional[str] = None

class TransactionResponse(BaseModel):
    id: UUID
    sender_account_id: UUID
    receiver_account_number: str
    amount: float
    status: str
    created_at: datetime

    class Config:
        from_attributes = True
