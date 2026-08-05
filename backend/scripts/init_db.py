import asyncio
import sys
import os
import uuid
from datetime import datetime, date

_BACKEND = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if _BACKEND not in sys.path:
    sys.path.insert(0, _BACKEND)

from app.core.database import Base, engine, SessionLocal
from app.core.security import get_password_hash
from app.models.models import (
    User, Customer, KYCProfile, RiskScore, Alert, Case, Regulation, PolicyRule
)
from app.core.schema_helpers import (
    ensure_phase10_schema, ensure_phase11_schema, ensure_phase12_schema,
    ensure_phase13_schema, ensure_phase14_schema, ensure_phase15_schema,
    ensure_phase17_schema
)

async def init_and_seed_db():
    print("Initializing database tables...")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    async with SessionLocal() as db:
        print("Ensuring dynamic phase schemas...")
        await ensure_phase10_schema(db)
        await ensure_phase11_schema(db)
        await ensure_phase12_schema(db)
        await ensure_phase13_schema(db)
        await ensure_phase14_schema(db)
        await ensure_phase15_schema(db)
        await ensure_phase17_schema(db)

        # 1. Seed Core Users if missing
        from sqlalchemy import select
        res = await db.execute(select(User).where(User.email == "admin@firm.co.uk"))
        admin_user = res.scalar_one_or_none()
        if not admin_user:
            admin_user = User(
                email="admin@firm.co.uk",
                password_hash=get_password_hash("AdminSecurePassword123!"),
                role="admin",
                is_active=True
            )
            db.add(admin_user)

        res = await db.execute(select(User).where(User.email == "compliance@firm.co.uk"))
        officer_user = res.scalar_one_or_none()
        if not officer_user:
            officer_user = User(
                email="compliance@firm.co.uk",
                password_hash=get_password_hash("ComplianceSecurePassword123!"),
                role="compliance_officer",
                is_active=True
            )
            db.add(officer_user)

        await db.flush()

        # 2. Seed Sample Customers & Risk Scores & Alerts if missing
        res = await db.execute(select(Customer))
        existing_customers = res.scalars().all()
        
        if not existing_customers or len(existing_customers) < 3:
            cust_high = Customer(
                customer_type="individual",
                first_name="Alexander",
                last_name="Vance",
                dob=date(1985, 4, 12),
                nationality="British",
                country="United Kingdom",
                status="active"
            )
            cust_med = Customer(
                customer_type="individual",
                first_name="Elena",
                last_name="Rostova",
                dob=date(1990, 8, 22),
                nationality="Cyprus",
                country="Cyprus",
                status="active"
            )
            cust_low = Customer(
                customer_type="individual",
                first_name="Sarah",
                last_name="Jenkins",
                dob=date(1992, 11, 5),
                nationality="British",
                country="United Kingdom",
                status="active"
            )
            db.add_all([cust_high, cust_med, cust_low])
            await db.flush()

            # Add Risk Scores
            rs_high = RiskScore(
                customer_id=cust_high.id,
                overall_score=92.5,
                risk_tier="high",
                breakdown={"pep_match": 80, "jurisdiction": 95, "transaction_pattern": 90}
            )
            rs_med = RiskScore(
                customer_id=cust_med.id,
                overall_score=65.0,
                risk_tier="medium",
                breakdown={"pep_match": 0, "jurisdiction": 70, "transaction_pattern": 60}
            )
            rs_low = RiskScore(
                customer_id=cust_low.id,
                overall_score=15.0,
                risk_tier="low",
                breakdown={"pep_match": 0, "jurisdiction": 10, "transaction_pattern": 20}
            )
            db.add_all([rs_high, rs_med, rs_low])

            # Add Alerts
            alert1 = Alert(
                customer_id=cust_high.id,
                alert_type="PEP Match & High Risk Country",
                risk_score=95.0,
                status="open",
                alert_metadata={"source": "automated_screening", "pep_tier": 1}
            )
            alert2 = Alert(
                customer_id=cust_high.id,
                alert_type="Structuring / Rapid Movement of Funds",
                risk_score=90.0,
                status="open",
                alert_metadata={"amount": 45000.0, "currency": "GBP"}
            )
            alert3 = Alert(
                customer_id=cust_med.id,
                alert_type="Large Single Deposit",
                risk_score=65.0,
                status="in_review",
                alert_metadata={"amount": 15000.0, "currency": "EUR"}
            )
            db.add_all([alert1, alert2, alert3])

            # Add Cases
            case1 = Case(
                customer_id=cust_high.id,
                assigned_to=officer_user.id if officer_user else None,
                priority="high",
                status="open",
                investigation_notes="Automated alert triggered PEP level 1 review.",
                sar_filed=False
            )
            db.add(case1)

            await db.flush()

        # 3. Seed Regulations if missing
        res = await db.execute(select(Regulation))
        if not res.scalars().first():
            reg_mlr = Regulation(
                title="Money Laundering Regulations 2017 (as amended 2024)",
                authority="FCA / HM Treasury",
                upload_path="/policies/mlr2017.pdf",
                uploaded_by_id=admin_user.id if admin_user else None
            )
            db.add(reg_mlr)
            await db.flush()

            rule = PolicyRule(
                regulation_id=reg_mlr.id,
                rule_name="High Value Transaction Threshold",
                rule_type="threshold",
                conditions={"metric": "amount", "operator": ">=", "value": 10000.0, "currency": "GBP"},
                is_active=True
            )
            db.add(rule)

        await db.commit()
        print("Database initialization and seeding completed successfully.")

if __name__ == "__main__":
    asyncio.run(init_and_seed_db())
