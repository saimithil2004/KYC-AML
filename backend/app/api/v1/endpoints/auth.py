from fastapi import APIRouter, Depends, HTTPException, status, Response, Request
from uuid import UUID
from typing import List
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from jose import jwt, JWTError
from app.core.config import settings
from app.core.database import get_db
from app.core.security import get_password_hash, verify_password, create_access_token, create_refresh_token
from app.dependencies.auth import get_current_user
from app.models.models import User, LoginHistory
from app.schemas.schemas import (
    UserRegister, UserLogin, Token, UserResponse, ChangePasswordRequest, 
    LoginHistoryResponse, MFAEnrollResponse, MFAVerifyRequest, MFASetupResponse
)
from app.services.auth_service import AuthService

router = APIRouter()

@router.post("/register", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
async def register(user_in: UserRegister, db: AsyncSession = Depends(get_db)):
    user = await AuthService.register_user(db, user_in)
    return user

@router.post("/login", response_model=Token)
async def login(
    request: Request,
    response: Response,
    user_in: UserLogin,
    db: AsyncSession = Depends(get_db)
):
    ip_address = request.client.host if request.client else "unknown"
    user_agent = request.headers.get("user-agent", "")

    # 1. Authenticate (handles lockouts, passive expiry tracking, login history)
    user = await AuthService.authenticate_user(
        db=db, 
        email=user_in.email, 
        password=user_in.password, 
        ip_address=ip_address, 
        user_agent=user_agent
    )

    # 2. Check TOTP Multi-factor verification during login
    mfa_set = await AuthService.get_mfa_settings(db, user.id)
    if mfa_set and mfa_set.enabled:
        if not user_in.mfa_code:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="MFA_REQUIRED"
            )
        is_mfa_ok = await AuthService.verify_mfa_login(db, user, user_in.mfa_code)
        if not is_mfa_ok:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid Multi-factor code or backup code."
            )

    # 3. Generate tokens with JTI support
    access_token = create_access_token(subject=user.id, role=user.role)
    refresh_token = create_refresh_token(subject=user.id, role=user.role)
    
    # Set Refresh Token as an HttpOnly secure cookie
    response.set_cookie(
        key="refresh_token",
        value=refresh_token,
        httponly=True,
        max_age=settings.REFRESH_TOKEN_EXPIRE_DAYS * 24 * 60 * 60,
        samesite="strict",
        secure=settings.COOKIE_SECURE
    )
    
    return {
        "access_token": access_token,
        "refresh_token": refresh_token,
        "token_type": "bearer",
        "user": user,
    }

@router.post("/refresh", response_model=Token)
async def refresh_token(request: Request, response: Response, db: AsyncSession = Depends(get_db)):
    refresh_tok = request.cookies.get("refresh_token")
    if not refresh_tok:
        raise HTTPException(status_code=401, detail="Refresh token missing")
        
    try:
        payload = jwt.decode(refresh_tok, settings.SECRET_KEY, algorithms=["HS256"])
        user_id: str = payload.get("sub")
        token_type: str = payload.get("type")
        jti: str = payload.get("jti")
        if user_id is None or token_type != "refresh":
            raise HTTPException(status_code=401, detail="Invalid refresh token")
        
        # Check revocation
        if await AuthService.is_token_revoked(db, jti):
            raise HTTPException(status_code=401, detail="Refresh token is revoked")

        user_uuid = UUID(user_id)
    except JWTError:
        raise HTTPException(status_code=401, detail="Invalid refresh token")
    except ValueError:
        raise HTTPException(status_code=401, detail="Invalid refresh token")
        
    result = await db.execute(select(User).where(User.id == user_uuid))
    user = result.scalars().first()
    if not user or not user.is_active:
        raise HTTPException(status_code=401, detail="User not found or inactive")
        
    # Rotate refresh token (token rotation policy)
    new_access_token = create_access_token(subject=user.id, role=user.role)
    new_refresh_token = create_refresh_token(subject=user.id, role=user.role)
    
    # Revoke old refresh token JTI
    if jti:
        await AuthService.revoke_token(db, jti, user.id, reason="refresh_token_rotation")

    response.set_cookie(
        key="refresh_token",
        value=new_refresh_token,
        httponly=True,
        max_age=settings.REFRESH_TOKEN_EXPIRE_DAYS * 24 * 60 * 60,
        samesite="strict",
        secure=settings.COOKIE_SECURE
    )
    
    return {
        "access_token": new_access_token,
        "refresh_token": new_refresh_token,
        "token_type": "bearer",
        "user": user,
    }

@router.post("/logout")
async def logout(request: Request, response: Response, db: AsyncSession = Depends(get_db)):
    """Revokes the current refresh token and clears auth cookies."""
    refresh_tok = request.cookies.get("refresh_token")
    if refresh_tok:
        try:
            payload = jwt.decode(refresh_tok, settings.SECRET_KEY, algorithms=["HS256"])
            jti = payload.get("jti")
            user_id = payload.get("sub")
            if jti:
                await AuthService.revoke_token(db, jti, UUID(user_id) if user_id else None, reason="logout")
        except Exception:
            pass

    response.delete_cookie(key="refresh_token")
    return {"detail": "Successfully logged out."}

@router.get("/me", response_model=UserResponse)
async def read_current_user(current_user: User = Depends(get_current_user)):
    return current_user

@router.post("/change-password")
async def change_password(
    body: ChangePasswordRequest, 
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    if not verify_password(body.old_password, current_user.password_hash):
        raise HTTPException(status_code=400, detail="Incorrect current password.")
    await AuthService.change_password(db, current_user, body.new_password)
    return {"detail": "Password changed successfully."}

@router.get("/login-history", response_model=List[LoginHistoryResponse])
async def get_login_history(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    # Standard security audit: users see their own history, admins see all
    query = select(LoginHistory)
    if current_user.role != "admin":
        query = query.where(LoginHistory.user_id == current_user.id)
    query = query.order_by(LoginHistory.created_at.desc()).limit(100)
    result = await db.execute(query)
    return result.scalars().all()

# ─── Multi-Factor Authentication Endpoints ───────────────────────────────────

@router.post("/mfa/setup", response_model=MFAEnrollResponse)
async def setup_mfa(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    secret, uri, qr_b64, backup_codes = await AuthService.enroll_mfa(db, current_user)
    return {
        "secret": secret,
        "qr_code_base64": qr_b64,
        "backup_codes": backup_codes,
        "otpauth_uri": uri
    }

@router.post("/mfa/verify", response_model=MFASetupResponse)
async def verify_mfa(
    body: MFAVerifyRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    success = await AuthService.confirm_mfa(db, current_user, body.code)
    if not success:
        raise HTTPException(status_code=400, detail="Invalid verification code.")
    return {
        "success": True,
        "message": "Multi-factor authentication enabled successfully."
    }

@router.post("/mfa/disable")
async def disable_mfa(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    await AuthService.disable_mfa(db, current_user)
    return {"detail": "Multi-factor authentication disabled."}

