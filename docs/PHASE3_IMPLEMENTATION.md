# Phase 3 Implementation

## Folder Structure

```text
backend/
  app/
    api/v1/endpoints/
      auth.py
      customers.py
      documents.py
      kyc.py
    core/
      config.py
      database.py
      security.py
    dependencies/
      auth.py
    models/
      models.py
    schemas/
      schemas.py
    services/
      auth_service.py
      upload_service.py
  migrations/
    versions/
      20260620_0001_initial_phase3_schema.py
  alembic.ini
  main.py

frontend/
  app/
    auth/login/page.tsx
    auth/register/page.tsx
    customer/dashboard/page.tsx
    customer/profile/page.tsx
    customer/kyc/page.tsx
    customer/documents/page.tsx
  components/
    FormField.tsx
    Navbar.tsx
    ProtectedRoute.tsx
    Sidebar.tsx
  context/
    AuthContext.tsx
  lib/
    api.ts

database/
  seed.py
  seed_phase3.py
```

## Database Models

Core Phase 3 tables are implemented in `backend/app/models/models.py`:

- `users`: UUID PK, unique indexed email, password hash, role, active flag, timestamps.
- `customers`: UUID PK, FK to `users`, indexed ownership, profile fields, status, timestamps.
- `kyc_profiles`: UUID PK, unique FK to `customers`, full name, DOB, nationality, address, occupation, source of funds, source of wealth, risk category, timestamps.
- `documents`: UUID PK, indexed FK to `customers`, document type, file metadata, local path, JSONB OCR/verification metadata, timestamps.

## Alembic Setup

Initial migration:

```bash
cd backend
alembic upgrade head
```

Generate future migrations:

```bash
cd backend
alembic revision --autogenerate -m "describe_change"
alembic upgrade head
```

Database initialization:

```bash
docker compose up -d postgres redis
docker compose run --rm backend_api alembic upgrade head
docker compose run --rm backend_api python ../database/seed.py
docker compose run --rm backend_api python ../database/seed_phase3.py
docker compose up backend_api celery_worker celery_beat frontend
```

## Authentication Code Structure

- Routes: `POST /api/v1/auth/register`, `POST /api/v1/auth/login`, `POST /api/v1/auth/refresh`, `GET /api/v1/auth/me`
- Password hashing: `backend/app/core/security.py`
- JWT creation and verification: `backend/app/core/security.py`, `backend/app/dependencies/auth.py`
- RBAC roles: `customer`, `compliance_officer`, `admin`
- RBAC dependencies: `verify_admin`, `verify_compliance_officer`, `verify_any_user`

## API Design

Customers:

- `POST /api/v1/customers/`
- `GET /api/v1/customers/me`
- `GET /api/v1/customers/{id}`
- `PUT /api/v1/customers/{id}`
- `DELETE /api/v1/customers/{id}`

KYC:

- `POST /api/v1/kyc/`
- `GET /api/v1/kyc/{customer_id}`
- `PUT /api/v1/kyc/{customer_id}`

Documents:

- `POST /api/v1/documents/upload`
- Supported content: PDF, PNG, JPEG
- Local storage: `settings.UPLOAD_DIR`
- Metadata persisted in `documents`

## Frontend Design

- Login page: token-based sign-in.
- Register page: account creation with role selection.
- Customer dashboard: onboarding status, KYC risk, next actions.
- Profile page: customer details CRUD.
- KYC form page: submit/update KYC profile.
- Document upload page: upload verification files.
- Components: navbar, sidebar, protected route, reusable form fields.

## Integration Flow

1. User registers through `POST /auth/register`.
2. User logs in through `POST /auth/login`.
3. Frontend stores access token and user profile in local storage.
4. Protected portal loads or creates `/customers/me`.
5. KYC form submits `POST /kyc/` or updates `PUT /kyc/{customer_id}`.
6. Document page uploads multipart files to `/documents/upload`.
7. Backend stores document metadata in Postgres and file binaries locally.

## Seed Data

Run:

```bash
python database/seed.py
python database/seed_phase3.py
```

Phase 3 seed creates:

- 10 customer users
- 10 customer records
- 10 KYC profiles
- 20 document metadata records

## Week Execution Plan

Day 1:
- Finalize SQLAlchemy models.
- Validate relationships and indexes.
- Lock schema naming.

Day 2:
- Apply Alembic initial migration.
- Verify table creation in PostgreSQL.
- Run base seed script.

Day 3:
- Validate register/login/refresh/me APIs.
- Test JWT verification and RBAC dependencies.
- Confirm password hashing.

Day 4:
- Validate customer CRUD APIs.
- Test profile ownership and officer/admin access.
- Connect profile page.

Day 5:
- Validate KYC create/read/update APIs.
- Connect KYC form.
- Confirm customer profile sync fields.

Day 6:
- Validate document upload.
- Confirm local file persistence and metadata records.
- Connect upload page.

Day 7:
- Run end-to-end flow: register, login, profile, KYC, upload.
- Seed 10 customers, 10 KYC profiles, 20 documents.
- Capture defects and prepare Phase 4 backlog.
