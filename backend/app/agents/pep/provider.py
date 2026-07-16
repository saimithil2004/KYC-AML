"""
PEP Provider Architecture
==========================

BasePepProvider
    Abstract interface that decouples the PEP Agent from any specific data
    source.  Every future provider (OpenSanctions, World-Check, Dow Jones,
    internal DB) implements this interface and nothing else changes.

MockPepProvider
    Deterministic in-memory dataset for development and testing.
    Contains realistic records covering all PEP categories so that every
    test scenario can be exercised without external network calls.

Usage
-----
    provider = MockPepProvider()
    records  = await provider.search(subject)

Future providers (same interface, zero changes to PepAgent):
    provider = OpenSanctionsProvider(api_key=...)
    provider = WorldCheckProvider(credentials=...)
    provider = DowJonesProvider(api_key=...)
"""

import abc
from typing import List

from app.agents.pep.models import ScreeningSubject, PepRecord
from app.agents.pep.constants import (
    PEP_CATEGORY_DOMESTIC, PEP_CATEGORY_FOREIGN,
    PEP_CATEGORY_INTERNATIONAL_ORG, PEP_CATEGORY_FAMILY_MEMBER,
    PEP_CATEGORY_CLOSE_ASSOCIATE, PEP_CATEGORY_FORMER_PEP,
    PEP_CATEGORY_CURRENT_PEP, PROVIDER_MOCK,
)


# ─────────────────────────────────────────────────────────────────────────────
# Abstract Base Provider
# ─────────────────────────────────────────────────────────────────────────────
class BasePepProvider(abc.ABC):
    """
    Provider interface for all PEP data sources.

    Implementors must override ``search()``.  The PEP Agent is coded
    exclusively against this interface — swapping providers requires
    zero changes to agent, matcher, or rules code.
    """

    @property
    @abc.abstractmethod
    def provider_name(self) -> str:
        """Human-readable name logged in audit trails."""

    @abc.abstractmethod
    async def search(self, subject: ScreeningSubject) -> List[PepRecord]:
        """
        Search the PEP dataset for records matching the given subject.

        Parameters
        ----------
        subject : ScreeningSubject
            The normalised person to screen.

        Returns
        -------
        List[PepRecord]
            Zero or more candidate PEP records.  The matching engine
            then scores each candidate and selects the best match.
        """


# ─────────────────────────────────────────────────────────────────────────────
# Mock Provider — deterministic, in-memory, suitable for tests
# ─────────────────────────────────────────────────────────────────────────────

# Realistic mock dataset.  Each record covers a distinct PEP category so
# every business rule (PEP001–PEP007) can be exercised in tests.
_MOCK_PEP_DATABASE: List[PepRecord] = [

    # ── Domestic PEP — Current ──────────────────────────────────────────────
    PepRecord(
        record_id="PEP-UK-001",
        full_name="James Alexander Wilson",
        dob="1965-03-22",
        nationality="United Kingdom",
        country="United Kingdom",
        category=PEP_CATEGORY_DOMESTIC,
        position="Member of Parliament, Treasury Select Committee",
        is_current=True,
        source=PROVIDER_MOCK,
        last_updated="2024-01-01",
    ),

    # ── Foreign PEP — Current ───────────────────────────────────────────────
    PepRecord(
        record_id="PEP-FR-001",
        full_name="Jean-Pierre Moreau",
        dob="1972-07-14",
        nationality="France",
        country="France",
        category=PEP_CATEGORY_FOREIGN,
        position="Deputy Minister of Finance, France",
        is_current=True,
        source=PROVIDER_MOCK,
        last_updated="2024-01-01",
    ),

    # ── International Organisation PEP ─────────────────────────────────────
    PepRecord(
        record_id="PEP-INT-001",
        full_name="Maria Elena Rodriguez",
        dob="1968-11-05",
        nationality="Spain",
        country="Belgium",
        category=PEP_CATEGORY_INTERNATIONAL_ORG,
        position="Senior Director, European Central Bank",
        is_current=True,
        source=PROVIDER_MOCK,
        last_updated="2024-01-01",
    ),

    # ── Family Member of PEP ────────────────────────────────────────────────
    PepRecord(
        record_id="PEP-FAM-001",
        full_name="Sarah Wilson",
        dob="1970-08-19",
        nationality="United Kingdom",
        country="United Kingdom",
        category=PEP_CATEGORY_FAMILY_MEMBER,
        position="Spouse of James Alexander Wilson (MP)",
        is_current=True,
        source=PROVIDER_MOCK,
        last_updated="2024-01-01",
    ),

    # ── Close Associate ─────────────────────────────────────────────────────
    PepRecord(
        record_id="PEP-ASC-001",
        full_name="Robert Chen",
        dob="1967-04-30",
        nationality="United Kingdom",
        country="United Kingdom",
        category=PEP_CATEGORY_CLOSE_ASSOCIATE,
        position="Business Associate of former Minister",
        is_current=True,
        source=PROVIDER_MOCK,
        last_updated="2024-01-01",
    ),

    # ── Former PEP ─────────────────────────────────────────────────────────
    PepRecord(
        record_id="PEP-FMR-001",
        full_name="David Thomas Hughes",
        dob="1955-12-01",
        nationality="United Kingdom",
        country="United Kingdom",
        category=PEP_CATEGORY_FORMER_PEP,
        position="Former Secretary of State for Home Affairs",
        is_current=False,
        source=PROVIDER_MOCK,
        last_updated="2024-01-01",
    ),

    # ── Fuzzy match candidate (slightly different name spelling) ────────────
    PepRecord(
        record_id="PEP-FUZ-001",
        full_name="Alexei Volkov",
        dob="1980-06-15",
        nationality="Russia",
        country="Russia",
        category=PEP_CATEGORY_FOREIGN,
        position="Regional Governor",
        is_current=True,
        source=PROVIDER_MOCK,
        last_updated="2024-01-01",
    ),
]


class MockPepProvider(BasePepProvider):
    """
    In-memory PEP provider using a hardcoded but realistic dataset.

    ``search()`` returns ALL records; the matching engine is responsible
    for scoring and filtering candidates.  This mirrors real provider
    behaviour where the provider returns candidates and the client scores them.
    """

    @property
    def provider_name(self) -> str:
        return PROVIDER_MOCK

    async def search(self, subject: ScreeningSubject) -> List[PepRecord]:
        """
        Returns the full mock dataset for every subject.
        The matching engine selects the best scoring record.
        """
        return list(_MOCK_PEP_DATABASE)
