from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from uuid import UUID
from app.core.database import get_db
from app.dependencies.auth import get_current_user, verify_compliance_officer
from app.models.models import User, Customer, Company, Director, UBO
from app.schemas.schemas import CustomerCreate, CustomerResponse, CustomerUpdate

router = APIRouter()

@router.get("/", response_model=list[CustomerResponse])
async def list_customers(
    current_user: User = Depends(verify_compliance_officer),
    db: AsyncSession = Depends(get_db)
):
    result = await db.execute(select(Customer).order_by(Customer.created_at.desc()))
    return result.scalars().all()

@router.post("/", response_model=CustomerResponse, status_code=status.HTTP_201_CREATED)
async def create_customer(
    customer_in: CustomerCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    result = await db.execute(select(Customer).where(Customer.user_id == current_user.id))
    existing_customer = result.scalars().first()
    if existing_customer:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="A customer profile already exists for this account."
        )

    customer = Customer(
        user_id=current_user.id,
        customer_type=customer_in.customer_type,
        first_name=customer_in.first_name,
        last_name=customer_in.last_name,
        dob=customer_in.dob,
        nationality=customer_in.nationality,
        phone_number=customer_in.phone_number,
        street_address=customer_in.street_address,
        city=customer_in.city,
        postal_code=customer_in.postal_code,
        country=customer_in.country,
        status="pending_verification"
    )
    db.add(customer)
    await db.flush()

    if customer_in.customer_type == "corporate":
        if not customer_in.company:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Company details are required for corporate customers."
            )
        
        result = await db.execute(select(Company).where(Company.registration_number == customer_in.company.registration_number))
        existing_company = result.scalars().first()
        if existing_company:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="A company with this registration number already exists."
            )

        company = Company(
            customer_id=customer.id,
            company_name=customer_in.company.company_name,
            registration_number=customer_in.company.registration_number,
            registered_address=customer_in.company.registered_address,
            trading_address=customer_in.company.trading_address,
            country_of_incorporation=customer_in.company.country_of_incorporation,
            incorporation_date=customer_in.company.incorporation_date,
            sic_code=customer_in.company.sic_code,
            status="active"
        )
        db.add(company)
        await db.flush()

        if customer_in.directors:
            for dir_in in customer_in.directors:
                director = Director(
                    company_id=company.id,
                    first_name=dir_in.first_name,
                    last_name=dir_in.last_name,
                    dob=dir_in.dob,
                    nationality=dir_in.nationality,
                    appointment_date=dir_in.appointment_date,
                    is_active=True,
                    verification_status="unverified"
                )
                db.add(director)

        if customer_in.ubos:
            for ubo_in in customer_in.ubos:
                ubo = UBO(
                    company_id=company.id,
                    first_name=ubo_in.first_name,
                    last_name=ubo_in.last_name,
                    dob=ubo_in.dob,
                    nationality=ubo_in.nationality,
                    ownership_percentage=ubo_in.ownership_percentage,
                    control_type=ubo_in.control_type,
                    verification_status="unverified"
                )
                db.add(ubo)

    await db.commit()
    await db.refresh(customer)
    return customer

@router.get("/me", response_model=CustomerResponse)
async def get_my_customer(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    result = await db.execute(select(Customer).where(Customer.user_id == current_user.id))
    customer = result.scalars().first()
    if not customer:
        raise HTTPException(status_code=404, detail="Customer profile not found.")
    return customer

@router.get("/me/company")
async def get_my_company(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    result = await db.execute(select(Customer).where(Customer.user_id == current_user.id))
    customer = result.scalars().first()
    if not customer:
        raise HTTPException(status_code=404, detail="Customer profile not found.")
        
    comp_result = await db.execute(select(Company).where(Company.customer_id == customer.id))
    company = comp_result.scalars().first()
    if not company:
        raise HTTPException(status_code=404, detail="Company details not found.")
        
    dir_result = await db.execute(select(Director).where(Director.company_id == company.id))
    directors = dir_result.scalars().all()
    
    ubo_result = await db.execute(select(UBO).where(UBO.company_id == company.id))
    ubos = ubo_result.scalars().all()
    
    return {
        "company": {
            "company_name": company.company_name,
            "registration_number": company.registration_number,
            "registered_address": company.registered_address,
            "trading_address": company.trading_address,
            "country_of_incorporation": company.country_of_incorporation,
            "incorporation_date": company.incorporation_date,
            "sic_code": company.sic_code,
        },
        "directors": [
            {
                "first_name": d.first_name,
                "last_name": d.last_name,
                "dob": d.dob,
                "nationality": d.nationality,
                "appointment_date": d.appointment_date,
            }
            for d in directors
        ],
        "ubos": [
            {
                "first_name": u.first_name,
                "last_name": u.last_name,
                "dob": u.dob,
                "nationality": u.nationality,
                "ownership_percentage": float(ubo_in.ownership_percentage) if hasattr(ubo_in := u, "ownership_percentage") else 0,
                "control_type": u.control_type,
            }
            for u in ubos
        ]
    }

@router.get("/{id}", response_model=CustomerResponse)
async def get_customer_by_id(
    id: UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    result = await db.execute(select(Customer).where(Customer.id == id))
    customer = result.scalars().first()
    if not customer:
        raise HTTPException(status_code=404, detail="Customer not found.")
        
    # Check permissions
    if customer.user_id != current_user.id and current_user.role not in ["compliance_officer", "admin"]:
        raise HTTPException(status_code=403, detail="Not authorized to access this customer profile.")
        
    return customer

@router.put("/{id}", response_model=CustomerResponse)
async def update_customer(
    id: UUID,
    customer_in: CustomerUpdate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    result = await db.execute(select(Customer).where(Customer.id == id))
    customer = result.scalars().first()
    if not customer:
        raise HTTPException(status_code=404, detail="Customer not found.")
        
    if customer.user_id != current_user.id and current_user.role not in ["compliance_officer", "admin"]:
        raise HTTPException(status_code=403, detail="Not authorized to edit this profile.")

    update_data = customer_in.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(customer, field, value)
    
    await db.commit()
    await db.refresh(customer)
    return customer

@router.delete("/{id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_customer(
    id: UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    result = await db.execute(select(Customer).where(Customer.id == id))
    customer = result.scalars().first()
    if not customer:
        raise HTTPException(status_code=404, detail="Customer not found.")
        
    if customer.user_id != current_user.id and current_user.role != "admin":
        raise HTTPException(status_code=403, detail="Only the profile owner or administrator can delete this profile.")

    await db.delete(customer)
    await db.commit()
    return None
