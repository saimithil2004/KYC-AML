"""
Country Risk Agent — Country Collection & Validator
===================================================

Extracts, normalises, and dedupes all countries associated with the case in AgentState.
Preserves the relationship between a country and its context (e.g., transaction destination)
so that context-specific business rules (CR006, CR007) can be evaluated.
"""

from typing import Dict, Any, List, Set, Tuple, Optional
from app.agents.base.agent_state import AgentState
from app.agents.country.normalizer import normalize_country


class CountryValidator:
    """
    Sourcing and normalisation validator for Country Risk screening.
    """

    @staticmethod
    def collect_countries(state: AgentState) -> Dict[str, Set[str]]:
        """
        Scans AgentState for any countries and returns a dict mapping
        normalized country names to a set of sources where they appeared.

        Also returns unknown/failed-to-normalize country strings under the
        source name 'unknown_source' for CR008 reporting.
        """
        # Dictionary of standard source -> list of raw values
        raw_sources: Dict[str, List[Optional[str]]] = {
            "customer_nationality": [],
            "customer_residence":   [],
            "company_registration": [],
            "operating_country":    [],
            "director_nationality": [],
            "ubo_nationality":       [],
            "shareholder_nationality": [],
            "signatory_nationality": [],
            "transaction_origin":   [],
            "transaction_destination": [],
            "bank_country":         [],
        }

        # ── 1. Customer ───────────────────────────────────────────────────────
        if state.customer:
            raw_sources["customer_nationality"].append(state.customer.get("nationality"))
            raw_sources["customer_residence"].append(
                state.customer.get("country") or
                state.customer.get("registered_country") or
                state.customer.get("country_of_residence")
            )

        # ── 2. Companies ──────────────────────────────────────────────────────
        for comp in state.companies or []:
            raw_sources["company_registration"].append(comp.get("country") or comp.get("registered_country"))
            
            # Operating countries (supports list, comma-separated string, or single string)
            ops = comp.get("operating_countries")
            if isinstance(ops, list):
                raw_sources["operating_country"].extend(ops)
            elif isinstance(ops, str):
                for op in ops.split(","):
                    raw_sources["operating_country"].append(op.strip())

        # ── 3. Directors ──────────────────────────────────────────────────────
        for d in state.directors or []:
            raw_sources["director_nationality"].append(d.get("nationality") or d.get("country"))

        # ── 4. UBOs ───────────────────────────────────────────────────────────
        for u in state.ubos or []:
            raw_sources["ubo_nationality"].append(u.get("nationality") or u.get("country"))

        # ── 5. Shareholders & Signatories in Customer Profile ──────────────────
        profile = state.customer_profile or {}
        
        shareholders = profile.get("shareholders") or []
        for s in shareholders:
            raw_sources["shareholder_nationality"].append(s.get("nationality") or s.get("country"))

        signatories = profile.get("authorised_signatories") or []
        for s in signatories:
            raw_sources["signatory_nationality"].append(s.get("nationality") or s.get("country"))

        # ── 6. Transactions ───────────────────────────────────────────────────
        for tx in state.transactions or []:
            raw_sources["transaction_origin"].append(tx.get("origin_country"))
            raw_sources["transaction_destination"].append(tx.get("destination_country"))
            raw_sources["bank_country"].append(tx.get("bank_country") or tx.get("country"))

        # ─── Normalise and Group ──────────────────────────────────────────────
        normalized_results: Dict[str, Set[str]] = {}
        
        for source_name, country_list in raw_sources.items():
            for raw_country in country_list:
                if not raw_country:
                    continue
                
                normalized = normalize_country(raw_country)
                if normalized:
                    if normalized not in normalized_results:
                        normalized_results[normalized] = set()
                    normalized_results[normalized].add(source_name)
                else:
                    # Keep raw name to flag as unknown under CR008
                    unknown_key = f"UNKNOWN:{raw_country}"
                    if unknown_key not in normalized_results:
                        normalized_results[unknown_key] = set()
                    normalized_results[unknown_key].add(source_name)

        return normalized_results
