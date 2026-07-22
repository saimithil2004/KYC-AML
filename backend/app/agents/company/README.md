# Company Agent

The **Company Agent** performs deterministic, rule-based verification of business
entity profiles as part of the UK AML + KYC workflow pipeline.

It is the **second** agent to execute after the KYC Agent and is LangGraph-aware.

---

## Routing Logic

| `customer_type` | Behaviour | `company_agent_executed` | `next_agent` |
|---|---|---|---|
| `individual` | **SKIP** — no checks run | `false` | `pep_agent` |
| `business` | **Full verification** | `true` | `pep_agent` |

Skipping an Individual customer is **not an error** — the agent returns
`success=True` with `company_status=SKIPPED`.

---

## AgentRoutingInfo (LangGraph-Compatible)

Every execution (skip or full) writes a structured routing object into
`AgentState.shared_metadata["company_agent_routing"]`:

```json
{
  "customer_type": "BUSINESS",
  "current_agent": "company_agent",
  "next_agent": "pep_agent",
  "company_agent_executed": true,
  "skip_reason": null
}
```

The **Orchestrator** reads this object to determine which LangGraph node executes
next. The Company Agent never calls the next agent directly.

---

## Verification Dimensions & Scoring Weights (Total: 100)

| Dimension | Rule ID | Score |
|---|---|---|
| Company Registration Number + Incorporation Date | `CO001` | 20 |
| Company Status (Active/Registered/Trading) | `CO002` / `CO003` | 15 |
| Registered Address (all 4 sub-fields) | `CO004` | 15 |
| Industry / SIC Code | `CO005` | 10 |
| Directors (≥1 verified) | `CO006` | 15 |
| Shareholders (≥1 declared) | `CO007` | 10 |
| UBOs ≥25% ownership (MLR 2017 as amended / ECCTA 2023) | `CO008` | 10 |
| Company Incorporation Documents | `CO009` | 5 |

---

## Statutory Compliance Framework & UBO Guidance

The **Company Agent** enforces corporate transparency requirements governed by:
- **Money Laundering Regulations 2017 (as amended through 2024/2026)**: Mandates disclosure and verification of all Ultimate Beneficial Owners (UBOs) holding ≥ 25% ownership or control.
- **Economic Crime and Corporate Transparency Act 2023 (ECCTA 2023)**: Mandates **Beneficial Ownership verification**, mandatory **PSC (Persons with Significant Control) verification**, and identity proofing for company directors and key controllers.
- **Identity Verification & EDD (Enhanced Due Diligence)**: When qualifying UBO or director declarations are missing or discrepant (`CO006` or `CO008`), the system triggers high-risk routing and requires mandatory Enhanced Due Diligence (EDD) before onboarding approval.

---

## Rule Identifiers

| ID | Trigger | Risk Impact |
|---|---|---|
| `CO001` | Missing registration number | HIGH |
| `CO002` | Missing company status field | MEDIUM |
| `CO003` | Invalid / missing status value | – |
| `CO004` | Incomplete registered address | MEDIUM |
| `CO005` | Missing industry classification | – |
| `CO006` | No verified directors | HIGH |
| `CO007` | No shareholders declared | MEDIUM |
| `CO008` | No UBOs with ≥25% ownership (MLR 2017 / ECCTA 2023) | HIGH → EDD |
| `CO009` | No incorporation documents | Recommendation |
| `CO010` | Dissolved / struck-off status | HIGH |

---

## Company Status Output

| Score | Warnings | Status |
|---|---|---|
| 100 | 0 | `COMPLETE` |
| ≥ 60 | any | `INCOMPLETE` |
| < 60 | any | `FAILED` |
| (individual) | — | `SKIPPED` |

---

## Data Sources

All input data is read **exclusively** from `AgentState`:

- `state.customer` → customer type, basic info
- `state.companies[0]` → company registration fields
- `state.directors` → director list
- `state.customer_profile["shareholders"]` → shareholder list
- `state.ubos` → beneficial owner list
- `state.uploaded_documents` → company documents

No database queries. No external API calls. No LLM.
