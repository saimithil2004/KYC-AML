# Sanctions Agent

The **Sanctions Agent** is Agent 4 in the UK AML + KYC workflow. It screens all
individuals and companies associated with a customer against international sanctions lists
(OFAC, UK Sanctions List, UN Sanctions, EU Sanctions, etc.) to determine if any active sanctions match exists.

Deterministic — zero LLM calls. All inputs sourced from `AgentState`.

---

## Workflow Position

```
KYC Agent → Company Agent → PEP Agent → Sanctions Agent → Country Risk Agent → ...
```

`next_agent` is always `"country_risk_agent"`. The agent never invokes the
next node directly — it writes routing information to `AgentState` and the LangGraph Orchestrator handles execution.

---

## Architecture

```
sanctions/
├── constants.py   — Rule IDs (SAN001–SAN010), sanction categories, recommendations
├── models.py      — SanctionRecord, SanctionMatchResult, SanctionsAuditTrail
├── provider.py    — BaseSanctionsProvider (ABC) + MockSanctionsProvider
├── matcher.py     — Multi-signal scoring engine (Name, Passport, Reg Number overrides)
├── validator.py   — Subject extraction & normalisation (Individuals & Companies)
├── rules.py       — SAN001–SAN010 business rules engine
├── agent.py       — SanctionsAgent (inherits BaseAgent)
├── tests.py       — 14-test suite
└── README.md      — This file
```

---

## Reusable Screening Framework

This agent depends on the shared `agents/screening/` package which encapsulates the cross-cutting models and matching logic.

| Shared Component | Used For |
|---|---|
| `ScreeningSubject` | Canonical individual person record |
| `CompanyScreeningSubject` | Canonical company entity record |
| `BaseScreeningMatcher` | Core composite individual fuzzy/exact matching equations |
| Match Constants | `MATCH_CONFIRMED`, `MATCH_POSSIBLE`, etc. |

---

## Matching Engine

### Individual Matching
- **Name Similarity**: RapidFuzz `token_sort_ratio` (50%)
- **DOB Match**: Exact match (20%)
- **Nationality Match**: Exact match (15%)
- **Country Match**: Exact match (10%)
- **Passport Match Override**: Exact passport number match + Name similarity >= 70% boosts score to 100.0 (CONFIRMED_MATCH).

### Company Matching
- **Company Name Similarity**: RapidFuzz `token_sort_ratio` (55%)
- **Registration Number Match**: Exact match (30%)
- **Country Match**: Exact match (15%)
- **Registration Match Override**: Exact registration number match + Name similarity >= 70% boosts score to 100.0 (CONFIRMED_MATCH).
- **Exact Name + Country Override**: Exact name (100%) + Country match boosts score to CONFIRMED_MATCH.

---

## Business Rules

| Rule | Trigger | Action | Risk Level |
|---|---|---|---|
| `SAN001` | No match | Continue | Low |
| `SAN002` | Possible match | Manual Review | Medium |
| `SAN003` | Confirmed Individual Sanction | Critical Risk | Critical |
| `SAN004` | Confirmed Company Sanction | Critical Risk | Critical |
| `SAN005` | Terrorist Financing Match | Immediate Escalation & SAR Review | Critical |
| `SAN006` | Asset Freeze | Block / Freeze Assets | High / Critical |
| `SAN007` | Travel Ban | Flag Travel ban warning | Medium / Critical |
| `SAN008` | Multiple Matches | Trigger multiple match alert | Critical |
| `SAN009` | Passport Match | Confirmed Individual Match | Critical |
| `SAN010` | Registration Number Match | Confirmed Company Match | Critical |

---

## AgentState Updates

```python
state.shared_metadata["sanctions_status"]          # CLEAR / POSSIBLE_MATCH / CONFIRMED_SANCTION
state.shared_metadata["sanctions_score"]           # 0–100
state.shared_metadata["sanctions_risk"]            # low / medium / high / critical
state.shared_metadata["matched_subjects"]          # List[SanctionMatchResult.dict()]
state.shared_metadata["matched_companies"]         # List[SanctionMatchResult.dict()]
state.shared_metadata["sanctions_findings"]        # List[str]
state.shared_metadata["sanctions_recommendations"] # List[str]
state.shared_metadata["sanctions_audit"]           # SanctionsAuditTrail.dict()
state.shared_metadata["next_agent"]                # "country_risk_agent"
```
