import json
import logging
from datetime import datetime, timedelta, timezone
from typing import Optional, Tuple, List
from uuid import UUID, uuid4
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from fastapi import HTTPException, status

from app.core.config import settings
from app.models.models import User, LoginHistory, PasswordHistory, MFASettings, RevokedToken, SecurityEvent
from app.core.security import get_password_hash, verify_password, validate_password_complexity
from app.security.encryption import encrypt, decrypt, verify_totp, generate_totp_secret, generate_totp_uri, generate_qr_code_base64, generate_backup_codes
from app.services.audit_service import AuditService

logger = logging.getLogger(__name__)

class AuthService:
    @staticmethod
    async def register_user(db: AsyncSession, user_in) -> User:
        result = await db.execute(select(User).where(User.email == user_in.email))
        existing_user = result.scalars().first()
        if existing_user:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Email address already registered in the system."
            )
        
        # Check password complexity on registration
        is_ok, msg = validate_password_complexity(user_in.password)
        if not is_ok:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=msg)
            
        pass_hash = get_password_hash(user_in.password)
        new_user = User(
            email=user_in.email,
            password_hash=pass_hash,
            role=user_in.role,
            is_active=True,
            failed_login_count=0,
            password_changed_at=datetime.utcnow()
        )
        db.add(new_user)
        await db.commit()
        await db.refresh(new_user)

        # Record initial password in history
        history = PasswordHistory(user_id=new_user.id, password_hash=pass_hash)
        db.add(history)
        await db.commit()

        await AuditService.log(
            db=db,
            user_id=None,
            action="REGISTER",
            entity_name="users",
            entity_id=new_user.id,
            new_values={"email": new_user.email, "role": new_user.role}
        )
        return new_user

    @staticmethod
    async def authenticate_user(
        db: AsyncSession, 
        email: str, 
        password: str, 
        ip_address: Optional[str] = None, 
        user_agent: Optional[str] = None
    ) -> User:
        # 1. Fetch user
        result = await db.execute(select(User).where(User.email == email))
        user = result.scalars().first()
        
        if not user:
            # Record failed login attempt for unknown user
            await AuthService._record_login_history(
                db=db, user_id=None, email=email, ip=ip_address, ua=user_agent, 
                success=False, failure_reason="user_not_found"
            )
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Incorrect email or password."
            )

        # 2. Check lockout status
        if user.locked_until and user.locked_until > datetime.utcnow():
            await AuthService._record_login_history(
                db=db, user_id=user.id, email=email, ip=ip_address, ua=user_agent, 
                success=False, failure_reason="account_locked"
            )
            time_left = int((user.locked_until - datetime.utcnow()).total_seconds() / 60)
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Account is temporarily locked. Try again in {max(1, time_left)} minutes."
            )

        # 3. Check status
        if not user.is_active:
            await AuthService._record_login_history(
                db=db, user_id=user.id, email=email, ip=ip_address, ua=user_agent, 
                success=False, failure_reason="user_inactive"
            )
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="User account is deactivated."
            )

        # 4. Verify password
        if not verify_password(password, user.password_hash):
            # Increment failed count
            user.failed_login_count = (user.failed_login_count or 0) + 1
            failure_reason = "incorrect_password"

            # Check if we should lock
            if user.failed_login_count >= settings.MAX_LOGIN_ATTEMPTS:
                user.locked_until = datetime.utcnow() + timedelta(minutes=settings.ACCOUNT_LOCKOUT_MINUTES)
                failure_reason = "account_locked"
                
                # Create a security alert event
                alert_evt = SecurityEvent(
                    event_type="ACCOUNT_LOCKED",
                    severity="high",
                    user_id=user.id,
                    ip_address=ip_address,
                    description=f"User {email} locked out after {settings.MAX_LOGIN_ATTEMPTS} failed attempts."
                )
                db.add(alert_evt)
                await AuditService.log(
                    db=db, user_id=user.id, action="ACCOUNT_LOCKED", 
                    entity_name="users", entity_id=user.id, reason="brute_force_protection"
                )

            await db.commit()
            await AuthService._record_login_history(
                db=db, user_id=user.id, email=email, ip=ip_address, ua=user_agent, 
                success=False, failure_reason=failure_reason
            )
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Incorrect email or password."
            )

        # 5. Success
        user.failed_login_count = 0
        user.locked_until = None
        user.last_login_at = datetime.utcnow()
        await db.commit()

        # Check if password expired
        password_expired = False
        if user.password_changed_at:
            age_days = (datetime.utcnow() - user.password_changed_at).days
            if age_days >= settings.PASSWORD_EXPIRY_DAYS:
                password_expired = True

        # Store success in login_history
        await AuthService._record_login_history(
            db=db, user_id=user.id, email=email, ip=ip_address, ua=user_agent, 
            success=True
        )
        
        await AuditService.log(
            db=db, user_id=user.id, action="LOGIN", 
            entity_name="users", entity_id=user.id
        )

        # We attach password expiry metadata to the user object dynamically for endpoint to intercept
        user.password_expired = password_expired
        return user

    @staticmethod
    async def change_password(db: AsyncSession, user: User, new_password: str) -> None:
        """Changes a user's password enforcing history list validation."""
        # 1. Complexity Validation
        is_ok, msg = validate_password_complexity(new_password)
        if not is_ok:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=msg)

        # 2. History verification
        # Fetch previous hashes
        history_result = await db.execute(
            select(PasswordHistory)
            .where(PasswordHistory.user_id == user.id)
            .order_back(PasswordHistory.created_at.desc())
            .limit(settings.PASSWORD_HISTORY_COUNT)
        )
        # Wait, SQLite/PostgreSQL order_by compatible:
        history_result = await db.execute(
            select(PasswordHistory)
            .where(PasswordHistory.user_id == user.id)
            .order_by(PasswordHistory.created_at.desc())
            .limit(settings.PASSWORD_HISTORY_COUNT)
        )
        previous_passwords = history_result.scalars().all()
        for p in previous_passwords:
            if verify_password(new_password, p.password_hash):
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Cannot reuse any of your last 5 passwords."
                )

        # Save to history
        new_hash = get_password_hash(new_password)
        hist = PasswordHistory(user_id=user.id, password_hash=new_hash)
        db.add(hist)

        # Update User
        user.password_hash = new_hash
        user.password_changed_at = datetime.utcnow()
        await db.commit()

        # Audit
        await AuditService.log(
            db=db, user_id=user.id, action="PASSWORD_CHANGED", 
            entity_name="users", entity_id=user.id
        )

    @staticmethod
    async def _record_login_history(
        db: AsyncSession,
        user_id: Optional[UUID],
        email: str,
        ip: Optional[str],
        ua: Optional[str],
        success: bool,
        failure_reason: Optional[str] = None
    ) -> None:
        try:
            lh = LoginHistory(
                user_id=user_id,
                email=email,
                ip_address=ip,
                user_agent=ua,
                success=success,
                failure_reason=failure_reason
            )
            db.add(lh)
            await db.commit()
        except Exception as e:
            logger.error(f"Failed to save login history log: {e}")

    @staticmethod
    async def revoke_token(db: AsyncSession, jti: str, user_id: Optional[UUID], reason: str = "logout") -> None:
        """Add token identifier to JTI revocation list."""
        # Calculate expiry (we keep it simple and clean up expired JTIs daily)
        expires_at = datetime.utcnow() + timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS)
        rev = RevokedToken(
            jti=jti,
            user_id=user_id,
            token_type="access" if "access" in reason else "refresh",
            reason=reason,
            expires_at=expires_at
        )
        db.add(rev)
        await db.commit()
        await AuditService.log(
            db=db, user_id=user_id, action="TOKEN_REVOKED", 
            entity_name="revoked_tokens", entity_id=rev.id, reason=reason
        )

    @staticmethod
    async def is_token_revoked(db: AsyncSession, jti: str) -> bool:
        """Check if JWT JTI identifier is in revoked lists."""
        if not jti:
            return False
        result = await db.execute(select(RevokedToken).where(RevokedToken.jti == jti))
        return result.scalars().first() is not None

    @staticmethod
    async def cleanup_revoked_tokens(db: AsyncSession) -> int:
        """Prune expired revoked token rows."""
        result = await db.execute(
            select(RevokedToken).where(RevokedToken.expires_at < datetime.utcnow())
        )
        expired = result.scalars().all()
        for r in expired:
            await db.delete(r)
        if expired:
            await db.commit()
        return len(expired)

    # ─── Multi-Factor Authentication (TOTP) ──────────────────────────────────

    @staticmethod
    async def get_mfa_settings(db: AsyncSession, user_id: UUID) -> Optional[MFASettings]:
        result = await db.execute(select(MFASettings).where(MFASettings.user_id == user_id))
        return result.scalars().first()

    @staticmethod
    async def enroll_mfa(db: AsyncSession, user: User) -> Tuple[str, str, str, List[str]]:
        """
        Generate TOTP credentials but do not mark setup_completed=True yet.
        Returns: (secret, provisioning_uri, qr_code_base64, backup_codes)
        """
        secret = generate_totp_secret()
        uri = generate_totp_uri(secret, user.email)
        qr_b64 = generate_qr_code_base64(uri) or ""
        backup_codes = generate_backup_codes(8)

        # Enforce encrypted storage of TOTP secrets in database
        encrypted_secret = encrypt(secret)
        # Hash the backup codes for secure validation later
        hashed_codes = [get_password_hash(c) for c in backup_codes]

        # Check if settings exist, otherwise create
        mfa_set = await AuthService.get_mfa_settings(db, user.id)
        if not mfa_set:
            mfa_set = MFASettings(user_id=user.id)
            db.add(mfa_set)

        mfa_set.secret = encrypted_secret
        mfa_set.backup_codes = json.dumps(hashed_codes)
        mfa_set.enabled = False  # Only enable after confirmation code check
        mfa_set.setup_completed = False
        await db.commit()

        return secret, uri, qr_b64, backup_codes

    @staticmethod
    async def confirm_mfa(db: AsyncSession, user: User, code: str) -> bool:
        """Verify the first TOTP code to confirm enroll and set enabled=True."""
        mfa_set = await AuthService.get_mfa_settings(db, user.id)
        if not mfa_set or not mfa_set.secret:
            return False

        # Decrypt secret
        secret = decrypt(mfa_set.secret)
        if verify_totp(secret, code):
            mfa_set.enabled = True
            mfa_set.setup_completed = True
            mfa_set.last_used_at = datetime.utcnow()
            
            # Save MFA status on user record as well
            user.mfa_secret = mfa_set.secret
            
            await db.commit()
            await AuditService.log(
                db=db, user_id=user.id, action="MFA_SETUP", 
                entity_name="mfa_settings", entity_id=mfa_set.id
            )
            return True
        return False

    @staticmethod
    async def verify_mfa_login(db: AsyncSession, user: User, code: str) -> bool:
        """Verify code at login. Supports backup recovery code fallback."""
        mfa_set = await AuthService.get_mfa_settings(db, user.id)
        if not mfa_set or not mfa_set.enabled:
            return True  # If not setup, MFA is bypassed/disabled for this user

        # Decrypt secret
        secret = decrypt(mfa_set.secret)
        if verify_totp(secret, code):
            mfa_set.last_used_at = datetime.utcnow()
            await db.commit()
            return True

        # Check if code matches backup recovery code
        if mfa_set.backup_codes:
            hashed_codes = json.loads(mfa_set.backup_codes)
            for idx, h_code in enumerate(hashed_codes):
                if verify_password(code.upper(), h_code):
                    # Code matches, consume it
                    hashed_codes.pop(idx)
                    mfa_set.backup_codes = json.dumps(hashed_codes)
                    mfa_set.last_used_at = datetime.utcnow()
                    await db.commit()
                    
                    # Log security event
                    alert_evt = SecurityEvent(
                        event_type="BACKUP_CODE_USED",
                        severity="medium",
                        user_id=user.id,
                        description=f"User {user.email} logged in using an MFA backup recovery code."
                    )
                    db.add(alert_evt)
                    await db.commit()
                    return True

        return False

    @staticmethod
    async def disable_mfa(db: AsyncSession, user: User) -> None:
        """Disable MFA for a user."""
        mfa_set = await AuthService.get_mfa_settings(db, user.id)
        if mfa_set:
            mfa_set.enabled = False
            mfa_set.setup_completed = False
            mfa_set.secret = None
            mfa_set.backup_codes = None
            
            user.mfa_secret = None
            await db.commit()
            await AuditService.log(
                db=db, user_id=user.id, action="MFA_DISABLED", 
                entity_name="mfa_settings", entity_id=mfa_set.id
            )

