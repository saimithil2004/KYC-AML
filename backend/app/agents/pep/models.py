"""
PEP Agent — Pydantic Models
============================

ScreeningSubject
    Imported from app.agents.screening.models and re-exported for backward
    compatibility.  The canonical definition lives in the shared screening
    package so all screening agents share a single model.

PepRecord
    A single entry returned by a PEP data provider.

PepMatchResult
    The result of running the matching engine against one subject.

PepAuditTrail
    Immutable per-run audit record stored in AgentResult.metadata
    and AgentState.shared_metadata.
"""

from datetime import datetime
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field

# Re-export from shared screening package for backward compatibility.
# All imports that previously pointed here continue to work unchanged.
from app.agents.screening.models import ScreeningSubject  # noqa: F401

__all__ = ["ScreeningSubject", "PepRecord", "PepMatchResult", "PepAuditTrail"]

# ─────────────────────────────────────────────────────────────────────────────
# PepRecord — returned by any PEP data provider
# ─────────────────────────────────────────────────────────────────────────────
class PepRecord(BaseModel):
    """
    A single PEP entry as returned by a provider (mock or real).

    Future providers (OpenSanctions, World-Check, Dow Jones) map their
    API responses onto this model inside their own provider implementation.
    The PEP Agent and matching engine only ever see PepRecord — they are
    completely decoupled from the provider wire format.
    """
    record_id:    str
    full_name:    str
    dob:          Optional[str]  = None
    nationality:  Optional[str]  = None
    country:      Optional[str]  = None
    category:     str                    # PEP_CATEGORY_* constant
    position:     Optional[str]  = None  # e.g. "Minister of Finance"
    is_current:   bool           = True  # Current vs Former office holder
    source:       str            = "unknown"
    last_updated: Optional[str]  = None


# ─────────────────────────────────────────────────────────────────────────────
# PepMatchResult — outcome for a single subject
# ─────────────────────────────────────────────────────────────────────────────
class PepMatchResult(BaseModel):
    """
    The result of running the multi-signal matching engine against
    one ScreeningSubject.  One PepMatchResult per subject screened.
    """
    subject_id:       str
    subject_name:     str
    subject_role:     str
    match_confidence: str            # MATCH_* constant
    match_score:      float          # 0–100
    matched_record:   Optional[PepRecord] = None
    pep_category:     Optional[str]  = None
    rules_triggered:  List[str]      = Field(default_factory=list)
    reason:           str            = "No match found"
    requires_edd:     bool           = False
    requires_manual_review: bool     = False


# ─────────────────────────────────────────────────────────────────────────────
# PepAuditTrail — stored in AgentResult.metadata and AgentState
# ─────────────────────────────────────────────────────────────────────────────
class PepAuditTrail(BaseModel):
    """Immutable per-run audit record produced by the PEP Agent."""
    provider_used:        str
    subjects_screened:    int          = 0
    matches_found:        int          = 0
    confirmed_peps:       int          = 0
    possible_matches:     int          = 0
    rules_triggered:      List[str]    = Field(default_factory=list)
    warnings:             List[str]    = Field(default_factory=list)
    recommendations:      List[str]    = Field(default_factory=list)
    execution_duration_ms: float       = 0.0
    validation_timestamp: str          = Field(
        default_factory=lambda: datetime.utcnow().isoformat()
    )
