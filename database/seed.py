import asyncio
import sys
import os

# Adjust path to import app modules
sys.path.append(os.path.join(os.path.dirname(__file__), '..', 'backend'))

from app.core.database import Base, engine, SessionLocal
from app.core.security import get_password_hash
from app.models.models import User, Regulation, PolicyRule

async def seed_data():
    print("Starting database seeding...")
    async with engine.begin() as conn:
        # Create tables automatically for base foundation validation
        await conn.run_sync(Base.metadata.create_all)
        
    async with SessionLocal() as db:
        # 1. Seed Core Users
        admin_user = User(
            email="admin@firm.co.uk",
            password_hash=get_password_hash("AdminSecurePassword123!"),
            role="admin",
            is_active=True
        )
        officer_user = User(
            email="compliance@firm.co.uk",
            password_hash=get_password_hash("ComplianceSecurePassword123!"),
            role="compliance_officer",
            is_active=True
        )
        customer_user = User(
            email="customer@firm.co.uk",
            password_hash=get_password_hash("CustomerSecurePassword123!"),
            role="customer",
            is_active=True
        )
        
        db.add(admin_user)
        db.add(officer_user)
        db.add(customer_user)
        await db.flush()

        # 2. Seed Regulation
        regulation = Regulation(
            title="Money Laundering Regulations 2017 (MLR 2017)",
            authority="FCA",
            upload_path="/policies/mlr2017.pdf",
            uploaded_by_id=admin_user.id
        )
        db.add(regulation)
        await db.flush()

        # 3. Seed Policy Rules
        rule_threshold = PolicyRule(
            regulation_id=regulation.id,
            rule_name="Large Transaction Trigger",
            rule_type="threshold",
            conditions={
                "metric": "amount",
                "operator": ">=",
                "value": 10000.00,
                "currency": "GBP"
            },
            is_active=True
        )
        rule_sanctions = PolicyRule(
            regulation_id=regulation.id,
            rule_name="OFSI Sanctions Match",
            rule_type="block",
            conditions={
                "metric": "sanction_status",
                "operator": "==",
                "value": "listed"
            },
            is_active=True
        )
        
        db.add(rule_threshold)
        db.add(rule_sanctions)
        
        await db.commit()
    print("Database seeding completed successfully.")

if __name__ == "__main__":
    asyncio.run(seed_data())
