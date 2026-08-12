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


def normalise_ocr_data(raw: Optional[Dict[str, Any]]) -> Optional["DocumentOcrOutput"]:
    """
    Convert the OCR engine's raw output into a ``DocumentOcrOutput`` instance.

    OCR engines (Gemini, DocTR, Tesseract) return every field wrapped in a
    ``{"value": ..., "confidence": ...}`` envelope, e.g.::

        {"full_name": {"value": "John Doe", "confidence": 0.99}}

    ``DocumentOcrOutput`` expects plain scalar values, e.g.::

        {"full_name": "John Doe"}

    This function:

    1. Unwraps the ``{value, confidence}`` envelope for every field.
    2. Coerces list fields (``directors``, ``shareholders``, ``ubo_information``)
       so they are always a ``list``, never ``""`` / ``None`` / ``"-"`` / ``"—"``.
       This handles the case where the frontend sends a plain ``<input>`` string
       for those fields after the user edits OCR data on the confirmation screen.
    3. Strips unknown / internal (``_``-prefixed) keys to avoid Pydantic errors.

    Fields that are already plain scalars (e.g. after user confirmation) pass
    through unchanged.  ``None`` / empty raw data returns ``None``.
    """
    if not raw:
        return None

    # Sentinel values that represent "no data" for list fields
    _EMPTY_SENTINELS = {"", "-", "—", "–", "none", "null", "n/a"}

    # Identify which DocumentOcrOutput fields are typed as List[*]
    import typing
    _list_fields: set[str] = set()
    for field_name, field_info in DocumentOcrOutput.model_fields.items():
        annotation = field_info.annotation
        origin = getattr(annotation, "__origin__", None)
        # Handles Optional[List[str]]  →  origin is Union, args include List[str]
        if origin is typing.Union:
            for arg in annotation.__args__:
                if getattr(arg, "__origin__", None) is list:
                    _list_fields.add(field_name)
                    break
        elif origin is list:
            _list_fields.add(field_name)

    known_fields = set(DocumentOcrOutput.model_fields.keys())
    flat: Dict[str, Any] = {}

    for key, val in raw.items():
        if key.startswith("_"):
            # Skip internal metadata keys such as _ocr_engine_used
            continue
        if isinstance(val, dict) and "value" in val:
            # Unwrap {"value": X, "confidence": Y}  →  X
            flat[key] = val["value"]
        else:
            flat[key] = val

    # ── List-field coercion ────────────────────────────────────────────────────
    # After unwrapping, list fields may hold ""/None/"-" (from frontend inputs)
    # or a plain scalar.  Pydantic requires an actual list.
    for lf in _list_fields:
        if lf not in flat:
            continue
        v = flat[lf]
        if v is None:
            flat[lf] = []
        elif isinstance(v, list):
            pass  # already correct
        elif isinstance(v, str):
            if v.strip().lower() in _EMPTY_SENTINELS:
                flat[lf] = []
            else:
                # e.g. "John Doe, Jane Smith" → wrap as single item;
                # splitting by comma is intentionally NOT done here because
                # the OCR engine already returns proper lists when it can.
                flat[lf] = [v]
        else:
            # Any other scalar (int, bool …) → wrap in a list
            flat[lf] = [str(v)]

    # Only pass fields that DocumentOcrOutput actually declares to avoid
    # Pydantic "unexpected field" errors for engine-specific extras.
    return DocumentOcrOutput(**{k: v for k, v in flat.items() if k in known_fields})



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
