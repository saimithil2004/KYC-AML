"""
Sanctions Agent — Models
=========================

SanctionRecord
    A single entry returned by a sanctions provider (contains individual or company info).

SanctionMatchResult
    The result of matching a subject against candidate sanctions records.

SanctionsAuditTrail
    The per-run audit record produced by the Sanctions Agent.
"""

from datetime import datetime
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field

from app.agents.screening.models import ScreeningSubject, CompanyScreeningSubject


# ─────────────────────────────────────────────────────────────────────────────
# SanctionRecord — data from sanctions lists
# ─────────────────────────────────────────────────────────────────────────────
class SanctionRecord(BaseModel):
    """
    A single record representing a sanctioned individual or company.
    Supports all major international lists (OFAC, UK, UN, EU, OpenSanctions, Internal).
    """
    record_id:           str
    entity_type:         str              # ENTITY_INDIVIDUAL / ENTITY_COMPANY
    full_name:           str
    aliases:             List[str]        = Field(default_factory=list)
    dob:                 Optional[str]    = None
    nationality:         Optional[str]    = None
    passport_number:     Optional[str]    = None
    company_name:        Optional[str]    = None
    registration_number: Optional[str]    = None
    country:             Optional[str]    = None
    business_address:    Optional[str]    = None
    sanction_category:   str              # SANCTION_CATEGORY_* constant
    sanction_list:       str              # LIST_* constant
    is_active:           bool             = True
    source:              str              = "unknown"
    last_updated:        Optional[str]    = None


# ─────────────────────────────────────────────────────────────────────────────
# SanctionMatchResult — match outcome
# ─────────────────────────────────────────────────────────────────────────────
class SanctionMatchResult(BaseModel):
    """
    Result of evaluating a ScreeningSubject or CompanyScreeningSubject
    against sanctions candidates.
    """
    subject_id:          str
    subject_name:        str
    subject_role:        str              # ROLE_* constant
    entity_type:         str              # ENTITY_INDIVIDUAL / ENTITY_COMPANY
    match_confidence:    str              # MATCH_* constant
    match_score:         float            # 0–100
    matched_record:      Optional[SanctionRecord] = None
    sanction_category:   Optional[str]    = None
    matched_list:        Optional[str]    = None
    matched_fields:      List[str]        = Field(default_factory=list)
    rules_triggered:     List[str]        = Field(default_factory=list)
    reason:              str              = "No match found"
    requires_escalation: bool             = False


# ─────────────────────────────────────────────────────────────────────────────
# SanctionsAuditTrail — per-run audit details
# ─────────────────────────────────────────────────────────────────────────────
class SanctionsAuditTrail(BaseModel):
    """Immutable audit trail for every sanctions screening execution."""
    provider_used:         str
    sanctions_lists_checked: List[str]    = Field(default_factory=list)
    subjects_screened:     int            = 0
    companies_screened:    int            = 0
    matches_found:         int            = 0
    matched_lists:         List[str]      = Field(default_factory=list)
    rules_triggered:       List[str]      = Field(default_factory=list)
    warnings:              List[str]      = Field(default_factory=list)
    recommendations:       List[str]      = Field(default_factory=list)
    execution_duration_ms: float          = 0.0
    validation_timestamp:  str            = Field(
        default_factory=lambda: datetime.utcnow().isoformat()
    )
