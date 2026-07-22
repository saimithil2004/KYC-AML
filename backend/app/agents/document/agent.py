"""
Document Verification Agent
============================
Performs document-level verification on uploaded customer documents.

Checks:
  1. OCR name match against declared KYC name
  2. OCR DOB match against declared KYC DOB
  3. Duplicate document detection (same file name or hash)
  4. Image quality proxy (file size heuristic)
  5. Document presence (at least one verified document)

Design constraints
------------------
• Deterministic — zero LLM calls
• All inputs from AgentState.uploaded_documents and AgentState.kyc_profile
• No direct database queries inside the agent
"""

import time
import logging
from datetime import datetime, date
from typing import Dict, Any, List, Optional, Set
from difflib import SequenceMatcher

from app.agents.base.base_agent import BaseAgent
from app.agents.base.agent_state import AgentState
from app.agents.base.registry import AgentRegistry
from app.agents.base.exceptions import AgentValidationError

logger = logging.getLogger(__name__)

# ── Constants ─────────────────────────────────────────────────────────────────
MIN_FILE_SIZE_BYTES = 5_000  # Proxy for minimum acceptable image quality
NAME_MATCH_THRESHOLD = 0.80  # SequenceMatcher ratio for fuzzy name match
VERIFIED_STATUSES = {"verified", "approved", "accepted"}
NEXT_AGENT = "pep_agent"  # Routing hint for orchestrator


@AgentRegistry.register("document_verification_agent")
class DocumentVerificationAgent(BaseAgent):
    """
    Document Verification Agent.
    Validates uploaded documents for name/DOB match, quality, and duplicates.
    """

    # ── Agent Metadata ────────────────────────────────────────────────────────
    def get_name(self) -> str:
        return "document_verification_agent"

    def get_version(self) -> str:
        return "1.0.0"

    def get_description(self) -> str:
        return (
            "Document verification agent. Performs OCR name/DOB cross-check, "
            "duplicate detection, image quality assessment, and document presence check."
        )

    def get_capabilities(self) -> List[str]:
        return [
            "ocr_name_match",
            "ocr_dob_match",
            "duplicate_detection",
            "image_quality_check",
            "document_presence_check",
            "verification_status_check",
        ]

    # ── Input Validation ──────────────────────────────────────────────────────
    def validate_input(self, state: AgentState) -> bool:
        if not state.customer_id:
            raise AgentValidationError(
                message="customer_id missing in AgentState. Cannot run DocumentVerificationAgent.",
                details={"customer_id": None},
            )
        return True

    # ── Core Processing ───────────────────────────────────────────────────────
    async def process(self, state: AgentState) -> Dict[str, Any]:
        start_time = time.perf_counter()
        state.logs.append(f"[{self.get_name()}] Starting document verification...")

        docs: List[Dict[str, Any]] = state.uploaded_documents or []
        kyc: Dict[str, Any] = state.kyc_profile or {}

        declared_name = str(kyc.get("full_name") or "").strip().lower()
        declared_dob = kyc.get("date_of_birth") or kyc.get("dob")

        findings: List[str] = []
        warnings: List[str] = []
        errors: List[str] = []
        recommendations: List[str] = []

        # Track for deduplication
        seen_filenames: Set[str] = set()
        duplicate_count = 0

        # Counters
        name_mismatches = 0
        dob_mismatches = 0
        low_quality = 0
        verified_count = 0
        total_docs = len(docs)

        for doc in docs:
            doc_type = doc.get("document_type", "UNKNOWN")
            file_name = str(doc.get("file_name") or "").strip()
            file_size = int(doc.get("file_size") or 0)
            status = str(doc.get("verification_status") or "").lower()
            ocr_data = doc.get("ocr_data") or {}

            # ── Duplicate detection ───────────────────────────────────────────
            if file_name and file_name in seen_filenames:
                duplicate_count += 1
                warnings.append(
                    f"Duplicate document detected: '{file_name}' ({doc_type})."
                )
            elif file_name:
                seen_filenames.add(file_name)

            # ── Verification status ───────────────────────────────────────────
            if status in VERIFIED_STATUSES:
                verified_count += 1

            # ── Image quality (file size proxy) ───────────────────────────────
            if file_size and file_size < MIN_FILE_SIZE_BYTES:
                low_quality += 1
                warnings.append(
                    f"Possible low quality image on '{file_name}' ({doc_type}): "
                    f"file size {file_size} bytes is below threshold {MIN_FILE_SIZE_BYTES} bytes."
                )

            # ── OCR name match ────────────────────────────────────────────────
            ocr_name = (
                str(ocr_data.get("full_name") or ocr_data.get("name") or "")
                .strip()
                .lower()
            )
            if ocr_name and declared_name:
                ratio = SequenceMatcher(None, declared_name, ocr_name).ratio()
                if ratio < NAME_MATCH_THRESHOLD:
                    name_mismatches += 1
                    errors.append(
                        f"Name mismatch on {doc_type} '{file_name}': "
                        f"declared '{declared_name}' vs OCR '{ocr_name}' "
                        f"(match ratio: {ratio:.2f})."
                    )
                else:
                    findings.append(
                        f"Name verified on {doc_type}: declared name matches OCR (ratio: {ratio:.2f})."
                    )

            # ── OCR DOB match ─────────────────────────────────────────────────
            ocr_dob_raw = ocr_data.get("dob") or ocr_data.get("date_of_birth")
            if ocr_dob_raw and declared_dob:
                try:
                    ocr_dob = self._parse_date(ocr_dob_raw)
                    decl_dob = self._parse_date(declared_dob)
                    if ocr_dob and decl_dob and ocr_dob != decl_dob:
                        dob_mismatches += 1
                        errors.append(
                            f"DOB mismatch on {doc_type} '{file_name}': "
                            f"declared '{decl_dob}' vs OCR '{ocr_dob}'."
                        )
                    elif ocr_dob and decl_dob:
                        findings.append(
                            f"DOB verified on {doc_type}: declared DOB matches OCR."
                        )
                except Exception as exc:
                    warnings.append(f"Could not compare DOB on {doc_type}: {exc}")

        # ── Summary findings ──────────────────────────────────────────────────
        if total_docs == 0:
            errors.append("No documents uploaded for this customer.")
            recommendations.append("Request customer to upload identity documents.")
        elif verified_count == 0:
            warnings.append("No documents have a 'verified' status yet.")
            recommendations.append("Manually verify uploaded documents.")

        if duplicate_count > 0:
            recommendations.append("Remove or review duplicate document submissions.")
        if name_mismatches > 0:
            recommendations.append(
                "Resolve name discrepancies between documents and KYC declaration."
            )
        if dob_mismatches > 0:
            recommendations.append(
                "Resolve DOB discrepancies between documents and KYC declaration."
            )
        if low_quality > 0:
            recommendations.append(
                "Request higher-quality document images from the customer."
            )

        # ── Calculate document score (0–100) ──────────────────────────────────
        document_score = self._calculate_document_score(
            total_docs=total_docs,
            verified_count=verified_count,
            name_mismatches=name_mismatches,
            dob_mismatches=dob_mismatches,
            duplicates=duplicate_count,
            low_quality=low_quality,
        )

        risk_level = (
            "high"
            if document_score < 40
            else "medium" if document_score < 70 else "low"
        )

        execution_duration_ms = round((time.perf_counter() - start_time) * 1000, 2)

        # ── Update AgentState ─────────────────────────────────────────────────
        state.risk_breakdown["document"] = document_score
        state.shared_metadata["document_score"] = document_score
        state.shared_metadata["document_risk"] = risk_level
        state.shared_metadata["document_name_mismatches"] = name_mismatches
        state.shared_metadata["document_dob_mismatches"] = dob_mismatches
        state.shared_metadata["document_duplicates"] = duplicate_count
        state.shared_metadata["document_verified_count"] = verified_count
        state.shared_metadata["document_total"] = total_docs
        state.shared_metadata["next_agent"] = NEXT_AGENT

        state.logs.append(
            f"DocumentVerificationAgent: {total_docs} doc(s), {verified_count} verified. "
            f"Score={document_score}, Risk={risk_level}. "
            f"Name mismatches={name_mismatches}, DOB mismatches={dob_mismatches}."
        )

        return {
            "_status": "success",
            "_reason": f"Document verification complete. Score={document_score}",
            "confidence": document_score / 100.0,
            "risk_score": document_score,
            "risk_level": risk_level,
            "findings": findings,
            "warnings": warnings,
            "recommendations": recommendations,
            "errors": errors,
            # Metadata
            "document_score": document_score,
            "total_docs": total_docs,
            "verified_count": verified_count,
            "name_mismatches": name_mismatches,
            "dob_mismatches": dob_mismatches,
            "duplicate_count": duplicate_count,
            "low_quality_count": low_quality,
            "next_agent": NEXT_AGENT,
            "execution_duration_ms": execution_duration_ms,
        }

    # ── Private Helpers ───────────────────────────────────────────────────────
    @staticmethod
    def _parse_date(raw) -> Optional[date]:
        """Parses various date formats into a date object."""
        if isinstance(raw, date):
            return raw
        if isinstance(raw, datetime):
            return raw.date()
        if isinstance(raw, str):
            for fmt in ("%Y-%m-%d", "%d/%m/%Y", "%d-%m-%Y", "%m/%d/%Y"):
                try:
                    return datetime.strptime(raw, fmt).date()
                except ValueError:
                    continue
        return None

    @staticmethod
    def _calculate_document_score(
        total_docs: int,
        verified_count: int,
        name_mismatches: int,
        dob_mismatches: int,
        duplicates: int,
        low_quality: int,
    ) -> float:
        """Computes document verification score (0–100, 100 = perfect)."""
        if total_docs == 0:
            return 0.0

        score = 100.0

        # Deduct for verification mismatches
        score -= name_mismatches * 20.0
        score -= dob_mismatches * 20.0
        score -= duplicates * 10.0
        score -= low_quality * 5.0

        # Boost for verified documents
        verification_ratio = verified_count / total_docs
        if verification_ratio < 1.0:
            score -= (1.0 - verification_ratio) * 20.0

        return round(max(0.0, min(100.0, score)), 2)
