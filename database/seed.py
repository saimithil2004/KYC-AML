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

        # 2. Seed Regulations
        reg_mlr = Regulation(
            title="Money Laundering Regulations 2017 (as amended through 2024/2026)",
            authority="FCA / HM Treasury",
            upload_path="/policies/mlr2017_amended.pdf",
            uploaded_by_id=admin_user.id
        )
        reg_eccta = Regulation(
            title="Economic Crime and Corporate Transparency Act 2023 (ECCTA 2023)",
            authority="Companies House / HM Government",
            upload_path="/policies/eccta2023.pdf",
            uploaded_by_id=admin_user.id
        )
        reg_fatf = Regulation(
            title="FATF Recommendations (Latest through 2025)",
            authority="Financial Action Task Force (FATF)",
            upload_path="/policies/fatf_recommendations.pdf",
            uploaded_by_id=admin_user.id
        )
        reg_poca = Regulation(
            title="Proceeds of Crime Act 2002 (POCA 2002)",
            authority="NCA / UK Parliament",
            upload_path="/policies/poca2002.pdf",
            uploaded_by_id=admin_user.id
        )
        reg_fraud = Regulation(
            title="Fraud Act 2006",
            authority="UK Ministry of Justice",
            upload_path="/policies/fraud_act_2006.pdf",
            uploaded_by_id=admin_user.id
        )
        reg_gdpr = Regulation(
            title="UK General Data Protection Regulation (UK GDPR)",
            authority="Information Commissioner's Office (ICO)",
            upload_path="/policies/uk_gdpr.pdf",
            uploaded_by_id=admin_user.id
        )
        reg_dpa = Regulation(
            title="Data Protection Act 2018 (DPA 2018)",
            authority="Information Commissioner's Office (ICO)",
            upload_path="/policies/dpa2018.pdf",
            uploaded_by_id=admin_user.id
        )
        reg_samla = Regulation(
            title="Sanctions and Anti-Money Laundering Act 2018 (SAMLA 2018)",
            authority="OFSI / Foreign, Commonwealth & Development Office",
            upload_path="/policies/samla2018.pdf",
            uploaded_by_id=admin_user.id
        )

        db.add_all([reg_mlr, reg_eccta, reg_fatf, reg_poca, reg_fraud, reg_gdpr, reg_dpa, reg_samla])
        await db.flush()

        # 3. Seed Policy Rules
        rule_threshold = PolicyRule(
            regulation_id=reg_mlr.id,
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
            regulation_id=reg_samla.id,
            rule_name="OFSI Sanctions Match",
            rule_type="block",
            conditions={
                "metric": "sanction_status",
                "operator": "==",
                "value": "listed"
            },
            is_active=True
        )
        rule_eccta_ubo = PolicyRule(
            regulation_id=reg_eccta.id,
            rule_name="ECCTA 2023 UBO & Identity Verification Trigger",
            rule_type="threshold",
            conditions={
                "metric": "ubo_ownership_percentage",
                "operator": ">=",
                "value": 25.0,
            },
            is_active=True
        )
        
        db.add_all([rule_threshold, rule_sanctions, rule_eccta_ubo])
        
        await db.commit()
    print("Database seeding completed successfully.")

if __name__ == "__main__":
    asyncio.run(seed_data())
