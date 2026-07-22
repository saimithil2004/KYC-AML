import os
import time
import logging
from pathlib import Path
from typing import Dict, Any, List, Optional
from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine
from sqlalchemy.exc import OperationalError

logger = logging.getLogger(__name__)


class DatabaseConnector:
    def __init__(self, db_url_env_name: str = "EXTERNAL_BANK_DB_URL"):
        self.db_url = os.getenv(db_url_env_name, "sqlite:///:memory:")
        self.mock_mode = (
            "placeholder" in self.db_url.lower() or self.db_url == "sqlite:///:memory:"
        )
        self.engine: Optional[Engine] = None
        self._initialize_connection()

    def _initialize_connection(self):
        if self.mock_mode:
            logger.info("Initializing DatabaseConnector in SAFE MOCK MODE.")
            return

        # Setup SQLAlchemy Connection Pooling based on DB type
        pool_args = {}
        if not self.db_url.startswith("sqlite"):
            pool_args = {
                "pool_size": int(os.getenv("DB_POOL_SIZE", "10")),
                "max_overflow": int(os.getenv("DB_MAX_OVERFLOW", "20")),
                "pool_recycle": int(os.getenv("DB_POOL_RECYCLE", "1800")),
                "pool_pre_ping": True,
            }

        # Multi-dialect configuration: Postgres, MySQL, SQL Server, Oracle, SQLite
        # Note: SQLAlchemy parses connection strings like postgresql://, mysql+pymysql://, sqlite://, mssql+pyodbc://, oracle+cx_oracle://
        try:
            self.engine = create_engine(
                self.db_url,
                connect_args=(
                    {"timeout": int(os.getenv("DB_TIMEOUT", "10"))}
                    if self.db_url.startswith("sqlite")
                    else {}
                ),
                **pool_args,
            )
            logger.info(
                f"DatabaseConnector connected successfully to dialect: {self.engine.dialect.name}"
            )
        except Exception as e:
            logger.error(
                f"Failed to initialize database connection pool: {e}. Falling back to MOCK MODE."
            )
            self.mock_mode = True

    def health_check(self) -> Dict[str, Any]:
        """Performs connection monitoring and health status checks."""
        if self.mock_mode:
            return {
                "status": "healthy",
                "mode": "mock_simulation",
                "dialect": "mock",
                "latency_ms": 0.5,
            }

        start = time.time()
        try:
            with self.engine.connect() as conn:
                conn.execute(text("SELECT 1"))
            latency = (time.time() - start) * 1000
            return {
                "status": "healthy",
                "mode": "production_pool",
                "dialect": self.engine.dialect.name,
                "latency_ms": round(latency, 2),
            }
        except Exception as e:
            logger.error(f"Database connection pool health check failed: {e}")
            return {
                "status": "unhealthy",
                "mode": "production_pool",
                "error": str(e),
                "latency_ms": -1,
            }

    def execute_with_retry(
        self,
        query: str,
        params: Optional[Dict[str, Any]] = None,
        retries: int = 3,
        backoff: float = 1.0,
    ) -> List[Dict[str, Any]]:
        """Executes query with exponential backoff retry logic."""
        if self.mock_mode:
            logger.info(f"[MOCK] Skipping raw execute: {query}")
            return []

        last_error = None
        for attempt in range(retries):
            try:
                with self.engine.connect() as conn:
                    result = conn.execute(text(query), params or {})
                    if result.returns_rows:
                        return [dict(row._mapping) for row in result.all()]
                    return []
            except (OperationalError, Exception) as e:
                last_error = e
                wait = backoff * (2**attempt)
                logger.warning(
                    f"Database operation failed (attempt {attempt + 1}/{retries}). Retrying in {wait}s. Error: {e}"
                )
                time.sleep(wait)

        logger.error(f"All database retries exhausted for query: {query}")
        raise last_error or RuntimeError("Database execution failure")

    # ─── SAFE MOCK DATA SIMULATOR ──────────────────────────────────────────────
    def get_mock_customers(self) -> List[Dict[str, Any]]:
        return [
            {
                "ext_id": "ext-cust-101",
                "first_name": "Jack",
                "last_name": "Roberts",
                "email": "jack.roberts@externalbank.com",
                "phone": "+447700900077",
                "dob": "1985-04-12",
                "nationality": "United Kingdom",
                "address_line1": "10 Downing St",
                "city": "London",
                "postcode": "SW1A 2AA",
                "country": "United Kingdom",
                "updated_at": "2026-07-12T00:00:00",
            },
            {
                "ext_id": "ext-cust-102",
                "first_name": "Charlie",
                "last_name": "Brown",
                "email": "charlie.brown@peanuts.org",
                "phone": "+44 7700 900088",
                "dob": "1992-10-30",
                "nationality": "United States",
                "address_line1": "1 Snoopy Lane",
                "city": "Minneapolis",
                "postcode": "55401",
                "country": "United States",
                "updated_at": "2026-07-12T01:00:00",
            },
            {
                "ext_id": "ext-cust-103",
                "first_name": "Isabella",
                "last_name": "Thomas",
                "email": "isabella.thomas@gmail.com",
                "phone": "07700900099",
                "dob": "1994-01-20",
                "nationality": "United Kingdom",
                "address_line1": "45 Regent Street",
                "city": "London",
                "postcode": "W1B 4DY",
                "country": "United Kingdom",
                "updated_at": "2026-07-12T02:00:00",
            },
        ]

    def get_mock_accounts(self) -> List[Dict[str, Any]]:
        return [
            {
                "ext_id": "ext-acc-801",
                "customer_ext_id": "ext-cust-101",
                "account_number": "11223344",
                "sort_code": "204512",
                "balance": 15000.50,
                "currency": "GBP",
                "status": "active",
                "updated_at": "2026-07-12T00:00:00",
            },
            {
                "ext_id": "ext-acc-802",
                "customer_ext_id": "ext-cust-102",
                "account_number": "88776655",
                "sort_code": "309910",
                "balance": 450.00,
                "currency": "USD",
                "status": "active",
                "updated_at": "2026-07-12T01:00:00",
            },
            {
                "ext_id": "ext-acc-803",
                "customer_ext_id": "ext-cust-103",
                "account_number": "99008877",
                "sort_code": "400820",
                "balance": 98000.00,
                "currency": "GBP",
                "status": "active",
                "updated_at": "2026-07-12T02:00:00",
            },
        ]

    def get_mock_transactions(self) -> List[Dict[str, Any]]:
        return [
            {
                "ext_id": "ext-tx-901",
                "account_number": "11223344",
                "sort_code": "204512",
                "receiver_name": "Sovereign Wealth Fund",
                "receiver_account_number": "99887766",
                "receiver_sort_code": "102030",
                "receiver_country": "Switzerland",
                "amount": 250000.00,
                "currency": "GBP",
                "tx_type": "transfer",
                "reference": "Investment Funding",
                "completed_at": "2026-07-12T09:30:00",
                "updated_at": "2026-07-12T09:30:00",
            },
            {
                "ext_id": "ext-tx-902",
                "account_number": "88776655",
                "sort_code": "309910",
                "receiver_name": "Acme Widgets Inc",
                "receiver_account_number": "44332211",
                "receiver_sort_code": "908070",
                "receiver_country": "United States",
                "amount": 1250.00,
                "currency": "USD",
                "tx_type": "transfer",
                "reference": "Invoice #89901",
                "completed_at": "2026-07-12T10:15:00",
                "updated_at": "2026-07-12T10:15:00",
            },
        ]

    def get_mock_companies(self) -> List[Dict[str, Any]]:
        return [
            {
                "ext_id": "ext-comp-501",
                "customer_ext_id": "ext-cust-103",
                "company_name": "Thomas Logistics Ltd",
                "registration_number": "09912345",
                "registered_address": "45 Regent Street, London, W1B 4DY",
                "trading_address": "Unit 5, Heathrow Trade Park, Hounslow",
                "country_of_incorporation": "United Kingdom",
                "incorporation_date": "2018-06-15",
                "sic_code": "49410",
                "updated_at": "2026-07-12T00:00:00",
            }
        ]

    def get_mock_directors_ubos(self) -> Dict[str, List[Dict[str, Any]]]:
        return {
            "directors": [
                {
                    "company_ext_id": "ext-comp-501",
                    "first_name": "Isabella",
                    "last_name": "Thomas",
                    "dob": "1994-01-20",
                    "nationality": "United Kingdom",
                    "appointment_date": "2018-06-15",
                }
            ],
            "ubos": [
                {
                    "company_ext_id": "ext-comp-501",
                    "first_name": "Isabella",
                    "last_name": "Thomas",
                    "dob": "1994-01-20",
                    "nationality": "United Kingdom",
                    "ownership_percentage": 100.0,
                    "control_type": "shares_and_voting_rights",
                }
            ],
        }
