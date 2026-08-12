"""
AML/KYC Platform — Production Provider Package
===============================================
Exposes all production-ready PEP and Sanctions screening providers.

Provider selection is controlled via environment variables:
  PEP_PROVIDER       : opensanctions | worldcheck | dowjones | mock
  SANCTIONS_PROVIDER : opensanctions | ofac | worldcheck | dowjones | mock

If a provider API key is absent, the factory falls back to MockProvider so
tests and local development never break.
"""

from app.providers.provider_factory import get_pep_provider, get_sanctions_provider
from app.providers.opensanctions_provider import OpenSanctionsPepProvider, OpenSanctionsSanctionsProvider
from app.providers.ofac_provider import OfacSanctionsProvider
from app.providers.worldcheck_provider import WorldCheckPepProvider, WorldCheckSanctionsProvider
from app.providers.dowjones_provider import DowJonesPepProvider, DowJonesSanctionsProvider
from app.providers.companies_house_provider import CompaniesHouseProvider

__all__ = [
    "get_pep_provider",
    "get_sanctions_provider",
    "OpenSanctionsPepProvider",
    "OpenSanctionsSanctionsProvider",
    "OfacSanctionsProvider",
    "WorldCheckPepProvider",
    "WorldCheckSanctionsProvider",
    "DowJonesPepProvider",
    "DowJonesSanctionsProvider",
    "CompaniesHouseProvider",
]
