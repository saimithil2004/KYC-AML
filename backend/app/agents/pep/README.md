# PEP Agent

The **PEP Agent** is Agent 3 in the UK AML + KYC workflow.  It screens all
persons associated with a customer against Politically Exposed Person (PEP)
datasets and determines whether Enhanced Due Diligence (EDD) is required.

Deterministic — zero LLM calls. All data sourced from `AgentState`.

---

## Workflow Position

```
KYC Agent → Company Agent → PEP Agent → Sanctions Agent → ...
```

`next_agent` is always `"sanctions_agent"`. The agent never invokes the
next node directly — it writes routing information to `AgentState` and
the LangGraph Orchestrator handles execution.

---

## Architecture

```
pep/
├── constants.py   — Rule IDs, PEP categories, thresholds, signal weights
├── models.py      — ScreeningSubject, PepRecord, PepMatchResult, PepAuditTrail
├── provider.py    — BasePepProvider (ABC) + MockPepProvider
├── matcher.py     — Multi-signal scoring engine (RapidFuzz + exact signals)
├── validator.py   — Subject extraction from AgentState (reusable)
├── rules.py       — PEP001–PEP007 business rules engine
├── agent.py       — PepAgent (inherits BaseAgent)
├── tests.py       — 17-test suite
└── README.md      — This file
```

---

## ScreeningSubject — Reusability Contract

`ScreeningSubject` and `PepValidator.build_subjects()` are the **single source
of truth** for extracting persons from `AgentState`.

Future agents reuse them without duplicating logic:

```python
# Sanctions Agent
from app.agents.pep.validator import PepValidator
subjects = PepValidator.build_subjects(state)   # same subjects, no re-extraction
```

| Agent | Purpose |
|---|---|
| **PEP Agent** | PEP dataset matching |
| **Sanctions Agent** | OFAC / HMT / UN sanctions lookup (future) |
| **Country Risk Agent** | Nationality / country risk scoring (future) |

---

## Provider Architecture

```
BasePepProvider (ABC)
    └── MockPepProvider          ← dev / testing
    └── OpenSanctionsProvider    ← future
    └── WorldCheckProvider       ← future
    └── DowJonesProvider         ← future
```

Providers are injected at agent construction:

```python
agent = PepAgent(provider=MockPepProvider())           # default
agent = PepAgent(provider=OpenSanctionsProvider(...))  # production
```

The PEP Agent is coded against the `BasePepProvider` interface. Swapping
providers requires **zero changes** to agent, matcher, or rules code.

---

## Matching Engine

| Signal | Method | Weight |
|---|---|---|
| Full name | RapidFuzz `token_sort_ratio` | 50% |
| Date of Birth | Exact string match | 20% |
| Nationality | Exact match (case-insensitive) | 15% |
| Country | Exact match (case-insensitive) | 10% |
| Role keyword | Position keyword presence | 5% |

**CONFIRMED override**: exact name (100%) + DOB or nationality match → forces
`CONFIRMED` regardless of total composite score (handles missing country).

**Anti-false-positive guard**: name similarity < 85% → never `CONFIRMED`.

**No-secondary-signal guard**: name only high score → capped at `POSSIBLE`.

### Score thresholds

| Score | Confidence |
|---|---|
| `name == 100% AND (DOB OR nationality match)` | `CONFIRMED_MATCH` |
| ≥ 75 (otherwise) | `POSSIBLE_MATCH` |
| < 75 | `NO_MATCH` |

---

## Business Rules

| Rule | Trigger | Action |
|---|---|---|
| `PEP001` | No match for subject | Continue, no action |
| `PEP002` | Possible match (75–94%) | Manual Review |
| `PEP003` | Confirmed PEP | Enhanced Due Diligence (EDD) |
| `PEP004` | Foreign PEP | Increase risk to HIGH |
| `PEP005` | Family member / close associate | Increase risk to HIGH |
| `PEP006` | Current office holder | CRITICAL risk |
| `PEP007` | Former PEP | MEDIUM risk, enhanced monitoring |

---

## PEP Status

| Condition | `pep_status` |
|---|---|
| All NO_MATCH | `CLEAR` |
| Any POSSIBLE_MATCH | `POSSIBLE_MATCH` |
| Any CONFIRMED_MATCH | `CONFIRMED_PEP` |

---

## PEP Score (0–100)

| Status | Risk | Score |
|---|---|---|
| CLEAR | low | 100 |
| POSSIBLE_MATCH | medium | 60 |
| CONFIRMED_PEP | high | 10 |
| CONFIRMED_PEP | critical | 0 |

---

## AgentState Updates

```python
state.shared_metadata["pep_status"]              # CLEAR / POSSIBLE_MATCH / CONFIRMED_PEP
state.shared_metadata["pep_score"]               # 0–100
state.shared_metadata["pep_risk"]                # low / medium / high / critical
state.shared_metadata["screened_subjects"]       # List[ScreeningSubject.dict()]
state.shared_metadata["matched_subjects"]        # List[PepMatchResult.dict()]
state.shared_metadata["pep_findings"]            # List[str]
state.shared_metadata["pep_recommendations"]     # List[str]
state.shared_metadata["pep_audit_trail"]         # PepAuditTrail.dict()
state.shared_metadata["next_agent"]              # "sanctions_agent"
state.shared_metadata["edd_required"]            # bool
state.shared_metadata["manual_review_required"]  # bool
```
