# UK Compliance AML & KYC Agentic Platform - Phase 2 Setup

This repository contains the complete production-grade foundation setup for the **Agentic AML + KYC Compliance Platform** designed for UK financial institutions.

---

## 1. Project Directory Structure

```
c:/Users/saimi/Desktop/KYC AML/
├── docker-compose.yml
├── README.md
├── backend/
│   ├── Dockerfile
│   ├── requirements.txt
│   ├── main.py
│   └── app/
│       ├── __init__.py
│       ├── api/
│       │   ├── __init__.py
│       │   └── v1/
│       │       ├── __init__.py
│       │       ├── api.py
│       │       └── endpoints/
│       │           ├── __init__.py
│       │           ├── auth.py
│       │           ├── customers.py
│       │           ├── documents.py
│       │           └── kyc.py
│       ├── core/
│       │   ├── __init__.py
│       │   ├── config.py
│       │   ├── database.py
│       │   ├── security.py
│       │   └── celery_app.py
│       ├── dependencies/
│       │   ├── __init__.py
│       │   └── auth.py
│       ├── models/
│       │   ├── __init__.py
│       │   └── models.py
│       ├── schemas/
│       │   ├── __init__.py
│       │   └── schemas.py
│       └── tasks/
│           ├── __init__.py
│           ├── kyc_tasks.py
│           └── schedule_tasks.py
├── frontend/
│   ├── Dockerfile
│   ├── package.json
│   └── app/
│       ├── layout.tsx
│       ├── globals.css
│       ├── page.tsx
│       ├── auth/
│       │   ├── login/
│       │   │   └── page.tsx
│       │   └── register/
│       │       └── page.tsx
│       └── customer/
│           ├── dashboard/
│           │   └── page.tsx
│           └── profile/
│               └── page.tsx
├── database/
│   └── seed.py
└── docs/
```

---

## 2. Technical Stack Setup

### Backend (FastAPI + SQLAlchemy)
- Root entry point is located in [main.py](file:///c:/Users/saimi/Desktop/KYC%20AML/backend/main.py) routing traffic through dynamic schemas.
- Database tables (17 core relational entities) are mapped via [models.py](file:///c:/Users/saimi/Desktop/KYC%20AML/backend/app/models/models.py).
- Authentication, session validation, and Role-Based Access Control filters are implemented in [auth.py](file:///c:/Users/saimi/Desktop/KYC%20AML/backend/app/dependencies/auth.py).

### Background Task Queue (Redis + Celery)
- Celery Task client is registered in [celery_app.py](file:///c:/Users/saimi/Desktop/KYC%20AML/backend/app/core/celery_app.py).
- Real-time screening pipeline operations (fuzzy PEP scans, sanctions match checks, document OCR loops) are defined in [kyc_tasks.py](file:///c:/Users/saimi/Desktop/KYC%20AML/backend/app/tasks/kyc_tasks.py).
- Periodic verification sweeps (scheduling reviews based on risk profiles) are defined in [schedule_tasks.py](file:///c:/Users/saimi/Desktop/KYC%20AML/backend/app/tasks/schedule_tasks.py).

---

## 3. Git Branching Strategy & PR Workflows

We use a modified Git Flow strategy:

### Branch Structure
- `main`: Production-ready release branch. Directly mapped to VPS deployment.
- `develop`: Primary integration branch. All feature branches merge here first.
- `frontend-dev`: Development track for UI team.
- `backend-dev`: Development track for Core API/DB team.
- `agent-dev`: Development track for LangGraph Agent systems.

### PR and Review Guidelines
1.  **Creation:** Developer branches off target subsystem track (e.g. `feat/ocr-handling` branch off `backend-dev`).
2.  **Verification:** Automated CI checks must pass (Linting, base unit testing).
3.  **Review:** Minimum of one approved code review from the respective subsystem lead developer is mandatory.
4.  **Merge:** Squash and merge into the target integration branch (`backend-dev`, `frontend-dev`, or `agent-dev`).

---

## 4. Weekly Developer Responsibilities (Week 1 Setup)

### Developer 1: Backend Foundation & Infrastructure
*   Configure Alembic migrations environment.
*   Deploy database models to local Postgres instance and test migrations.
*   Implement JWT verification middleware and configure RBAC authorization handlers.
*   Set up FastAPI Swagger documentation endpoints.

### Developer 2: Agent Design & Risk Engine
*   Construct LangGraph schema loops (orchestrator state definition).
*   Mock out individual agents (PEP, Sanctions, Country checks).
*   Define the mathematical weights structure for Risk Engine calculations.

### Developer 3: Frontend Foundation Setup
*   Initialize Next.js 15 App router structure.
*   Scaffold layouts, navigation sidebars, and onboarding routes.
*   Implement state controls on Registration and Login forms.

---

## 5. Day-by-Day Implementation Roadmap (Week 1)

*   **Day 1: Bootstrap Environments**
    - Setup Docker container files. Spin up PostgreSQL & Redis instances locally.
    - Confirm local API compiles.
*   **Day 2: Database Schema Validation**
    - Run Alembic initialization. Apply database migrations to build tables.
    - Run data seed scripts to verify keys.
*   **Day 3: Authentication and Session Locks**
    - Deploy registration/login endpoints. Validate password hashing and cookie storage.
*   **Day 4: Next.js Layouts & UI Forms**
    - Scaffold Next.js client forms. Wire registration submit requests to backend auth routes.
*   **Day 5: Background Task Orchestration**
    - Configure Celery workers. Run mock OCR and screening pipeline operations via queue tasks.
*   **Day 6: LangGraph Loop Prototyping**
    - Define main graph paths. Run mock sequence execution.
*   **Day 7: System Integration Verification**
    - End-to-end user registration, document upload, and status evaluation checks.
