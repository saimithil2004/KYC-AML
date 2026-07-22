from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from uuid import UUID
from app.core.database import get_db
from app.dependencies.auth import get_current_user
from app.models.models import User, Customer, KYCProfile
from app.schemas.schemas import KYCProfileCreate, KYCProfileResponse, KYCProfileUpdate
from app.core.celery_app import celery_app

router = APIRouter()


@router.post(
    "/", response_model=KYCProfileResponse, status_code=status.HTTP_201_CREATED
)
async def submit_kyc(
    kyc_in: KYCProfileCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(Customer).where(Customer.id == kyc_in.customer_id))
    customer = result.scalars().first()
    if not customer:
        raise HTTPException(status_code=404, detail="Customer not found")

    if customer.user_id != current_user.id and current_user.role not in [
        "compliance_officer",
        "admin",
    ]:
        raise HTTPException(
            status_code=403, detail="Not authorized to edit this profile."
        )

    # Update Customer core details
    names = kyc_in.full_name.split(" ", 1)
    customer.first_name = names[0]
    customer.last_name = names[1] if len(names) > 1 else ""
    customer.dob = kyc_in.dob
    customer.nationality = kyc_in.nationality
    customer.street_address = kyc_in.address
    customer.status = "pending_verification"

    res_existing = await db.execute(
        select(KYCProfile).where(KYCProfile.customer_id == customer.id)
    )
    existing = res_existing.scalars().first()
    if existing:
        raise HTTPException(
            status_code=409,
            detail="KYC profile already exists for this customer. Use PUT to update it.",
        )

    kyc_profile = KYCProfile(
        customer_id=customer.id,
        full_name=kyc_in.full_name,
        date_of_birth=kyc_in.dob,
        nationality=kyc_in.nationality,
        tax_residency=kyc_in.tax_residency,
        address=kyc_in.address,
        source_of_funds=kyc_in.source_of_funds,
        source_of_wealth=kyc_in.source_of_wealth,
        occupation=kyc_in.occupation,
        annual_income_range=kyc_in.annual_income_range,
        expected_activity_desc=kyc_in.expected_activity_desc,
        risk_category=kyc_in.risk_category or "low",
    )
    db.add(kyc_profile)
    await db.commit()
    await db.refresh(kyc_profile)

    # Trigger background pipeline
    celery_app.send_task(
        "tasks.kyc_tasks.run_aml_kyc_pipeline", args=[str(customer.id)]
    )

    response_data = KYCProfileResponse(
        id=kyc_profile.id,
        customer_id=kyc_profile.customer_id,
        full_name=kyc_in.full_name,
        dob=kyc_in.dob,
        nationality=kyc_in.nationality,
        tax_residency=kyc_profile.tax_residency,
        address=kyc_in.address,
        occupation=kyc_profile.occupation,
        source_of_funds=kyc_profile.source_of_funds,
        source_of_wealth=kyc_profile.source_of_wealth,
        annual_income_range=kyc_profile.annual_income_range,
        risk_category=kyc_profile.risk_category,
        expected_activity_desc=kyc_profile.expected_activity_desc,
        created_at=kyc_profile.created_at,
        updated_at=kyc_profile.updated_at,
    )
    return response_data


@router.get("/{customer_id}", response_model=KYCProfileResponse)
async def get_kyc(
    customer_id: UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(Customer).where(Customer.id == customer_id))
    customer = result.scalars().first()
    if not customer:
        raise HTTPException(status_code=404, detail="Customer not found")

    if customer.user_id != current_user.id and current_user.role not in [
        "compliance_officer",
        "admin",
    ]:
        raise HTTPException(
            status_code=403, detail="Not authorized to access this KYC profile."
        )

    res_kyc = await db.execute(
        select(KYCProfile).where(KYCProfile.customer_id == customer_id)
    )
    kyc = res_kyc.scalars().first()
    if not kyc:
        raise HTTPException(
            status_code=404, detail="KYC profile declarations not found."
        )

    return KYCProfileResponse(
        id=kyc.id,
        customer_id=kyc.customer_id,
        full_name=kyc.full_name,
        dob=kyc.date_of_birth,
        nationality=kyc.nationality,
        address=kyc.address,
        occupation=kyc.occupation,
        source_of_funds=kyc.source_of_funds,
        source_of_wealth=kyc.source_of_wealth,
        risk_category=kyc.risk_category,
        created_at=kyc.created_at,
        updated_at=kyc.updated_at,
    )


@router.put("/{customer_id}", response_model=KYCProfileResponse)
async def update_kyc(
    customer_id: UUID,
    kyc_in: KYCProfileUpdate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(Customer).where(Customer.id == customer_id))
    customer = result.scalars().first()
    if not customer:
        raise HTTPException(status_code=404, detail="Customer not found")

    if customer.user_id != current_user.id and current_user.role not in [
        "compliance_officer",
        "admin",
    ]:
        raise HTTPException(
            status_code=403, detail="Not authorized to edit this profile."
        )

    res_kyc = await db.execute(
        select(KYCProfile).where(KYCProfile.customer_id == customer_id)
    )
    kyc = res_kyc.scalars().first()
    if not kyc:
        raise HTTPException(status_code=404, detail="KYC profile not found.")

    changed = False

    if kyc_in.full_name is not None and kyc_in.full_name != kyc.full_name:
        names = kyc_in.full_name.split(" ", 1)
        customer.first_name = names[0]
        customer.last_name = names[1] if len(names) > 1 else ""
        kyc.full_name = kyc_in.full_name
        changed = True
    if kyc_in.dob is not None and kyc_in.dob != kyc.date_of_birth:
        customer.dob = kyc_in.dob
        kyc.date_of_birth = kyc_in.dob
        changed = True
    if kyc_in.nationality is not None and kyc_in.nationality != kyc.nationality:
        customer.nationality = kyc_in.nationality
        kyc.nationality = kyc_in.nationality
        changed = True
    if kyc_in.tax_residency is not None and kyc_in.tax_residency != kyc.tax_residency:
        kyc.tax_residency = kyc_in.tax_residency
        changed = True
    if kyc_in.address is not None and kyc_in.address != kyc.address:
        customer.street_address = kyc_in.address
        kyc.address = kyc_in.address
        changed = True
    if (
        kyc_in.source_of_funds is not None
        and kyc_in.source_of_funds != kyc.source_of_funds
    ):
        kyc.source_of_funds = kyc_in.source_of_funds
        changed = True
    if (
        kyc_in.source_of_wealth is not None
        and kyc_in.source_of_wealth != kyc.source_of_wealth
    ):
        kyc.source_of_wealth = kyc_in.source_of_wealth
        changed = True
    if kyc_in.occupation is not None and kyc_in.occupation != kyc.occupation:
        kyc.occupation = kyc_in.occupation
        changed = True
    if (
        kyc_in.annual_income_range is not None
        and kyc_in.annual_income_range != kyc.annual_income_range
    ):
        kyc.annual_income_range = kyc_in.annual_income_range
        changed = True
    if (
        kyc_in.expected_activity_desc is not None
        and kyc_in.expected_activity_desc != kyc.expected_activity_desc
    ):
        kyc.expected_activity_desc = kyc_in.expected_activity_desc
        changed = True
    if kyc_in.risk_category is not None and kyc_in.risk_category != kyc.risk_category:
        kyc.risk_category = kyc_in.risk_category
        changed = True

    if changed:
        customer.status = "pending_verification"

    await db.commit()
    await db.refresh(kyc)

    if changed:
        celery_app.send_task(
            "tasks.kyc_tasks.run_aml_kyc_pipeline", args=[str(customer.id)]
        )

    return KYCProfileResponse(
        id=kyc.id,
        customer_id=kyc.customer_id,
        full_name=kyc.full_name,
        dob=kyc.date_of_birth,
        nationality=kyc.nationality,
        tax_residency=kyc.tax_residency,
        address=kyc.address,
        occupation=kyc.occupation,
        source_of_funds=kyc.source_of_funds,
        source_of_wealth=kyc.source_of_wealth,
        annual_income_range=kyc.annual_income_range,
        risk_category=kyc.risk_category,
        expected_activity_desc=kyc.expected_activity_desc,
        created_at=kyc.created_at,
        updated_at=kyc.updated_at,
    )
