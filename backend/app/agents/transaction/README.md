# Transaction Agent — Behavioral AML Analysis Engine

Deterministic behavioral transaction monitoring engine for the UK AML/KYC Agentic AI Platform. Analyzes customer ledger flows to flag structuring, velocity anomalies, large transfers, cash-heavy behavior, circular flow patterns, account reactivation, and anomalous operating hours.

## Architecture & Modules

The Transaction Agent is implemented with modular, SOLID design principles, isolating validation, pattern detection, risk scoring, and business rules:

1. **`agent.py`**
   - Implements the `TransactionAgent` class subclassing `BaseAgent`.
   - Manages validation lifecycle, input ingestion from `AgentState`, orchestration, audit logs, and metric reporting.
2. **`constants.py`**
   - Holds deterministic thresholds (e.g. structuring thresholds between £8,000 and £9,999.99, dormant gap definitions of 90 days), rule IDs (`TX001`–`TX010`), status labels, and routing names.
3. **`models.py`**
   - Defines strict Pydantic v2 schemas: `TransactionRecord` (normalized transaction rows), `PatternResult` (per-pattern outcomes), `TransactionAnalysis` (consolidated results), and `TransactionAuditTrail`.
4. **`validator.py`**
   - Validates timestamps, ensures non-negative transaction amounts, verifies 3-character ISO currency codes, handles missing counterparty data, and filters corrupted records without breaking overall pipeline execution.
5. **`patterns.py`**
   - Implements isolated, stateless detection algorithms for 9 of the core AML patterns (e.g. Smurfing, high velocity, dormant account activation, etc.).
6. **`analyzer.py`**
   - Combines individual detections and evaluates `TX009` (Multiple Suspicious Patterns) when $\ge 3$ patterns trigger simultaneously.
7. **`risk_calculator.py`**
   - Implements a composite risk scoring deduction engine (starting at 100 and deducting points per pattern severity) and maps scores to risk tiers (LOW, MEDIUM, HIGH, CRITICAL).
8. **`rules.py`**
   - Implements the `TransactionRulesEngine` applying compliance rules `TX001`–`TX008` to generate structured findings, warnings, recommendations, and graph-ready statuses.

## AML Detection Patterns (10 Detectors)

| ID | Pattern | Detection Trigger / Threshold | Severity |
|---|---|---|---|
| **TX001** | Structuring (Smurfing) | Multiple transactions between £8,000 and £9,999.99 in a rolling 24h window | HIGH |
| **TX002** | Velocity | $\ge 10$ transactions/24h or $\ge 20$/7 days | MEDIUM |
| **TX003** | Large Value | Single transaction $\ge £50,000$ | HIGH |
| **TX004** | High-Risk Country Transfers | Counterparty originating or destination country in `high_risk` / `prohibited` list | HIGH/CRITICAL |
| **TX005** | Rapid In / Rapid Out | Outflows sum to $\ge 80\%$ of inflow on the same account within a 48h window | HIGH |
| **TX006** | Round Amount | $\ge 3$ transactions of exact multiples of £1,000 or round values (£10k, £20k, £50k, etc.) | MEDIUM |
| **TX007** | Dormant Reactivation | Transaction activity after $\ge 90$ days of dormancy | HIGH |
| **TX008** | Cash Intensive | Cash transaction count $\ge 3$ or cash volume $\ge 30\%$ of total amount | MEDIUM |
| **TX009** | Multiple Alerts | $\ge 3$ transaction patterns triggered simultaneously | CRITICAL |
| **TX010** | Time Anomaly | $\ge 3$ transactions executed between 00:00 and 05:00 local time | LOW |

## Business Rules Mapping (`rules.py`)

- **TX001**: No suspicious patterns detected $\to$ Continue (Status: `CLEAR`, score: 100).
- **TX002**: Structuring detected $\to$ High Risk (Status: `ALERT`).
- **TX003**: High transaction velocity or large value transfer $\to$ Increase Risk (Status: `WARNING`).
- **TX004**: High-risk/Prohibited country exposure $\to$ Critical Risk (Status: `CRITICAL`).
- **TX005**: Rapid in/out loop detected $\to$ Layering Alert (Status: `ALERT`).
- **TX006**: Cash intensive behavior detected $\to$ Manual Review (Status: `WARNING`).
- **TX007**: Reactivation of dormant accounts $\to$ Increase Risk (Status: `WARNING`).
- **TX008**: Multiple indicators triggered $\to$ Critical Risk (Status: `CRITICAL`).

## Execution Flow

```
AgentState.transactions
   ├── TransactionValidator (clean invalid entries, parse timestamps)
   └── TransactionAnalyzer
          ├── Run 9 pattern detectors from patterns.py
          ├── Evaluate TX009 (Multiple Patterns) if count >= 3
          └── TransactionRulesEngine (evaluate business rules TX001-TX008)
                 └── TransactionRiskCalculator (calculate score 0-100 & risk tier)
                        └── Update AgentState (risk breakdown, next_agent="account_agent")
```
