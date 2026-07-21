# Enterprise AML & KYC Compliance Platform (v1.0.0)

A production-grade, AI-agentic Anti-Money Laundering (AML) and Know Your Customer (KYC) compliance platform. Designed for banks and enterprise financial institutions, this system leverages autonomous multi-agent graphs, real-time transaction monitoring, continuous re-screening, compliance policy guardrails, and explainable AI governance audits.

---

## 1. Core Architectural Features

*   **Multi-Agent LangGraph Orchestrator**: Runs autonomous checking loops across specialized compliance agents.
*   **Real-Time Screening**: Fuzzy name checks, PEP checks, sanctions checks, and adverse media scraping.
*   **Continuous Monitoring**: Scheduled cron jobs check customer risk changes periodically, triggering re-screening.
*   **Explainable AI (XAI)**: Generates structured decision trees and compliance justification audits for compliance desks.
*   **AI Governance & Registry**: Tracks model parameters, version histories, and estimated token usage costs.
*   **Human-In-The-Loop Reviews**: Submits rating reviews and overrides parameters logs to keep model evaluation metrics precise.
*   **DevOps & Production Readiness**: Scalable container compose profiles, Prometheus exporters, and Kubernetes manifests.
*   **Hardened Enterprise Security**: TOTP Multi-Factor Authentication, AES-256 GCM PII encryption, password lockout policies, and comprehensive RBAC.

---

## 2. Platform Architecture

```mermaid
graph TD
    A[Next.js Admin Console] -->|API Requests| B[FastAPI Backend Gateway]
    B -->|RBAC / JWT / MFA| C[Authentication & Security]
    B -->|Trigger Screening| D[Celery Tasks Queue]
    D -->|Orchestrate Agents| E[LangGraph Orchestrator]
    E -->|Analyze Profile| F[KYC Agent]
    E -->|Fuzzy Matches| G[Sanctions & PEP Agents]
    E -->|Risk Scoring| H[Risk Scoring Agent]
    B -->|Read/Write Data| I[(PostgreSQL DB / Replica)]
    D -->|Read/Write Cache| J[(Redis Sentinel Cache)]
    B -->|Governance Audits| K[AI Governance & Registry]
    B -->|Export Metrics| L[Prometheus / Grafana]
```

---

## 3. Technology Stack

*   **Backend**: FastAPI, SQLAlchemy (PostgreSQL + SQLite support), Pydantic V2, Celery.
*   **Frontend**: Next.js (App Router), TypeScript, Tailwind CSS, Lucide Icons.
*   **Database**: PostgreSQL (with read replica support), PgVector for semantic similarities.
*   **Caching & Queue**: Redis Sentinel / Redis Cluster.
*   **AI & LLM**: Google Gemini (via Google GenAI SDK), LangGraph.
*   **Security**: PyJWT, cryptography (AES-256 GCM), PyOTP (MFA).
*   **Observability**: Prometheus metrics exporter, Loki logger streams.

---

## 4. Project Directory Structure

```
KYC-AML/
├── backend/                   # Python API Gateway & Celery Worker
│   ├── app/
│   │   ├── agents/           # Specialized LangGraph Compliance Agents
│   │   ├── api/              # API Route Controllers (v1)
│   │   ├── core/             # Configuration, Database Connection & Middleware
│   │   ├── models/           # SQLAlchemy DB Models
│   │   ├── services/         # Core business logic services
│   │   └── tasks/            # Celery Periodic & Event tasks
│   ├── tests/                # Comprehensive Pytest suites
│   └── main.py               # Application startup entry point
├── frontend/                  # Next.js App Router Project
│   ├── app/                  # Next.js Page views
│   ├── components/           # Shared React components
│   └── lib/                  # Client API functions & helpers
├── deployment/                # Production Infrastructure Configs
│   ├── kubernetes/           # K8s Ingress, StatefulSet, NetworkPolicies
│   ├── nginx/                # Reverse proxy configs
│   └── prometheus/           # Metrics scrapers
├── docker-compose.yml         # Local development stack
├── docker-compose.prod.yml    # Multi-stage production compose stack
└── README.md                  # Comprehensive Documentation
```

---

## 5. Getting Started

### Prerequisites
*   Docker & Docker Compose (v2.0+)
*   Python 3.11+
*   Node.js v18+

### Environment Configuration
Create a `.env` file at the root and backend directories:
```env
ENV=development
SECRET_KEY=VerySecretJWTKeyForTokens_ReplaceInProduction
ENCRYPTION_KEY=StrongAESKeyForPIIEncryptionBase64String=
DATABASE_URL=postgresql+asyncpg://compliance_admin:SecretSecurePassword99@postgres:5432/aml_compliance_db
REDIS_URL=redis://redis:6379/0
GEMINI_API_KEY=your_gemini_api_key_here
```

### Run Locally via Docker Compose
To boot the database, cache, backend api, and frontend client:
```bash
docker-compose up --build
```
Access points:
*   Frontend: `http://localhost:3000`
*   Backend API Swagger docs: `http://localhost:8000/docs`
*   Prometheus Exporter: `http://localhost:8000/api/v1/health/metrics`

---

## 6. Running Tests

### Backend Unit & Regression Tests
Run the entire validation suite including Phase 17 unit checks:
```bash
cd backend
python -m pytest --asyncio-mode=auto -v
```

### Frontend Build Compilation
Verify there are no Next.js build errors or static generation issues:
```bash
cd frontend
npm run build
```

---

## 7. License

Distributed under the MIT License. See `LICENSE` for more details.
