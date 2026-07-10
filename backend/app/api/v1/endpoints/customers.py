from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from uuid import UUID
from app.core.database import get_db
from app.dependencies.auth import get_current_user, verify_compliance_officer
from app.models.models import User, Customer
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
