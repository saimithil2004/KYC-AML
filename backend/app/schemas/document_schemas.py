from datetime import date, datetime
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field
from uuid import UUID


class DocumentOcrOutput(BaseModel):
    full_name: Optional[str] = None
    dob: Optional[date] = None
    nationality: Optional[str] = None
    address: Optional[str] = None
    document_number: Optional[str] = None
    issue_date: Optional[date] = None
    expiry_date: Optional[date] = None
    issuing_authority: Optional[str] = None

    # Business-specific fields
    company_registration_number: Optional[str] = None
    company_name: Optional[str] = None
    directors: Optional[List[str]] = []
    shareholders: Optional[List[str]] = []
    ubo_information: Optional[List[str]] = []


class DocumentValidationDetail(BaseModel):
    is_expired: bool = False
    is_blurry: bool = False
    is_corrupted: bool = False
    wrong_file_type: bool = False
    is_duplicate: bool = False
    missing_pages: bool = False
    unsupported_document: bool = False
    errors: List[str] = []


class DocumentMatchingDetail(BaseModel):
    name_match_ratio: float = 0.0
    dob_match: bool = False
    address_match_ratio: float = 0.0
    nationality_match: bool = False
    overall_confidence_score: float = 0.0


class DocumentRiskDetail(BaseModel):
    risk_category: str = "low"  # low, medium, high
    reasons: List[str] = []


class DocumentVerificationDetailsResponse(BaseModel):
    document_id: UUID
    verification_status: str
    ocr_data: Optional[DocumentOcrOutput] = None
    validation: Optional[DocumentValidationDetail] = None
    matching: Optional[DocumentMatchingDetail] = None
    risk: Optional[DocumentRiskDetail] = None
    metadata: Dict[str, Any] = {}
    history: List[Dict[str, Any]] = []


class ReprocessResponse(BaseModel):
    document_id: UUID
    status: str
    message: str
