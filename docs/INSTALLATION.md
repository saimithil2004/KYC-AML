# UK Compliance Platform — Local Installation Guide

This document describes setting up the AML/KYC Platform in a local development environment.

## 1. Prerequisites
Ensure you have the following installed:
- **Python 3.12+**
- **Node.js 20+**
- **Git**
- **Docker & Docker Compose** (Optional, for containerized local setups)

---

## 2. Backend Set Up

1. **Clone the Repository:**
   ```bash
   git clone https://github.com/enterprise/kyc-aml.git
   cd kyc-aml/backend
   ```

2. **Create a Virtual Environment & Activate:**
   - On Windows:
     ```powershell
     python -m venv venv
     .\venv\Scripts\Activate.ps1
     ```
   - On Linux/macOS:
     ```bash
     python -m venv venv
     source venv/bin/activate
     ```

3. **Install Python Packages:**
   ```bash
   pip install -r requirements.txt
   ```

4. **Configure Environment Variables:**
   Create a `.env` file inside the `backend/` folder:
   ```env
   ENV=development
   DATABASE_URL=sqlite+aiosqlite:///../aml_compliance_db.db
   REDIS_URL=redis://localhost:6379/0
   SECRET_KEY=VerySecretJWTKeyForTokens_ReplaceInProduction
   ENCRYPTION_KEY=StrongAESKeyForPIIEncryptionBase64String=
   ```

5. **Initialize Database and Schema:**
   The application auto-migrates and updates database tables on startup. You can run it directly:
   ```bash
   uvicorn main:app --host 0.0.0.0 --port 8000 --reload
   ```
   Or run the standalone schema checker script:
   ```bash
   python check_tables.py
   ```

---

## 3. Frontend Set Up

1. **Navigate to Frontend Directory:**
   ```bash
   cd ../frontend
   ```

2. **Install Node Packages:**
   ```bash
   npm install
   ```

3. **Configure Environment Variables:**
   Create a `.env` file inside `frontend/` folder:
   ```env
   NEXT_PUBLIC_API_URL=http://localhost:8000/api/v1
   ```

4. **Start NextJS Development Server:**
   ```bash
   npm run dev
   ```
   The site will be available at `http://localhost:3000`.

---

## 4. Run Services with Docker Compose
If you prefer running a fully containerized stack:
```bash
docker-compose up --build
```
This boots up PostgreSQL, Redis, backend FastAPI API, Celery worker/beat, and frontend Next.js app.
