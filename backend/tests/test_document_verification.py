import pytest
from pathlib import Path
from uuid import uuid4
from datetime import date

# Mock DB Session
class MockQuery:
    def __init__(self, items):
        self.items = items
    def filter(self, *args, **kwargs):
        return self
    def first(self):
        return self.items[0] if self.items else None
    def all(self):
        return self.items

class MockDb:
    def __init__(self, queries=None):
        self.queries = queries or {}
        self.committed = False
        self.rolled_back = False
    def query(self, model):
        return MockQuery(self.queries.get(model, []))
    def commit(self):
        self.committed = True
    def rollback(self):
        self.rolled_back = True

# Import Verification Service
from app.services.document_verification import DocumentVerificationService, calculate_similarity
from app.models.models import Document, KYCProfile, Customer

def test_fuzzy_match_ratios():
    # Identical
    assert calculate_similarity("Isabella Thomas", "Isabella Thomas") == 100.0
    # Nickname / slight difference
    assert calculate_similarity("Isabella Thomas", "Isabella Thompson") >= 80.0
    # Empty
    assert calculate_similarity("", "John Doe") == 0.0

def test_document_classification():
    p1 = Path("temp_passport.png")
    res1 = DocumentVerificationService.classify_document(p1, "passport")
    assert res1["classified_type"] == "passport"

    p2 = Path("ubo_details_draft.pdf")
    res2 = DocumentVerificationService.classify_document(p2, "ubo_document")
    assert res2["classified_type"] == "ubo_document"

def test_image_quality_agent():
    # Test low size file (low resolution / unreadable fallback)
    p_tiny = Path("tiny_image.jpg")
    # Simulate file properties
    class MockPath:
        def __init__(self, name, size):
            self.name = name
            self._size = size
        def stat(self):
            class Stat:
                st_size = self._size
            return Stat()
    
    tiny_ref = MockPath("tiny.jpg", 1024) # 1KB
    res = DocumentVerificationService.assess_image_quality(tiny_ref)
    assert res["passed"] is False
    assert "resolution" in res["reasons"][0]

def test_document_validation():
    doc = Document(
        id=uuid4(),
        customer_id=uuid4(),
        document_type="passport",
        file_name="passport.png",
        file_path="passport.png",
        content_type="image/png",
        file_size=2048,
        verification_status="uploaded"
    )
    
    # 1. Past Expiry check
    ocr_data = {
        "expiry_date": {"value": "2020-05-15"}
    }
    validation = DocumentVerificationService.validate_document(doc, ocr_data, is_dup_hash=False)
    assert validation["is_expired"] is True

    # 2. Future Expiry check
    ocr_data_valid = {
        "expiry_date": {"value": "2035-12-31"}
    }
    validation_valid = DocumentVerificationService.validate_document(doc, ocr_data_valid, is_dup_hash=False)
    assert validation_valid["is_expired"] is False
