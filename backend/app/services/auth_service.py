from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from fastapi import HTTPException, status
from app.models.models import User
from app.core.security import get_password_hash, verify_password, create_access_token, create_refresh_token
from app.schemas.schemas import UserRegister, UserLogin

class AuthService:
    @staticmethod
    async def register_user(db: AsyncSession, user_in: UserRegister) -> User:
        result = await db.execute(select(User).where(User.email == user_in.email))
        existing_user = result.scalars().first()
        if existing_user:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Email address already registered in the system."
            )
        
        new_user = User(
            email=user_in.email,
            password_hash=get_password_hash(user_in.password),
            role=user_in.role,
            is_active=True
        )
        db.add(new_user)
        await db.commit()
        await db.refresh(new_user)
        return new_user

    @staticmethod
    async def authenticate_user(db: AsyncSession, credentials: UserLogin) -> User:
        result = await db.execute(select(User).where(User.email == credentials.email))
        user = result.scalars().first()
        if not user or not verify_password(credentials.password, user.password_hash):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Incorrect email or password."
            )
        if not user.is_active:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="User account is deactivated."
            )
        return user
