import logging
from pathlib import Path
from typing import Dict, Any, List
from app.services.ocr.base import BaseOcrEngine
from app.services.ocr.gemini import GeminiVisionOcr
from app.services.ocr.doctr import DocTrOcr
from app.services.ocr.tesseract import TesseractOcr

logger = logging.getLogger(__name__)

class OcrOrchestrator:
    def __init__(self, engines: List[BaseOcrEngine] = None):
        if engines is None:
            self.engines = [
                GeminiVisionOcr(),
                DocTrOcr(),
                TesseractOcr()
            ]
        else:
            self.engines = engines

    def process_document(self, file_path: Path, document_type: str) -> Dict[str, Any]:
        """
        Processes a document by routing through the OCR engine failover chain.
        First successful extraction returns the result.
        """
        errors = []
        for engine in self.engines:
            try:
                logger.info(f"Orchestrator routing to engine: {engine.get_name()}")
                result = engine.extract_text(file_path, document_type)
                if result and any(result.values()):
                    # Add processing metadata
                    result["_ocr_engine_used"] = engine.get_name()
                    return result
            except Exception as e:
                logger.warning(f"Engine {engine.get_name()} failed with error: {e}")
                errors.append(f"{engine.get_name()}: {str(e)}")

        raise RuntimeError(f"All OCR Engines failed to process document: {', '.join(errors)}")
