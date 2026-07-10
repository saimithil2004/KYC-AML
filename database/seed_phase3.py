import asyncio
import sys
import os
from datetime import date

# Adjust path to import app modules
sys.path.append(os.path.join(os.path.dirname(__file__), '..', 'backend'))

from app.core.database import SessionLocal
from app.core.security import get_password_hash
from app.models.models import User, Customer, KYCProfile, Document

async def seed_phase3():
    print("Seeding Phase 3 test dataset...")
    
    async with SessionLocal() as db:
        # Create 10 dummy users, customers, KYC profiles, and documents
        first_names = ["Alice", "Bob", "Charlie", "David", "Emma", "Frank", "Grace", "Henry", "Isabella", "Jack"]
        last_names = ["Smith", "Jones", "Brown", "Taylor", "Miller", "Wilson", "Davies", "Evans", "Thomas", "Roberts"]
        countries = ["United Kingdom", "France", "Germany", "Spain", "Italy", "United Kingdom", "United Kingdom", "Canada", "Australia", "United Kingdom"]
        occupations = ["Engineer", "Teacher", "Physician", "Artist", "Manager", "Consultant", "Director", "Architect", "Designer", "Accountant"]
        funds_sources = ["Salary", "Savings", "Dividends", "Inheritance", "Salary", "Savings", "Salary", "Inheritance", "Salary", "Dividends"]

        for i in range(10):
            email = f"user{i+1}@example.com"
            user = User(
                email=email,
                password_hash=get_password_hash("TestPassword123!"),
                role="customer",
                is_active=True
            )
            db.add(user)
            await db.flush()

            customer = Customer(
                user_id=user.id,
                customer_type="individual",
                first_name=first_names[i],
                last_name=last_names[i],
                dob=date(1980 + i, 1 + i, 10 + i),
                nationality=countries[i],
                phone_number=f"+44770090000{i}",
                street_address=f"{100 + i} High Street",
                city="London",
                postal_code="SW1A 1AA",
                country=countries[i],
                status="approved" if i % 2 == 0 else "pending_verification"
            )
            db.add(customer)
            await db.flush()

            kyc = KYCProfile(
                customer_id=customer.id,
                full_name=f"{first_names[i]} {last_names[i]}",
                date_of_birth=date(1980 + i, 1 + i, 10 + i),
                nationality=countries[i],
                address=f"{100 + i} High Street, London",
                source_of_funds=funds_sources[i],
                source_of_wealth="Employment income accumulated over 10 years",
                occupation=occupations[i],
                risk_category="low" if i % 2 == 0 else "medium"
            )
            db.add(kyc)
            await db.flush()

            # Seed 2 documents per customer
            doc1 = Document(
                customer_id=customer.id,
                document_type="passport",
                file_name=f"{first_names[i].lower()}_passport.pdf",
                file_path=f"/app/shared_docs/{customer.id}_passport.pdf",
                content_type="application/pdf",
                file_size=128000,
                verification_status="verified"
            )
            doc2 = Document(
                customer_id=customer.id,
                document_type="utility_bill",
                file_name=f"{first_names[i].lower()}_utility_bill.png",
                file_path=f"/app/shared_docs/{customer.id}_utility_bill.png",
                content_type="image/png",
                file_size=64000,
                verification_status="verified"
            )
            db.add(doc1)
            db.add(doc2)
            
        await db.commit()
    print("Phase 3 seeding successfully finalized.")

if __name__ == "__main__":
    asyncio.run(seed_phase3())
