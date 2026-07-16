# KYC Agent

The KYC Agent verifies whether the customer's Know Your Customer (KYC) profile is complete and compliant before any downstream AML screening begins.

It is a deterministic, rule-based agent and does NOT query LLMs or external endpoints.

---

## Scoring Weights (Total: 100)

- **Personal Information**: 20 points
  - Name: 5 points
  - DOB: 5 points
  - Gender: 5 points
  - Nationality: 5 points
- **Address Details**: 20 points
  - Street: 5 points
  - City: 5 points
  - Postcode: 5 points
  - Country: 5 points
- **Identity Documents**: 20 points
  - Passport, National ID, or Driving Licence presence: 20 points
- **Occupation**: 10 points
- **Source of Funds**: 15 points
- **Source of Wealth**: 10 points
- **Tax Residency**: 5 points

---

## Rule Identifiers

- **`KYC001`**: Missing Full Name (Critical error)
- **`KYC002`**: Missing Date of Birth (Critical error)
- **`KYC003`**: Missing Passport/ID/Licence Identity Documents (High Risk warning)
- **`KYC004`**: Missing Address Details (Medium Risk warning)
- **`KYC005`**: Missing Source of Wealth (Manual Review recommendation)
- **`KYC006`**: Missing Source of Funds (Medium Risk warning)
- **`KYC007`**: Missing Occupation
- **`KYC008`**: Missing Tax Residency
- **`KYC009`**: Missing Gender
- **`KYC010`**: Missing Nationality (Warning)

---

## Output Metrics & Statuses

- **`COMPLETE`**: KYC Score = 100, zero Warnings.
- **`INCOMPLETE`**: KYC Score >= 60.
- **`FAILED`**: KYC Score < 60.

---

## Routing Mappings
- **Business Customer**: Routes next workflow step to `company_agent`.
- **Individual Customer**: Routes next workflow step to `pep_agent`.
