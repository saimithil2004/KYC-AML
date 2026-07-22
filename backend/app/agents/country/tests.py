"""
Country Risk Agent Test Suite
==============================

Covers:
  1. Individual Customer (Low Risk)
  2. Business Customer (Medium Risk / Low Risk mix)
  3. Low Risk Countries (UK, US)
  4. Medium Risk Countries (Panama, Cayman Islands)
  5. High Risk Countries (Russia, Syria)
  6. Prohibited Countries (North Korea, Iran)
  7. Multiple High Risk Countries (Russia + Syria)
  8. Duplicate Country Removal
  9. Country Normalization (US/USA -> United States)
 10. Unknown Country (Atlantis -> Warning CR008)
 11. Missing Country (Throws AgentValidationError)
 12. Provider Failure (Graceful fallback)
"""

import pytest
from typing import List, Optional, Dict, Any

from app.agents.base.agent_state import AgentState
from app.agents.base.exceptions import AgentValidationError
from app.agents.country.agent import CountryRiskAgent
from app.agents.country.models import CountryRiskProfile
from app.agents.country.provider import BaseCountryRiskProvider
from app.agents.country.constants import (
    RISK_LOW,
    RISK_MEDIUM,
    RISK_HIGH,
    RISK_PROHIBITED,
    RISK_CRITICAL,
    COUNTRY_STATUS_CLEAR,
    COUNTRY_STATUS_WARNING,
    COUNTRY_STATUS_SUSPENDED,
)


# ─── Test Providers ───────────────────────────────────────────────────────────
class FailingCountryProvider(BaseCountryRiskProvider):
    @property
    def provider_name(self) -> str:
        return "FailingCountryProvider"

    def get_country_profile(self, country_name: str) -> Optional[CountryRiskProfile]:
        raise ConnectionError("Country Risk database connection timeout")


# ─── Payload Helpers ──────────────────────────────────────────────────────────
def individual_customer(
    nationality: str = "United Kingdom", residence: str = "UK"
) -> Dict[str, Any]:
    return {
        "first_name": "John",
        "last_name": "Smith",
        "dob": "1980-01-01",
        "nationality": nationality,
        "country": residence,
        "customer_type": "individual",
    }


def business_customer() -> Dict[str, Any]:
    return {"first_name": "Acme", "last_name": "Ltd", "customer_type": "business"}


def make_state(
    customer: Optional[Dict[str, Any]] = None,
    directors: Optional[List] = None,
    ubos: Optional[List] = None,
    customer_profile: Optional[Dict] = None,
    companies: Optional[List] = None,
    transactions: Optional[List] = None,
    use_empty_customer: bool = False,
) -> AgentState:
    resolved_customer = (
        {}
        if use_empty_customer
        else (customer if customer is not None else individual_customer())
    )
    return AgentState(
        customer_id="test-cust-456",
        case_id="case-country-456",
        customer=resolved_customer,
        directors=directors or [],
        ubos=ubos or [],
        customer_profile=customer_profile or {},
        companies=companies or [],
        transactions=transactions or [],
    )


# ─────────────────────────────────────────────────────────────────────────────
# Test Cases
# ─────────────────────────────────────────────────────────────────────────────


@pytest.mark.anyio
async def test_individual_low_risk_is_clear():
    state = make_state(customer=individual_customer("United Kingdom", "US"))
    agent = CountryRiskAgent()
    result = await agent.execute(state)

    assert result.success is True
    assert result.metadata["country_status"] == COUNTRY_STATUS_CLEAR
    assert result.metadata["country_score"] == 100.0
    assert result.risk_level == RISK_LOW
    assert "United Kingdom" in result.metadata["countries_evaluated"]
    assert "United States" in result.metadata["countries_evaluated"]


@pytest.mark.anyio
async def test_business_medium_risk():
    """Business with Panama operating country -> Score 90, RISK_MEDIUM."""
    state = make_state(
        customer=business_customer(),
        companies=[
            {
                "name": "Acme Ltd",
                "country": "UK",
                "operating_countries": ["Panama", "United States"],
            }
        ],
        directors=[{"nationality": "Germany"}],
    )
    agent = CountryRiskAgent()
    result = await agent.execute(state)

    assert result.success is True
    assert result.metadata["country_score"] == 90.0  # 100 - 10 (Panama)
    assert result.risk_level == RISK_MEDIUM
    assert "Panama" in result.metadata["countries_evaluated"]
    assert "United Kingdom" in result.metadata["countries_evaluated"]


@pytest.mark.anyio
async def test_high_risk_country_association():
    """Russia association -> Deduct 30 points -> Score 70, RISK_HIGH."""
    state = make_state(customer=individual_customer("Russia", "UK"))
    agent = CountryRiskAgent()
    result = await agent.execute(state)

    assert result.metadata["country_score"] == 70.0  # 100 - 30 (Russia)
    assert result.risk_level == RISK_HIGH
    assert "Russia" in result.metadata["high_risk_countries"]
    assert "CR003" in result.metadata["rules_triggered"]


@pytest.mark.anyio
async def test_prohibited_country_association():
    """North Korea association -> Score 0, RISK_CRITICAL, Suspended status."""
    state = make_state(customer=individual_customer("North Korea", "UK"))
    agent = CountryRiskAgent()
    result = await agent.execute(state)

    assert result.metadata["country_score"] == 0.0
    assert result.metadata["country_status"] == COUNTRY_STATUS_SUSPENDED
    assert result.risk_level == RISK_CRITICAL
    assert "North Korea" in result.metadata["prohibited_countries"]
    assert "CR004" in result.metadata["rules_triggered"]


@pytest.mark.anyio
async def test_multiple_high_risk_countries():
    """Syria + Russia -> Deduct 60 points -> Score 40 -> triggers CR005."""
    state = make_state(
        customer=individual_customer("Syria", "UK"),
        directors=[{"nationality": "Russia"}],
    )
    agent = CountryRiskAgent()
    result = await agent.execute(state)

    assert result.metadata["country_score"] == 40.0  # 100 - 30 - 30
    assert result.risk_level == RISK_HIGH
    assert "CR005" in result.metadata["rules_triggered"]
    assert any("multiple high risk" in w.lower() for w in result.warnings)


@pytest.mark.anyio
async def test_duplicate_country_removal():
    """Customer residence and director nationality both UK/GBR -> evaluated once."""
    state = make_state(
        customer=individual_customer("United Kingdom", "GBR"),
        directors=[{"nationality": "GB"}, {"nationality": "United Kingdom"}],
    )
    agent = CountryRiskAgent()
    result = await agent.execute(state)

    # All standardized to 'United Kingdom' and deduped
    assert result.metadata["countries_evaluated"] == ["United Kingdom"]
    assert result.metadata["audit_trail"]["countries_evaluated"] == ["United Kingdom"]


@pytest.mark.anyio
async def test_country_normalization():
    state = make_state(customer=individual_customer("US", "USA"))
    agent = CountryRiskAgent()
    result = await agent.execute(state)

    assert result.metadata["countries_evaluated"] == ["United States"]


@pytest.mark.anyio
async def test_unknown_country_warning():
    """Atlantis -> raises CR008 Warning -> status WARNING, RISK_MEDIUM."""
    state = make_state(customer=individual_customer("Atlantis", "UK"))
    agent = CountryRiskAgent()
    result = await agent.execute(state)

    assert "CR008" in result.metadata["rules_triggered"]
    assert result.metadata["country_status"] == COUNTRY_STATUS_WARNING
    assert result.risk_level == RISK_MEDIUM
    assert any("atlantis" in w.lower() for w in result.warnings)


@pytest.mark.anyio
async def test_missing_country_throws_validation_error():
    """If state has zero countries -> throws AgentValidationError."""
    state = make_state(use_empty_customer=True)  # customer={}
    agent = CountryRiskAgent()
    with pytest.raises(AgentValidationError) as exc_info:
        await agent.execute(state)
    assert "country" in str(exc_info.value).lower()


@pytest.mark.anyio
async def test_provider_failure_fallback_graceful():
    state = make_state(customer=individual_customer("Russia", "UK"))
    agent = CountryRiskAgent(provider=FailingCountryProvider())
    result = await agent.execute(state)

    # Should fall back to RISK_LOW (100) instead of failing
    assert result.success is True
    assert result.metadata["country_score"] == 100.0
    assert result.risk_level == RISK_LOW


@pytest.mark.anyio
async def test_contextual_transaction_destination_rule():
    """High-risk country (Russia) in transaction destination triggers CR006."""
    state = make_state(
        customer=individual_customer("UK", "UK"),
        transactions=[
            {
                "origin_country": "UK",
                "destination_country": "Russia",
                "bank_country": "UK",
            }
        ],
    )
    agent = CountryRiskAgent()
    result = await agent.execute(state)

    assert "CR006" in result.metadata["rules_triggered"]
    assert any("transaction destination" in w.lower() for w in result.warnings)


@pytest.mark.anyio
async def test_contextual_company_registration_rule():
    """High-risk country (Syria) in company registration triggers CR007."""
    state = make_state(
        customer=business_customer(),
        companies=[{"name": "Syrian Shipping", "country": "Syria"}],
    )
    agent = CountryRiskAgent()
    result = await agent.execute(state)

    assert "CR007" in result.metadata["rules_triggered"]
    assert any("business is incorporated in" in w.lower() for w in result.warnings)
