import pytest
from uuid import uuid4
from datetime import date

# Import Integration Layer
from app.services.database_integration.connector import DatabaseConnector
from app.services.database_integration.mapper import DataMapper
from app.services.database_integration.validator import IngestionValidator
from app.services.database_integration.sync_service import SyncService
from app.models.models import Customer, KYCProfile

def test_database_connector_mock():
    conn = DatabaseConnector()
    assert conn.mock_mode is True
    hc = conn.health_check()
    assert hc["status"] == "healthy"
    assert hc["mode"] == "mock_simulation"

def test_mapper_normalization():
    # Phone clean
    assert DataMapper.normalize_phone("+44-7700-900077") == "+447700900077"
    assert DataMapper.normalize_phone("07700 900 088") == "07700900088"
    
    # Currency caps
    assert DataMapper.normalize_currency("usd") == "USD"
    assert DataMapper.normalize_currency("  gbp  ") == "GBP"
    
    # Country clean
    assert DataMapper.normalize_country("uk") == "United Kingdom"
    assert DataMapper.normalize_country("gbr") == "United Kingdom"
    assert DataMapper.normalize_country("france") == "France"

    # Date parsing
    assert DataMapper.parse_date("1990-05-15") == date(1990, 5, 15)
    assert DataMapper.parse_date(date(2020, 1, 1)) == date(2020, 1, 1)
    assert DataMapper.parse_date("") is None

def test_ingestion_validator():
    # 1. Customer validate
    valid_c = {
        "first_name": "Jack",
        "last_name": "Roberts",
        "email": "jack.roberts@externalbank.com",
        "phone": "+447700900077",
        "dob": "1985-04-12",
        "nationality": "United Kingdom",
        "country": "United Kingdom"
    }
    
    is_v1, errs1 = IngestionValidator.validate_customer(valid_c, [], [])
    assert is_v1 is True
    
    # Missing field
    invalid_c = valid_c.copy()
    invalid_c["email"] = None
    is_v2, errs2 = IngestionValidator.validate_customer(invalid_c, [], [])
    assert is_v2 is False
    assert "Missing" in errs2[0]

    # Duplicate check
    is_v3, errs3 = IngestionValidator.validate_customer(valid_c, ["jack.roberts@externalbank.com"], [])
    assert is_v3 is False
    assert "Duplicate" in errs3[0]

def test_data_quality_score():
    customer = Customer(
        first_name="John",
        last_name="Doe",
        phone_number="+447700900077",
        street_address="123 Road",
        city="London",
        postal_code="EC1A 1BB"
    )
    
    # Complete profile
    kyc = KYCProfile(
        full_name="John Doe",
        date_of_birth=date(1990, 5, 15),
        nationality="United Kingdom",
        address="123 Road",
        source_of_funds="salaried",
        source_of_wealth="savings"
    )
    
    res = SyncService.calculate_data_quality_score(customer, kyc, [1])
    assert res["quality_score"] == 100.0

    # Incomplete profile (missing phone)
    cust_incomplete = Customer(
        first_name="Jane",
        last_name="Doe",
        phone_number=None,
        street_address="123 Road"
    )
    res_incomplete = SyncService.calculate_data_quality_score(cust_incomplete, None, [])
    assert res_incomplete["quality_score"] < 50.0
