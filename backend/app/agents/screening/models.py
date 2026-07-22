"""
Shared Screening — Models
==========================

ScreeningSubject
    The canonical individual-person record used across the AML pipeline.
    Used by PEP Agent, Sanctions Agent, and Country Risk Agent.

CompanyScreeningSubject
    The canonical company entity record.
    Used by Sanctions Agent for company-level screening.
    Country Risk Agent may also use it for country-of-incorporation risk.

Both are defined here so every future screening agent imports from a single
source of truth rather than duplicating model definitions.
"""

from typing import Any, Dict, List, Optional
from pydantic import BaseModel


# ─────────────────────────────────────────────────────────────────────────────
# ScreeningSubject — individual persons
# ─────────────────────────────────────────────────────────────────────────────
class ScreeningSubject(BaseModel):
    """
    Normalised individual-person record extracted from AgentState.

    Produced by ``PepValidator.build_subjects(state)`` and consumed by:
      • PEP Agent          — PEP dataset matching
      • Sanctions Agent    — individual sanctions screening
      • Country Risk Agent — nationality / country risk scoring
    """

    subject_id: str  # Unique within a case run
    role: str  # ROLE_* constant from screening.constants
    full_name: str
    dob: Optional[str] = None  # ISO-8601, e.g. "1970-01-15"
    nationality: Optional[str] = None
    country: Optional[str] = None
    company_name: Optional[str] = None  # For directors/UBOs
    passport_number: Optional[str] = None  # For enhanced sanctions matching

    def display(self) -> str:
        return (
            f"{self.role}:{self.full_name} "
            f"(DOB:{self.dob}, NAT:{self.nationality}, PP:{self.passport_number})"
        )


# ─────────────────────────────────────────────────────────────────────────────
# CompanyScreeningSubject — company entities
# ─────────────────────────────────────────────────────────────────────────────
class CompanyScreeningSubject(BaseModel):
    """
    Normalised company entity extracted from AgentState.

    Used by the Sanctions Agent for company-level sanctions screening.
    Future Country Risk Agent can use it for country-of-incorporation risk.
    """

    subject_id: str
    role: str  # ROLE_COMPANY
    company_name: str
    registration_number: Optional[str] = None
    country: Optional[str] = None
    business_address: Optional[str] = None

    def display(self) -> str:
        return (
            f"COMPANY:{self.company_name} "
            f"(REG:{self.registration_number}, COUNTRY:{self.country})"
        )
