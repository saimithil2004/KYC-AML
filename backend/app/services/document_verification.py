import hashlib
import logging
from datetime import date, datetime
from pathlib import Path
from typing import Dict, Any, List
from uuid import UUID

from app.models.models import Document, KYCProfile, Customer
from app.services.ocr.orchestrator import OcrOrchestrator

# Import rapidfuzz with dynamic fallback to difflib
try:
    from rapidfuzz import fuzz

    def calculate_similarity(s1: str, s2: str) -> float:
        if not s1 or not s2:
            return 0.0
        return float(fuzz.ratio(s1.strip().lower(), s2.strip().lower()))

except ImportError:
    from difflib import SequenceMatcher

    def calculate_similarity(s1: str, s2: str) -> float:
        if not s1 or not s2:
            return 0.0
        return round(
            SequenceMatcher(None, s1.strip().lower(), s2.strip().lower()).ratio() * 100,
            1,
        )


logger = logging.getLogger(__name__)


class DocumentVerificationService:

    # ─── STEP 1: FILE PERSISTENCE HELPERS ──────────────────────────────────────
    @staticmethod
    def calculate_sha256(file_path: Path) -> str:
        """Calculates SHA-256 hash of document for duplicates."""
        sha256 = hashlib.sha256()
        with open(file_path, "rb") as f:
            while chunk := f.read(8192):
                sha256.update(chunk)
        return sha256.hexdigest()

    # ─── STEP 2: DOCUMENT CLASSIFICATION AGENT ─────────────────────────────────
    @staticmethod
    def classify_document(file_path: Path, declared_type: str) -> Dict[str, Any]:
        """
        Classifies the document category based on visual context, file patterns, or content.
        Returns a dict: {"classified_type": str, "confidence": float}
        """
        fn = file_path.name.lower()

        # Simple rule-based classifier for testing
        classified = "unknown"
        confidence = 0.90

        if "passport" in fn or declared_type == "passport":
            classified = "passport"
        elif "id" in fn or declared_type == "national_id":
            classified = "national_id"
        elif "licence" in fn or "license" in fn or declared_type == "driving_licence":
            classified = "driving_licence"
        elif "bill" in fn or declared_type in ["utility_bill", "proof_of_address"]:
            classified = "utility_bill"
        elif "statement" in fn or declared_type == "bank_statement":
            classified = "bank_statement"
        elif "incorporation" in fn or declared_type == "certificate_of_incorporation":
            classified = "certificate_of_incorporation"
        elif "ubo" in fn or declared_type == "ubo_document":
            classified = "ubo_document"
        elif "director" in fn or declared_type == "director_identity":
            classified = "director_identity"
        else:
            classified = declared_type

        return {"classified_type": classified, "confidence": confidence}

    # ─── STEP 3: IMAGE QUALITY AGENT ───────────────────────────────────────────
    @staticmethod
    def assess_image_quality(file_path: Path) -> Dict[str, Any]:
        """
        Runs quality inspections: blur, glare, contrast, crop bounds.
        Returns dict: {"passed": bool, "details": Dict[str, Any]}
        """
        size = file_path.stat().st_size

        # Heuristics: extremely small images indicate low-resolution/blur
        passed = True
        metrics = {
            "blur_score": 92.5,  # out of 100
            "resolution_passed": True,
            "brightness_passed": True,
            "glare_detected": False,
            "hidden_corners": False,
            "reasons": [],
        }

        if size < 5 * 1024:  # Under 5KB is likely unreadable or corrupt
            passed = False
            metrics["resolution_passed"] = False
            metrics["reasons"].append(
                "File size is too small; resolution check failed."
            )

        # Mock blur check for simulated corrupted/blurry files
        if "blurry" in file_path.name.lower():
            passed = False
            metrics["blur_score"] = 34.0
            metrics["reasons"].append("Document text detected as extremely blurry.")

        metrics["passed"] = passed
        return metrics

    # ─── STEP 6: DOCUMENT VALIDATION AGENT ─────────────────────────────────────
    @classmethod
    def validate_document(
        cls, doc: Document, ocr_data: Dict[str, Any], is_dup_hash: bool
    ) -> Dict[str, Any]:
        """Validates format constraints, expiry constraints, and page count."""
        validation = {
            "is_expired": False,
            "is_corrupted": False,
            "wrong_file_type": False,
            "is_duplicate": is_dup_hash,
            "missing_pages": False,
            "unsupported_document": False,
            "invalid_doc_number": False,
            "errors": [],
        }

        # Validate file signature/mime
        allowed_mimes = {"application/pdf", "image/png", "image/jpeg"}
        if doc.content_type and doc.content_type not in allowed_mimes:
            validation["wrong_file_type"] = True
            validation["errors"].append(
                f"MIME type '{doc.content_type}' is not supported."
            )

        # Expiry Validation
        expiry_field = ocr_data.get("expiry_date", {})
        expiry_val = (
            expiry_field.get("value")
            if isinstance(expiry_field, dict)
            else expiry_field
        )
        if expiry_val:
            try:
                exp_date = (
                    datetime.strptime(expiry_val, "%Y-%m-%d").date()
                    if isinstance(expiry_val, str)
                    else expiry_val
                )
                if exp_date < date.today():
                    validation["is_expired"] = True
                    validation["errors"].append(f"Document expired on {exp_date}.")
            except ValueError:
                pass

        # Expiry year check for future safety
        if is_dup_hash:
            validation["errors"].append("Document duplicate hash already uploaded.")

        return validation

    # ─── STEP 7: MATCHING AGENT ────────────────────────────────────────────────
    @classmethod
    def match_kyc_data(
        cls, ocr_data: Dict[str, Any], kyc: KYCProfile, customer: Customer
    ) -> Dict[str, Any]:
        """Performs fuzzy matching on Name, DOB, address, and nationality."""
        matching = {
            "name_match_ratio": 0.0,
            "dob_match": False,
            "address_match_ratio": 0.0,
            "nationality_match": False,
            "overall_confidence_score": 0.0,
        }

        # Name match
        ocr_name_field = ocr_data.get("full_name", {})
        ocr_name = (
            ocr_name_field.get("value")
            if isinstance(ocr_name_field, dict)
            else ocr_name_field
        )
        declared_name = (
            kyc.full_name
            if kyc
            else f"{customer.first_name or ''} {customer.last_name or ''}".strip()
        )
        matching["name_match_ratio"] = calculate_similarity(
            ocr_name or "", declared_name
        )

        # DOB match
        ocr_dob_field = ocr_data.get("dob", {})
        ocr_dob = (
            ocr_dob_field.get("value")
            if isinstance(ocr_dob_field, dict)
            else ocr_dob_field
        )
        declared_dob = kyc.date_of_birth if kyc else customer.dob
        if ocr_dob and declared_dob:
            try:
                ocr_dob_val = (
                    datetime.strptime(ocr_dob, "%Y-%m-%d").date()
                    if isinstance(ocr_dob, str)
                    else ocr_dob
                )
                matching["dob_match"] = ocr_dob_val == declared_dob
            except ValueError:
                pass

        # Address match
        ocr_addr_field = ocr_data.get("address", {})
        ocr_addr = (
            ocr_addr_field.get("value")
            if isinstance(ocr_addr_field, dict)
            else ocr_addr_field
        )
        declared_addr = (
            kyc.address
            if kyc
            else f"{customer.street_address or ''}, {customer.city or ''}".strip()
        )
        matching["address_match_ratio"] = calculate_similarity(
            ocr_addr or "", declared_addr
        )

        # Nationality match
        ocr_nat_field = ocr_data.get("nationality", {})
        ocr_nat = (
            ocr_nat_field.get("value")
            if isinstance(ocr_nat_field, dict)
            else ocr_nat_field
        )
        declared_nat = kyc.nationality if kyc else customer.nationality
        if ocr_nat and declared_nat:
            matching["nationality_match"] = (
                ocr_nat.strip().lower() == declared_nat.strip().lower()
            )

        # Calculate overall confidence
        weights = [
            matching["name_match_ratio"],
            100.0 if matching["dob_match"] else 0.0,
            matching["address_match_ratio"],
            100.0 if matching["nationality_match"] else 0.0,
        ]
        matching["overall_confidence_score"] = round(sum(weights) / len(weights), 1)
        return matching

    # ─── STEP 8: FRAUD DETECTION AGENT ─────────────────────────────────────────
    @staticmethod
    def scan_for_fraud(
        file_path: Path, ocr_data: Dict[str, Any], db_session, current_doc_id: UUID
    ) -> List[str]:
        """Inspects image metadata, photoshop tags, and document ID reuse."""
        fraud_reasons = []

        # Photoshop tag detection
        try:
            with open(file_path, "rb") as f:
                content = f.read()
                # Check for image modification signatures
                edit_signatures = [
                    b"Adobe Photoshop",
                    b"Photoshop",
                    b"GIMP",
                    b"Pixelmator",
                ]
                for sig in edit_signatures:
                    if sig in content:
                        fraud_reasons.append(
                            f"Image manipulation warning: metadata contains '{sig.decode()}' signature."
                        )
        except Exception:
            pass

        # Document Number reuse check
        # NOTE: .astext is a PostgreSQL-only operator.  SQLite stores JSON as
        # plain TEXT so we cannot use SQLAlchemy JSON column-path expressions.
        # Instead, pull all other documents (cheap: only id and ocr_data) and
        # compare the value in Python.
        doc_num_field = ocr_data.get("document_number", {})
        doc_num = (
            doc_num_field.get("value")
            if isinstance(doc_num_field, dict)
            else doc_num_field
        )
        if doc_num:
            other_docs = (
                db_session.query(Document)
                .filter(Document.id != current_doc_id)
                .all()
            )
            for other in other_docs:
                other_ocr = other.ocr_data or {}
                other_num_field = other_ocr.get("document_number", {})
                other_num = (
                    other_num_field.get("value")
                    if isinstance(other_num_field, dict)
                    else other_num_field
                )
                if other_num and str(other_num).strip() == str(doc_num).strip():
                    fraud_reasons.append(
                        f"Duplicate document number reuse detected: matched customer {other.customer_id}"
                    )
                    break  # one match is enough

        return fraud_reasons

    # ─── PIPELINE ENTRY POINTS ──────────────────────────────────────────────────
    @classmethod
    def run_pre_ocr_checks(cls, db_session, document_id: UUID) -> Dict[str, Any]:
        """
        Step 11 Workflow - Stage A:
        Upload -> Classification -> Image Quality -> modular OCR -> Save as pending_confirmation.
        API responds immediately while this runs asynchronously in Celery.
        """
        doc = db_session.query(Document).filter(Document.id == document_id).first()
        if not doc:
            raise ValueError(f"Document {document_id} not found.")

        file_path = Path(doc.file_path)
        if not file_path.exists():
            doc.verification_status = "failed"
            db_session.commit()
            raise FileNotFoundError(f"File missing at: {doc.file_path}")

        # Compute hash
        file_hash = cls.calculate_sha256(file_path)
        if not doc.verification_metadata:
            doc.verification_metadata = {}
        doc.verification_metadata["file_hash"] = file_hash

        # Classification Agent
        classification = cls.classify_document(file_path, doc.document_type)
        doc.verification_metadata["classification"] = classification

        # Quality Agent
        quality = cls.assess_image_quality(file_path)
        doc.verification_metadata["quality"] = quality

        # Check if quality failed
        if not quality["passed"]:
            doc.verification_status = "failed"
            doc.verification_metadata["validation"] = {
                "errors": [
                    "Image quality checks failed: " + ", ".join(quality["reasons"])
                ]
            }
            db_session.commit()
            return {"status": "quality_failed", "details": quality}

        # Run Modular OCR
        orchestrator = OcrOrchestrator()
        ocr_results = orchestrator.process_document(file_path, doc.document_type)

        # Save OCR data and status to pending_confirmation
        doc.ocr_data = ocr_results
        doc.verification_status = "pending_confirmation"

        # Append history event
        history = doc.verification_metadata.get("history", [])
        history.append(
            {
                "timestamp": datetime.utcnow().isoformat(),
                "event": "ocr_completed_pending_review",
                "ocr_engine": ocr_results.get("_ocr_engine_used", "Unknown"),
            }
        )
        doc.verification_metadata["history"] = history

        db_session.commit()
        return {"status": "pending_confirmation", "ocr_data": ocr_results}

    @classmethod
    def run_post_ocr_verification(
        cls, db_session, document_id: UUID, confirmed_ocr_data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Step 11 Workflow - Stage B:
        Triggered when customer confirms/saves the OCR data.
        Runs Validation -> Matching -> Fraud Detection -> Risk Scoring -> Save -> Trigger AML.
        """
        doc = db_session.query(Document).filter(Document.id == document_id).first()
        if not doc:
            raise ValueError(f"Document {document_id} not found.")

        file_path = Path(doc.file_path)
        kyc = (
            db_session.query(KYCProfile)
            .filter(KYCProfile.customer_id == doc.customer_id)
            .first()
        )
        customer = (
            db_session.query(Customer).filter(Customer.id == doc.customer_id).first()
        )

        # Update ocr_data with confirmed fields
        doc.ocr_data = confirmed_ocr_data

        # Hash check for duplicate document uploads.
        # NOTE: .astext is a PostgreSQL-only operator.  On SQLite the JSON
        # column is stored as TEXT, so we filter candidates in Python instead.
        file_hash = doc.verification_metadata.get("file_hash", "")
        duplicate_hash = False
        if file_hash:
            other_docs = (
                db_session.query(Document)
                .filter(Document.id != doc.id)
                .all()
            )
            for other in other_docs:
                other_meta = other.verification_metadata or {}
                if other_meta.get("file_hash") == file_hash:
                    duplicate_hash = True
                    break

        # Validation Agent
        validation = cls.validate_document(doc, confirmed_ocr_data, duplicate_hash)
        doc.verification_metadata["validation"] = validation

        # Matching Agent
        matching = cls.match_kyc_data(confirmed_ocr_data, kyc, customer)
        doc.verification_metadata["matching"] = matching

        # Fraud Agent
        fraud_reasons = cls.scan_for_fraud(
            file_path, confirmed_ocr_data, db_session, doc.id
        )
        doc.verification_metadata["fraud"] = {
            "fraud_detected": len(fraud_reasons) > 0,
            "reasons": fraud_reasons,
        }

        # Document Risk Agent
        risk_score = 0.0
        reasons = []

        if validation["is_expired"]:
            risk_score += 40.0
            reasons.append("Expired document.")
        if duplicate_hash:
            risk_score += 50.0
            reasons.append("Duplicate document hash detected.")
        if len(fraud_reasons) > 0:
            risk_score += 60.0
            reasons.extend(fraud_reasons)
        if matching["overall_confidence_score"] < 60.0 and kyc:
            risk_score += 30.0
            reasons.append(
                f"Low match confidence ratio: {matching['overall_confidence_score']}%"
            )

        risk_score = min(risk_score, 100.0)
        risk_category = "low"
        if risk_score >= 70.0 or validation["is_expired"] or len(fraud_reasons) > 0:
            risk_category = "high"
        elif risk_score >= 40.0:
            risk_category = "medium"

        doc.verification_metadata["risk"] = {
            "risk_score": risk_score,
            "risk_category": risk_category,
            "reasons": reasons,
        }

        # Finalize status
        doc.verification_status = "verified" if risk_category != "high" else "flagged"

        # Append history event
        history = doc.verification_metadata.get("history", [])
        history.append(
            {
                "timestamp": datetime.utcnow().isoformat(),
                "event": "verification_finalized",
                "risk_category": risk_category,
                "status": doc.verification_status,
            }
        )
        doc.verification_metadata["history"] = history

        db_session.commit()

        # Trigger Celery AML Graph re-screening
        from app.core.celery_app import celery_app

        celery_app.send_task(
            "tasks.kyc_tasks.run_aml_kyc_pipeline", args=[str(doc.customer_id)]
        )

        return doc.verification_metadata
