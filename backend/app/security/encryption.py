"""
AES-256 GCM Encryption Layer — Phase 15
=========================================
Provides field-level AES-256 GCM encryption for all PII stored in the database.

Fields encrypted:
  - Customer passport/national ID numbers
  - Bank account numbers
  - Integration API keys / secrets
  - Webhook signing secrets
  - Company registration numbers (where sensitive)

The encryption key is derived from settings.ENCRYPTION_KEY using PBKDF2HMAC
to ensure the key is exactly 32 bytes regardless of the raw key length.

Graceful degradation:
  - If the `cryptography` package is not installed, all operations fall back
    to base64 encoding (no real encryption) and log a WARNING. This ensures
    the application boots in development environments without the package.

Usage:
    from app.security.encryption import encrypt, decrypt, hash_value, verify_hash

    encrypted = encrypt("GB12345678")
    original  = decrypt(encrypted)
    h         = hash_value("GB12345678")
    ok        = verify_hash("GB12345678", h)
"""

import base64
import hashlib
import hmac
import logging
import os
import secrets
from typing import Optional

logger = logging.getLogger(__name__)

# ─── Try to import cryptography ───────────────────────────────────────────────

try:
    from cryptography.hazmat.primitives.ciphers.aead import AESGCM
    from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
    from cryptography.hazmat.primitives import hashes
    from cryptography.hazmat.backends import default_backend

    _CRYPTO_AVAILABLE = True
except ImportError:
    _CRYPTO_AVAILABLE = False
    logger.warning(
        "⚠  `cryptography` package not installed. "
        "Encryption is in PASSTHROUGH mode — install it for production!"
    )

# ─── Try TOTP / QR dependencies ──────────────────────────────────────────────

try:
    import pyotp

    _PYOTP_AVAILABLE = True
except ImportError:
    _PYOTP_AVAILABLE = False
    logger.warning("`pyotp` not available — MFA TOTP disabled.")

try:
    import qrcode
    import io

    _QRCODE_AVAILABLE = True
except ImportError:
    _QRCODE_AVAILABLE = False
    logger.warning("`qrcode` not available — QR generation disabled.")


# ─── Key Derivation ───────────────────────────────────────────────────────────


def _derive_key(raw_key: str) -> bytes:
    """
    Derive a 32-byte AES key from the raw settings key using PBKDF2-HMAC-SHA256.
    Salt is deterministic so the key is consistent across restarts.
    """
    if not _CRYPTO_AVAILABLE:
        return b"\x00" * 32
    salt = hashlib.sha256(b"aml_kyc_platform_v15_salt").digest()
    kdf = PBKDF2HMAC(
        algorithm=hashes.SHA256(),
        length=32,
        salt=salt,
        iterations=100_000,
        backend=default_backend(),
    )
    return kdf.derive(raw_key.encode("utf-8"))


def _get_key() -> bytes:
    """Load and cache the encryption key."""
    from app.core.config import settings

    return _derive_key(settings.ENCRYPTION_KEY)


# ─── Core Encryption Functions ────────────────────────────────────────────────


def encrypt(plaintext: str) -> str:
    """
    Encrypt a string using AES-256 GCM.
    Returns: base64url(nonce[12] + ciphertext + tag[16])
    Falls back to base64 if cryptography not installed.
    """
    if not plaintext:
        return plaintext

    if not _CRYPTO_AVAILABLE:
        # Passthrough mode — encode only
        return "plain:" + base64.b64encode(plaintext.encode()).decode()

    try:
        key = _get_key()
        nonce = os.urandom(12)  # 96-bit nonce for GCM
        aesgcm = AESGCM(key)
        ciphertext = aesgcm.encrypt(nonce, plaintext.encode("utf-8"), None)
        combined = (
            nonce + ciphertext
        )  # nonce + ciphertext+tag (AESGCM appends 16-byte tag)
        return "enc:" + base64.urlsafe_b64encode(combined).decode()
    except Exception as exc:
        logger.error(f"Encryption failed: {exc}")
        return plaintext


def decrypt(ciphertext: str) -> str:
    """
    Decrypt a value encrypted by encrypt().
    Returns original plaintext, or the input unchanged if not encrypted.
    """
    if not ciphertext:
        return ciphertext

    if ciphertext.startswith("plain:"):
        return base64.b64decode(ciphertext[6:]).decode()

    if not ciphertext.startswith("enc:"):
        return ciphertext  # Not encrypted, return as-is

    if not _CRYPTO_AVAILABLE:
        logger.warning("Cannot decrypt — cryptography package not installed.")
        return ciphertext

    try:
        key = _get_key()
        combined = base64.urlsafe_b64decode(ciphertext[4:])
        nonce = combined[:12]
        encrypted_data = combined[12:]
        aesgcm = AESGCM(key)
        plaintext = aesgcm.decrypt(nonce, encrypted_data, None)
        return plaintext.decode("utf-8")
    except Exception as exc:
        logger.error(f"Decryption failed: {exc}")
        return ciphertext


def hash_value(value: str) -> str:
    """
    Create a deterministic SHA-256 HMAC hash of a value for searchable indexing
    of encrypted fields. Uses the encryption key as HMAC secret.
    """
    from app.core.config import settings

    key = settings.ENCRYPTION_KEY.encode()
    return hmac.new(key, value.encode(), hashlib.sha256).hexdigest()


def verify_hash(value: str, hashed: str) -> bool:
    """Verify that a value matches a previously computed hash."""
    return hmac.compare_digest(hash_value(value), hashed)


def generate_encryption_key() -> str:
    """Generate a cryptographically secure 32-byte key encoded as base64."""
    return base64.urlsafe_b64encode(secrets.token_bytes(32)).decode()


def is_encrypted(value: str) -> bool:
    """Check if a value was encrypted by this module."""
    return isinstance(value, str) and (
        value.startswith("enc:") or value.startswith("plain:")
    )


# ─── TOTP MFA Functions ───────────────────────────────────────────────────────


def generate_totp_secret() -> str:
    """Generate a new TOTP secret key (base32 encoded)."""
    if _PYOTP_AVAILABLE:
        return pyotp.random_base32()
    return base64.b32encode(secrets.token_bytes(20)).decode()


def generate_totp_uri(secret: str, email: str) -> str:
    """Generate an otpauth:// URI for QR code generation."""
    from app.core.config import settings

    if _PYOTP_AVAILABLE:
        totp = pyotp.TOTP(secret)
        return totp.provisioning_uri(name=email, issuer_name=settings.MFA_ISSUER)
    issuer = settings.MFA_ISSUER.replace(" ", "%20")
    return f"otpauth://totp/{issuer}:{email}?secret={secret}&issuer={issuer}"


def verify_totp(secret: str, code: str) -> bool:
    """Verify a TOTP code. Allows 1 step drift (30 seconds either way)."""
    if not secret or not code:
        return False
    if _PYOTP_AVAILABLE:
        totp = pyotp.TOTP(secret)
        return totp.verify(code, valid_window=1)
    # Fallback: accept any 6-digit code in dev (NOT for production)
    logger.warning("pyotp not available — TOTP verification is DISABLED (dev mode).")
    return len(code) == 6 and code.isdigit()


def generate_qr_code_base64(uri: str) -> Optional[str]:
    """
    Generate a QR code PNG for the TOTP URI and return it as base64.
    Returns None if qrcode package is unavailable.
    """
    if not _QRCODE_AVAILABLE:
        return None
    try:
        qr = qrcode.QRCode(version=1, box_size=10, border=5)
        qr.add_data(uri)
        qr.make(fit=True)
        img = qr.make_image(fill_color="black", back_color="white")
        buffer = io.BytesIO()
        img.save(buffer, format="PNG")
        return base64.b64encode(buffer.getvalue()).decode()
    except Exception as exc:
        logger.error(f"QR code generation failed: {exc}")
        return None


def generate_backup_codes(count: int = 8) -> list:
    """Generate one-time-use backup recovery codes for MFA."""
    return [secrets.token_hex(5).upper() for _ in range(count)]
