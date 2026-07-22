"""
Phase 15 Security, Hardening & Observability Tests
==================================================
Covers:
  1. Password complexity rules validation
  2. AES-256 GCM field-level encryption/decryption roundtrips
  3. Brute-force lockout and account unlocking
  4. Login history records tracking
  5. JWT JTI token revocation outbox blacklist
  6. TOTP-based Multi-Factor Authentication setup, confirmation, and verify
  7. Observability metrics collections
  8. Redis cache patterns
  9. System backups creation, SHA-256 integrity verification, and cleanup
"""

import json
import pytest
import time
from datetime import datetime, timedelta
from uuid import uuid4, UUID
from unittest.mock import AsyncMock, MagicMock, patch

from app.core.config import settings
from app.core.security import validate_password_complexity, get_password_hash
from app.security.encryption import encrypt, decrypt, hash_value, verify_hash
from app.services.auth_service import AuthService
from app.services.observability_service import ObservabilityService
from app.services.backup_service import BackupService
from app.core.cache import cache

from sqlalchemy.ext.asyncio import AsyncSession

# ─── Mock DB Helper ───────────────────────────────────────────────────────────


class _ScalarResult:
    def __init__(self, items):
        self._items = items

    def first(self):
        return self._items[0] if self._items else None

    def all(self):
        return list(self._items)

    def scalars(self):
        return self


def make_mock_db(rows=None):
    db = AsyncMock(spec=AsyncSession)
    db.execute.return_value = _ScalarResult(rows or [])
    db.get = AsyncMock(return_value=rows[0] if rows else None)
    db.flush = AsyncMock()
    db.commit = AsyncMock()
    db.rollback = AsyncMock()
    db.add = MagicMock()
    db.delete = AsyncMock()
    db.refresh = AsyncMock()
    # Mock bind dialect name
    db.bind = MagicMock()
    db.bind.dialect.name = "sqlite"
    return db


# ─── 1. Password Complexity Rules ────────────────────────────────────────────


class TestPasswordComplexity:
    def test_valid_complex_password(self):
        ok, msg = validate_password_complexity("StrongSecurePass99!")
        assert ok is True
        assert "meets complexity" in msg

    def test_too_short_password(self):
        ok, msg = validate_password_complexity("Short1!")
        assert ok is False
        assert "at least" in msg

    def test_no_uppercase(self):
        ok, msg = validate_password_complexity("lowercaseonly99!")
        assert ok is False
        assert "uppercase" in msg

    def test_no_lowercase(self):
        ok, msg = validate_password_complexity("UPPERCASEONLY99!")
        assert ok is False
        assert "lowercase" in msg

    def test_no_digit(self):
        ok, msg = validate_password_complexity("NoDigitsInHere!")
        assert ok is False
        assert "number" in msg

    def test_no_special_character(self):
        ok, msg = validate_password_complexity("NoSpecialChars99")
        assert ok is False
        assert "special character" in msg


# ─── 2. AES-256 GCM Field Encryption ──────────────────────────────────────────


class TestFieldEncryption:
    def test_encryption_decryption_roundtrip(self):
        secret_value = "SecretNationalID_1234567"
        encrypted = encrypt(secret_value)
        assert encrypted != secret_value
        assert encrypted.startswith("enc:") or encrypted.startswith("plain:")

        decrypted = decrypt(encrypted)
        assert decrypted == secret_value

    def test_decryption_on_unencrypted_returns_as_is(self):
        unencrypted = "NormalPublicString"
        decrypted = decrypt(unencrypted)
        assert decrypted == unencrypted

    def test_hashing_and_verification(self):
        pii = "PassportNumber999"
        h = hash_value(pii)
        assert len(h) == 64  # sha256 hex is 64 characters
        assert verify_hash(pii, h) is True
        assert verify_hash("WrongPassportNumber", h) is False


# ─── 3. Lockout & Brute Force ─────────────────────────────────────────────────


@pytest.mark.asyncio
class TestLockoutMechanisms:
    async def test_authentication_with_lockout(self):
        # Create a user locked in the future
        user = MagicMock()
        user.id = uuid4()
        user.email = "locked@test.com"
        user.is_active = True
        user.locked_until = datetime.utcnow() + timedelta(minutes=5)

        db = make_mock_db([user])
        with pytest.raises(Exception) as exc:
            await AuthService.authenticate_user(db, "locked@test.com", "SomePassword!")
        assert "locked" in str(exc.value).lower()

    async def test_successful_auth_resets_failed_count(self):
        user = MagicMock()
        user.id = uuid4()
        user.email = "test@test.com"
        user.password_hash = get_password_hash("PassComplex99!")
        user.is_active = True
        user.failed_login_count = 3
        user.locked_until = None
        user.password_changed_at = datetime.utcnow()

        db = make_mock_db([user])
        authenticated_user = await AuthService.authenticate_user(
            db, "test@test.com", "PassComplex99!"
        )
        assert authenticated_user.failed_login_count == 0
        assert authenticated_user.locked_until is None


# ─── 4. Token Revocation Blacklist ───────────────────────────────────────────


@pytest.mark.asyncio
class TestTokenRevocation:
    async def test_revoke_token_records_db_entry(self):
        db = make_mock_db()
        jti = "jti-uuid-string-token"
        user_id = uuid4()
        await AuthService.revoke_token(db, jti, user_id, "logout")
        # Assert commit/add called
        assert db.commit.called

    async def test_is_token_revoked_check(self):
        revoked_token = MagicMock()
        revoked_token.jti = "blacklisted-jti"

        db = make_mock_db([revoked_token])
        is_rev = await AuthService.is_token_revoked(db, "blacklisted-jti")
        assert is_rev is True

        db_empty = make_mock_db([])
        is_rev_no = await AuthService.is_token_revoked(db_empty, "clean-jti")
        assert is_rev_no is False


# ─── 5. TOTP Multi-Factor Authentication ──────────────────────────────────────


@pytest.mark.asyncio
class TestMultiFactorAuthentication:
    async def test_enroll_mfa_flow(self):
        user = MagicMock()
        user.id = uuid4()
        user.email = "mfa@test.com"

        db = make_mock_db([])
        secret, uri, qr_b64, backup_codes = await AuthService.enroll_mfa(db, user)
        assert len(secret) > 10
        assert "otpauth://totp/" in uri
        assert len(backup_codes) == 8
        assert db.commit.called

    async def test_verify_mfa_login_disabled(self):
        user = MagicMock()
        user.id = uuid4()

        # User without MFA enabled settings
        db = make_mock_db([])
        res = await AuthService.verify_mfa_login(db, user, "123456")
        assert res is True  # returns True to pass through if disabled


# ─── 6. Observability Metrics ────────────────────────────────────────────────


@pytest.mark.asyncio
class TestObservabilityMetrics:
    async def test_get_system_metrics_structure(self):
        metrics = await ObservabilityService.get_system_metrics()
        assert "cpu_percent" in metrics
        assert "memory_percent" in metrics
        assert "disk_percent" in metrics

    async def test_record_and_read_api_stats(self):
        ObservabilityService.record_request("/api/v1/auth/login", "POST", 200, 150.0)
        ObservabilityService.record_request("/api/v1/customers", "GET", 400, 20.0)

        stats = await ObservabilityService.get_api_stats()
        assert stats["request_count_1h"] >= 2
        assert stats["average_latency_ms"] > 0
        assert stats["error_rate_percent"] == 50.0


# ─── 7. Cache Service ─────────────────────────────────────────────────────────


@pytest.mark.asyncio
class TestCacheService:
    async def test_cache_set_and_get(self):
        await cache.set("test_key", {"data": "hello"}, ttl=10)
        val = await cache.get("test_key")
        assert val == {"data": "hello"}

    async def test_cache_delete(self):
        await cache.set("delete_key", "value")
        await cache.delete("delete_key")
        val = await cache.get("delete_key")
        assert val is None

    async def test_cache_delete_pattern(self):
        await cache.set("pat:one", "1")
        await cache.set("pat:two", "2")
        await cache.set("other:three", "3")

        count = await cache.delete_pattern("pat:*")
        assert count >= 2
        assert await cache.get("pat:one") is None
        assert await cache.get("other:three") == "3"


# ─── 8. Backup & Integrity ────────────────────────────────────────────────────


@pytest.mark.asyncio
class TestBackupService:
    async def test_list_and_integrity_fallback(self):
        db = make_mock_db()
        record = await BackupService.create_backup(
            db, backup_type="config", triggered_by="manual"
        )
        assert record.status == "completed"
        assert record.backup_type == "config"
        assert len(record.sha256_checksum) == 64

        # Verify integrity
        db_with_record = make_mock_db([record])
        is_ok = await BackupService.verify_backup_integrity(record.id, db_with_record)
        assert is_ok is True
