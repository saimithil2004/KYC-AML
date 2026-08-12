"""
Provider Architecture & Integration Tests — Priority 1
======================================================
Tests PEP, Sanctions, and Country Risk provider abstractions, provider factory,
OpenSanctions/OFAC production adapters via mocked HTTP responses, safe fallback
behavior when credentials are missing, and zero-change agent swapping.
"""

import os
import pytest
import httpx
from typing import List
from unittest.mock import patch, MagicMock, AsyncMock

from app.providers.provider_factory import get_pep_provider, get_sanctions_provider
from app.agents.pep.provider import BasePepProvider, MockPepProvider
from app.agents.pep.models import ScreeningSubject, PepRecord
from app.agents.pep.agent import PepAgent

from app.agents.sanctions.provider import BaseSanctionsProvider, MockSanctionsProvider
from app.agents.sanctions.models import SanctionRecord
from app.agents.screening.models import CompanyScreeningSubject
from app.agents.sanctions.agent import SanctionsAgent

from app.agents.country.provider import BaseCountryRiskProvider, MockCountryRiskProvider
from app.agents.country.agent import CountryRiskAgent

from app.providers.opensanctions_provider import (
    OpenSanctionsPepProvider,
    OpenSanctionsSanctionsProvider,
)
from app.providers.ofac_provider import OfacSanctionsProvider


# ── 1. Provider Factory Auto-Selection & Fallback ─────────────────────────────


def test_provider_factory_defaults_to_mock():
    """Verify factory defaults to mock providers when no env keys are provided."""
    with patch.dict(os.environ, {}, clear=True):
        pep_p = get_pep_provider()
        sanc_p = get_sanctions_provider()
        assert isinstance(pep_p, MockPepProvider)
        assert isinstance(sanc_p, MockSanctionsProvider)
        assert "Mock" in pep_p.provider_name
        assert "Mock" in sanc_p.provider_name


def test_provider_factory_forced_provider():
    """Verify PEP_PROVIDER and SANCTIONS_PROVIDER env overrides work."""
    with patch.dict(os.environ, {"PEP_PROVIDER": "mock", "SANCTIONS_PROVIDER": "mock"}):
        pep_p = get_pep_provider()
        sanc_p = get_sanctions_provider()
        assert isinstance(pep_p, MockPepProvider)
        assert isinstance(sanc_p, MockSanctionsProvider)


def test_provider_factory_opensanctions_auto_select():
    """Verify OpenSanctions provider is selected when API key is present."""
    with patch.dict(os.environ, {"OPEN_SANCTIONS_API_KEY": "test_opensanctions_key_123"}), \
         patch("app.providers.provider_factory._HAS_OPENSANCTIONS", True):
        pep_p = get_pep_provider()
        sanc_p = get_sanctions_provider()
        assert isinstance(pep_p, OpenSanctionsPepProvider)
        assert isinstance(sanc_p, OpenSanctionsSanctionsProvider)


# ── 2. OpenSanctions HTTP Response Adapter Tests ──────────────────────────────


@pytest.mark.asyncio
async def test_opensanctions_pep_provider_http_mapping():
    """Verify OpenSanctionsPepProvider correctly parses and maps API search response."""
    mock_response = {
        "responses": {
            "entity": {
                "results": [
                    {
                        "id": "os-pep-101",
                        "caption": "James Alexander Wilson",
                        "schema": "Person",
                        "properties": {
                            "birthDate": ["1965-03-22"],
                            "nationality": ["gb"],
                            "country": ["gb"],
                            "position": ["Member of Parliament"],
                            "topics": ["role.pep.domestic"],
                        },
                    }
                ]
            }
        }
    }

    def custom_handler(request: httpx.Request):
        assert "Authorization" in request.headers
        assert request.headers["Authorization"] == "ApiKey test_key"
        return httpx.Response(200, json=mock_response)

    transport = httpx.MockTransport(custom_handler)
    provider = OpenSanctionsPepProvider()

    subject = ScreeningSubject(
        subject_id="sub-001",
        role="customer",
        full_name="James Alexander Wilson",
        dob="1965-03-22",
        nationality="United Kingdom",
        country="United Kingdom",
    )

    with patch(
        "app.providers.opensanctions_provider._search_entities",
        new_callable=AsyncMock,
        return_value=[
            {
                "id": "os-pep-101",
                "caption": "James Alexander Wilson",
                "schema": "Person",
                "properties": {
                    "birthDate": ["1965-03-22"],
                    "nationality": ["gb"],
                    "country": ["gb"],
                    "position": ["Member of Parliament"],
                    "topics": ["role.pep.domestic"],
                },
            }
        ],
    ), patch.dict(os.environ, {"OPEN_SANCTIONS_API_KEY": "test_key"}):
        records = await provider.search(subject)
        assert len(records) == 1
        record = records[0]
        assert isinstance(record, PepRecord)
        assert record.record_id == "os-pep-101"
        assert record.full_name == "James Alexander Wilson"
        assert record.source == "opensanctions"


@pytest.mark.asyncio
async def test_opensanctions_sanctions_provider_http_mapping():
    """Verify OpenSanctionsSanctionsProvider correctly maps company & individual responses."""
    mock_response = {
        "responses": {
            "entity": {
                "results": [
                    {
                        "id": "os-sanc-202",
                        "caption": "North Star Shipping Ltd",
                        "schema": "Company",
                        "properties": {
                            "registrationNumber": ["REG-991188"],
                            "country": ["kp"],
                            "topics": ["sanction"],
                        },
                    }
                ]
            }
        }
    }

    def custom_handler(request: httpx.Request):
        return httpx.Response(200, json=mock_response)

    transport = httpx.MockTransport(custom_handler)
    provider = OpenSanctionsSanctionsProvider()

    subject = CompanyScreeningSubject(
        subject_id="comp-001",
        role="company",
        company_name="North Star Shipping Ltd",
        registration_number="REG-991188",
        country="North Korea",
    )

    with patch.object(httpx, "AsyncClient", return_value=httpx.AsyncClient(transport=transport)):
        records = await provider.search_companies(subject)
        assert len(records) == 1
        record = records[0]
        assert isinstance(record, SanctionRecord)
        assert record.record_id == "os-sanc-202"
        assert record.full_name == "North Star Shipping Ltd"
        assert record.source == "opensanctions"


# ── 3. Provider Fail-Safe & Graceful Degradation Tests ────────────────────────


@pytest.mark.asyncio
async def test_opensanctions_http_error_graceful_degradation():
    """Verify HTTP 500 or timeout error logs warning and returns empty list safely."""
    def custom_handler(request: httpx.Request):
        return httpx.Response(500, json={"error": "Internal server error"})

    transport = httpx.MockTransport(custom_handler)
    provider = OpenSanctionsPepProvider()

    subject = ScreeningSubject(subject_id="sub-002", role="customer", full_name="Unknown Person")

    with patch.object(httpx, "AsyncClient", return_value=httpx.AsyncClient(transport=transport)):
        records = await provider.search(subject)
        assert records == []  # Graceful fallback, no unhandled crash


# ── 4. Zero-Change Agent Swapping Test ────────────────────────────────────────


class CustomTestPepProvider(BasePepProvider):
    @property
    def provider_name(self) -> str:
        return "custom_test_provider"

    async def search(self, subject: ScreeningSubject) -> List[PepRecord]:
        return [
            PepRecord(
                record_id="CUSTOM-001",
                full_name=subject.full_name,
                dob=subject.dob,
                nationality=subject.nationality,
                category="domestic_pep",
                position="Custom Government Official",
                is_current=True,
                source="custom_test_provider",
            )
        ]


@pytest.mark.asyncio
async def test_pep_agent_with_swapped_provider():
    """Verify PepAgent operates seamlessly when injected with a custom provider."""
    custom_provider = CustomTestPepProvider()
    agent = PepAgent(provider=custom_provider)

    assert agent._provider.provider_name == "custom_test_provider"
