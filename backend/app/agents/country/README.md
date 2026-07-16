# Country Risk Agent

The **Country Risk Agent** is Agent 5 in the UK AML + KYC workflow. It evaluates every country associated with the customer, company, directors, UBOs, shareholders, authorized signatories, operating countries, and transactions.

The goal is to determine jurisdictional AML risk and produce a standardized score (0–100) and risk tier. It evaluates countries only and does not perform individual or company name screening.

Deterministic — zero LLM calls. All inputs sourced from `AgentState`.

---

## Workflow Position

```
KYC Agent → Company Agent → PEP Agent → Sanctions Agent → Country Risk Agent → Transaction Agent → ...
```

`next_agent` is always `"transaction_agent"`. The agent never invokes the next node directly — it writes routing information to `AgentState` and the LangGraph Orchestrator handles execution.

---

## Architecture

```
country/
├── constants.py    — Rule IDs (CR001–CR008), risk tiers, default deductions
├── models.py       — CountryRiskProfile, CountryRiskAssessment, CountryAuditTrail
├── normalizer.py   — ISO Alpha-2/Alpha-3 and common name standardizer
├── provider.py     — BaseCountryRiskProvider ABC + MockCountryRiskProvider
├── risk_matrix.py  — Risk matrix lookup wrapper
├── validator.py    — Sourcing and normalization from AgentState
├── rules.py        — CR001–CR008 business rules engine
├── agent.py        — CountryRiskAgent (inherits BaseAgent)
├── tests.py        — 12-test suite
└── README.md       — This file
```

---

## Sourcing Countries

The validator extracts country references from the following sources in the case state:
1. Customer nationality & residence country
2. Company registration country & operating countries
3. Director nationalities
4. UBO nationalities
5. Shareholder nationalities
6. Signatory nationalities
7. Transaction origin, destination, and bank countries

---

## Matching & Overrides

### Country Normalization (`normalizer.py`)
Standardizes abbreviations (e.g. `UK`, `GBR`, `GB` -> `United Kingdom`, `US`, `USA` -> `United States`) to match entries in the risk database. Unknown or unrecognized country strings are preserved with an `UNKNOWN:` prefix to trigger warning rule `CR008`.

### Scoring Engine (0–100)
- Starts at `100.0`.
- Any `PROHIBITED` country reduces score to `0.0` (Risk: `CRITICAL`).
- Each `HIGH` country deducts `30.0` points (minimum score `10.0`, Risk: `HIGH`).
- Each `MEDIUM` country deducts `10.0` points (minimum score `50.0`, Risk: `MEDIUM`).
- Else: Risk is `LOW`.

---

## Business Rules

| Rule | Trigger | Action | Risk Level |
|---|---|---|---|
| `CR001` | Low Risk Country | Continue standard screening | Low |
| `CR002` | Medium Risk Country | Apply standard ongoing monitoring | Medium |
| `CR003` | High Risk Country | Increase risk score component | High |
| `CR004` | Prohibited Country | Immediately suspend and escalate | Critical |
| `CR005` | Multiple High-Risk | Trigger Manual Compliance Review | High / Critical |
| `CR006` | High-Risk Transaction Destination | Flag transaction for compliance review | High |
| `CR007` | High-Risk Company Registration Country | Flag company risk increment | High |
| `CR008` | Unknown Country | Warn analyst to correct country detail in CRM | Medium |

---

## Downstream Consumer (Transaction Agent)
The Transaction Agent will consume the country risk data directly from the state's shared metadata to adjust transaction weights or evaluate country-transaction cross-risks:
- `state.shared_metadata["high_risk_countries"]`
- `state.shared_metadata["prohibited_countries"]`
- `state.shared_metadata["country_risk"]`

---

## AgentState Updates

```python
state.shared_metadata["country_status"]          # CLEAR / WARNING / SUSPENDED
state.shared_metadata["country_score"]           # 0–100
state.shared_metadata["country_risk"]            # low / medium / high / critical
state.shared_metadata["evaluated_countries"]     # List[str] (Normalized standard countries)
state.shared_metadata["high_risk_countries"]     # List[str]
state.shared_metadata["prohibited_countries"]    # List[str]
state.shared_metadata["country_findings"]        # List[str]
state.shared_metadata["country_recommendations"] # List[str]
state.shared_metadata["country_audit"]           # CountryAuditTrail.dict()
state.shared_metadata["next_agent"]              # "transaction_agent"
```
