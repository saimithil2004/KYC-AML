"""
Provider Factory
=================
Selects the appropriate PEP and Sanctions provider based on environment config.

Priority order (first configured wins):
  PEP      : opensanctions → worldcheck → dowjones → mock
  Sanctions: opensanctions → ofac → worldcheck → dowjones → mock

This factory is the single point of truth for provider selection.
It is called by PepAgent and SanctionsAgent constructors.

Environment Variables:
  PEP_PROVIDER            : Force a specific PEP provider (opensanctions|worldcheck|dowjones|mock)
  SANCTIONS_PROVIDER      : Force a specific sanctions provider (opensanctions|ofac|worldcheck|dowjones|mock)
  OPEN_SANCTIONS_API_KEY  : Enables OpenSanctions provider
  OFAC_API_KEY            : Enables OFAC provider
  WORLD_CHECK_API_KEY     : Enables World-Check provider
  DOW_JONES_API_KEY       : Enables Dow Jones provider
"""

import logging
import os

logger = logging.getLogger(__name__)

# ─── Forced provider names (from env) ────────────────────────────────────────
_FORCED_PEP = os.getenv("PEP_PROVIDER", "").lower().strip()
_FORCED_SANCTIONS = os.getenv("SANCTIONS_PROVIDER", "").lower().strip()

# ─── API key availability ─────────────────────────────────────────────────────
_HAS_OPENSANCTIONS = bool(os.getenv("OPEN_SANCTIONS_API_KEY", ""))
_HAS_OFAC = bool(os.getenv("OFAC_API_KEY", ""))
_HAS_WORLDCHECK = bool(
    os.getenv("WORLD_CHECK_API_KEY", "") and os.getenv("WORLD_CHECK_API_SECRET", "")
)
_HAS_DOWJONES = bool(
    os.getenv("DOW_JONES_API_KEY", "") and os.getenv("DOW_JONES_API_SECRET", "")
)


def get_pep_provider():
    """
    Returns the appropriate PEP provider based on env configuration.
    Falls back to MockPepProvider if no real API keys are configured.

    Returns
    -------
    BasePepProvider instance
    """
    # If PEP_PROVIDER is explicitly set, honor it
    if _FORCED_PEP == "opensanctions":
        from app.providers.opensanctions_provider import OpenSanctionsPepProvider
        logger.info("PEP Provider: OpenSanctions (forced via PEP_PROVIDER env)")
        return OpenSanctionsPepProvider()

    if _FORCED_PEP == "worldcheck":
        from app.providers.worldcheck_provider import WorldCheckPepProvider
        logger.info("PEP Provider: World-Check (forced via PEP_PROVIDER env)")
        return WorldCheckPepProvider()

    if _FORCED_PEP == "dowjones":
        from app.providers.dowjones_provider import DowJonesPepProvider
        logger.info("PEP Provider: Dow Jones (forced via PEP_PROVIDER env)")
        return DowJonesPepProvider()

    if _FORCED_PEP == "mock":
        from app.agents.pep.provider import MockPepProvider
        logger.info("PEP Provider: Mock (forced via PEP_PROVIDER env)")
        return MockPepProvider()

    # Auto-select based on available API keys (priority order)
    if _HAS_OPENSANCTIONS:
        from app.providers.opensanctions_provider import OpenSanctionsPepProvider
        logger.info("PEP Provider: OpenSanctions (auto-selected, API key found)")
        return OpenSanctionsPepProvider()

    if _HAS_WORLDCHECK:
        from app.providers.worldcheck_provider import WorldCheckPepProvider
        logger.info("PEP Provider: World-Check (auto-selected, credentials found)")
        return WorldCheckPepProvider()

    if _HAS_DOWJONES:
        from app.providers.dowjones_provider import DowJonesPepProvider
        logger.info("PEP Provider: Dow Jones (auto-selected, credentials found)")
        return DowJonesPepProvider()

    # Final fallback — development/test mode
    from app.agents.pep.provider import MockPepProvider
    logger.warning(
        "PEP Provider: MockPepProvider — NO production API keys found. "
        "Set OPEN_SANCTIONS_API_KEY, WORLD_CHECK_API_KEY, or DOW_JONES_API_KEY "
        "in .env for real screening. THIS IS NOT PRODUCTION-SAFE."
    )
    return MockPepProvider()


def get_sanctions_provider():
    """
    Returns the appropriate Sanctions provider based on env configuration.
    Falls back to MockSanctionsProvider if no real API keys are configured.

    Returns
    -------
    BaseSanctionsProvider instance
    """
    # If SANCTIONS_PROVIDER is explicitly set, honor it
    if _FORCED_SANCTIONS == "opensanctions":
        from app.providers.opensanctions_provider import OpenSanctionsSanctionsProvider
        logger.info("Sanctions Provider: OpenSanctions (forced via SANCTIONS_PROVIDER env)")
        return OpenSanctionsSanctionsProvider()

    if _FORCED_SANCTIONS == "ofac":
        from app.providers.ofac_provider import OfacSanctionsProvider
        logger.info("Sanctions Provider: OFAC (forced via SANCTIONS_PROVIDER env)")
        return OfacSanctionsProvider()

    if _FORCED_SANCTIONS == "worldcheck":
        from app.providers.worldcheck_provider import WorldCheckSanctionsProvider
        logger.info("Sanctions Provider: World-Check (forced via SANCTIONS_PROVIDER env)")
        return WorldCheckSanctionsProvider()

    if _FORCED_SANCTIONS == "dowjones":
        from app.providers.dowjones_provider import DowJonesSanctionsProvider
        logger.info("Sanctions Provider: Dow Jones (forced via SANCTIONS_PROVIDER env)")
        return DowJonesSanctionsProvider()

    if _FORCED_SANCTIONS == "mock":
        from app.agents.sanctions.provider import MockSanctionsProvider
        logger.info("Sanctions Provider: Mock (forced via SANCTIONS_PROVIDER env)")
        return MockSanctionsProvider()

    # Auto-select based on available API keys (priority order)
    if _HAS_OPENSANCTIONS:
        from app.providers.opensanctions_provider import OpenSanctionsSanctionsProvider
        logger.info("Sanctions Provider: OpenSanctions (auto-selected, API key found)")
        return OpenSanctionsSanctionsProvider()

    if _HAS_OFAC:
        from app.providers.ofac_provider import OfacSanctionsProvider
        logger.info("Sanctions Provider: OFAC (auto-selected, API key found)")
        return OfacSanctionsProvider()

    if _HAS_WORLDCHECK:
        from app.providers.worldcheck_provider import WorldCheckSanctionsProvider
        logger.info("Sanctions Provider: World-Check (auto-selected, credentials found)")
        return WorldCheckSanctionsProvider()

    if _HAS_DOWJONES:
        from app.providers.dowjones_provider import DowJonesSanctionsProvider
        logger.info("Sanctions Provider: Dow Jones (auto-selected, credentials found)")
        return DowJonesSanctionsProvider()

    # Final fallback — development/test mode
    from app.agents.sanctions.provider import MockSanctionsProvider
    logger.warning(
        "Sanctions Provider: MockSanctionsProvider — NO production API keys found. "
        "Set OPEN_SANCTIONS_API_KEY, OFAC_API_KEY, WORLD_CHECK_API_KEY, "
        "or DOW_JONES_API_KEY in .env for real screening. "
        "THIS IS NOT PRODUCTION-SAFE."
    )
    return MockSanctionsProvider()
