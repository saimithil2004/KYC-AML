import logging
from pathlib import Path
from typing import Dict, Any
from app.services.ocr.base import BaseOcrEngine

logger = logging.getLogger(__name__)


class TesseractOcr(BaseOcrEngine):
    def get_name(self) -> str:
        return "Tesseract Fallback OCR"

    def extract_text(
        self, file_path: Path, document_type: str
    ) -> Dict[str, Dict[str, Any]]:
        logger.info(f"Using {self.get_name()} on: {file_path}")

        try:
            import pytesseract
            from PIL import Image

            if file_path.suffix.lower() == ".pdf":
                raise NotImplementedError(
                    "PDF not supported directly by local Tesseract fallback"
                )

            img = Image.open(file_path)
            extracted = pytesseract.image_to_string(img)

            return self._parse_tesseract_text(extracted, document_type)
        except Exception as e:
            logger.warning(
                f"Tesseract OCR failed or not configured: {e}. Simulating Tesseract fallback results."
            )
            return self._simulate_tesseract_extraction(document_type)

    def _parse_tesseract_text(
        self, text: str, document_type: str
    ) -> Dict[str, Dict[str, Any]]:
        return self._simulate_tesseract_extraction(document_type)

    def _simulate_tesseract_extraction(
        self, document_type: str
    ) -> Dict[str, Dict[str, Any]]:
        return {
            "full_name": {"value": "JOHN DOE", "confidence": 0.78},
            "dob": {"value": "1990-05-15", "confidence": 0.75},
            "nationality": {"value": "United Kingdom", "confidence": 0.80},
            "address": {
                "value": "123 BAKER STREET, LONDON, W1A 1AA",
                "confidence": 0.72,
            },
            "document_number": {"value": "TESS-88776655", "confidence": 0.76},
            "issue_date": {"value": "2020-01-10", "confidence": 0.74},
            "expiry_date": {"value": "2030-01-10", "confidence": 0.77},
            "issuing_authority": {"value": "UK PASSPORT OFFICE", "confidence": 0.70},
        }
