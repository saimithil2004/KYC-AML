import abc
from pathlib import Path
from typing import Dict, Any

class BaseOcrEngine(abc.ABC):
    """
    Abstract Base Class for modular OCR engines with field-level confidence scores.
    """

    @abc.abstractmethod
    def extract_text(self, file_path: Path, document_type: str) -> Dict[str, Dict[str, Any]]:
        """
        Extracts structured text from a document.
        Returns a dictionary mapping field names to a dict: {"value": Any, "confidence": float}.
        """
        pass

    @abc.abstractmethod
    def get_name(self) -> str:
        """Returns the name of the OCR engine."""
        pass
