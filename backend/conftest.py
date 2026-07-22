import os
import sys
from pathlib import Path
import pytest

# Ensure backend directory is in sys.path
_BACKEND_DIR = Path(__file__).resolve().parent
if str(_BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(_BACKEND_DIR))

# Default test environment variables if not already set
os.environ.setdefault("ENV", "test")
os.environ.setdefault(
    "SECRET_KEY", "test_secret_key_validation_must_be_strong_min_length_32_bytes"
)
os.environ.setdefault(
    "ENCRYPTION_KEY", "StrongAESKeyForPIIEncryptionBase64String="
)
os.environ.setdefault("DATABASE_URL", "sqlite+aiosqlite:///./test_ci_db.db")
os.environ.setdefault("REDIS_URL", "redis://localhost:6379/0")
