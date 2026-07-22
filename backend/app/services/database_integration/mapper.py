import logging
from datetime import datetime, date
from typing import Dict, Any, Optional
from uuid import uuid4, UUID
from app.models.models import Customer, Account, Transaction, Company, Director, UBO

logger = logging.getLogger(__name__)


class DataMapper:
    @staticmethod
    def normalize_phone(phone: Optional[str]) -> Optional[str]:
        """Cleans spaces, dashes, and normalizes phone numbers."""
        if not phone:
            return None
        cleaned = "".join(c for c in phone.strip() if c.isdigit() or c == "+")
        # Ensure + prefix if country code is present (e.g. +44)
        return cleaned

    @staticmethod
    def normalize_country(country: Optional[str]) -> str:
        """Standardizes resident resident country names."""
        if not country:
            return "United Kingdom"
        c = country.strip().lower()
        if c in ["uk", "united kingdom", "gb", "gbr"]:
            return "United Kingdom"
        if c in ["us", "usa", "united states", "united states of america"]:
            return "United States"
        return country.strip().title()

    @staticmethod
    def normalize_currency(currency: Optional[str]) -> str:
        """Forces ISO upper codes."""
        if not currency:
            return "GBP"
        return currency.strip().upper()

    @staticmethod
    def parse_date(date_val: Any) -> Optional[date]:
        """Safely parses dates from various input formats."""
        if isinstance(date_val, date):
            return date_val
        if isinstance(date_val, datetime):
            return date_val.date()
        if isinstance(date_val, str) and date_val.strip():
            try:
                # Try standard ISO YYYY-MM-DD
                return datetime.strptime(date_val.strip(), "%Y-%m-%d").date()
            except ValueError:
                pass
            try:
                # Try timestamp format
                return datetime.fromisoformat(date_val.strip()).date()
            except ValueError:
                pass
        return None

    @staticmethod
    def parse_datetime(dt_val: Any) -> Optional[datetime]:
        """Safely parses datetimes."""
        if isinstance(dt_val, datetime):
            return dt_val
        if isinstance(dt_val, date):
            return datetime.combine(dt_val, datetime.min.time())
        if isinstance(dt_val, str) and dt_val.strip():
            try:
                return datetime.fromisoformat(dt_val.strip())
            except ValueError:
                pass
            try:
                return datetime.strptime(dt_val.strip(), "%Y-%m-%d %H:%M:%S")
            except ValueError:
                pass
        return None

    @classmethod
    def map_external_customer(
        cls, ext_data: Dict[str, Any], user_id: Optional[UUID] = None
    ) -> Customer:
        """Maps external customer record to internal SQLAlchemy model."""
        cust = Customer(
            id=uuid4(),
            user_id=user_id,
            customer_type="individual",
            first_name=ext_data.get("first_name"),
            last_name=ext_data.get("last_name"),
            dob=cls.parse_date(ext_data.get("dob")),
            nationality=cls.normalize_country(ext_data.get("nationality")),
            phone_number=cls.normalize_phone(ext_data.get("phone")),
            street_address=ext_data.get("address_line1"),
            city=ext_data.get("city"),
            postal_code=ext_data.get("postcode"),
            country=cls.normalize_country(ext_data.get("country")),
            status="pending_verification",
        )
        return cust

    @classmethod
    def map_external_account(
        cls, ext_data: Dict[str, Any], customer_id: UUID
    ) -> Account:
        """Maps external bank account to internal SQLAlchemy model."""
        acc = Account(
            id=uuid4(),
            customer_id=customer_id,
            account_number=ext_data.get("account_number", "").strip(),
            sort_code=ext_data.get("sort_code", "").replace("-", "").strip(),
            currency=cls.normalize_currency(ext_data.get("currency")),
            balance=float(ext_data.get("balance") or 0.0),
            status="active",
        )
        return acc

    @classmethod
    def map_external_transaction(
        cls, ext_data: Dict[str, Any], sender_account_id: UUID
    ) -> Transaction:
        """Maps external bank transactions to internal SQLAlchemy model."""
        tx = Transaction(
            id=uuid4(),
            sender_account_id=sender_account_id,
            receiver_account_number=ext_data.get("receiver_account_number", "").strip(),
            receiver_sort_code=ext_data.get("receiver_sort_code", "")
            .replace("-", "")
            .strip(),
            receiver_name=ext_data.get("receiver_name", "Unknown").strip(),
            receiver_country=cls.normalize_country(ext_data.get("receiver_country")),
            amount=float(ext_data.get("amount") or 0.0),
            currency=cls.normalize_currency(ext_data.get("currency")),
            transaction_type=ext_data.get("tx_type", "transfer").strip(),
            status="completed",
            reference=ext_data.get("reference"),
            completed_at=cls.parse_datetime(ext_data.get("completed_at")),
        )
        return tx

    @classmethod
    def map_external_company(
        cls, ext_data: Dict[str, Any], customer_id: UUID
    ) -> Company:
        """Maps external company records to internal SQLAlchemy model."""
        comp = Company(
            id=uuid4(),
            customer_id=customer_id,
            company_name=ext_data.get("company_name", "Unknown Company").strip(),
            registration_number=ext_data.get("registration_number", "").strip(),
            registered_address=ext_data.get("registered_address", "").strip(),
            trading_address=ext_data.get("trading_address"),
            country_of_incorporation=cls.normalize_country(
                ext_data.get("country_of_incorporation")
            ),
            incorporation_date=cls.parse_date(ext_data.get("incorporation_date")),
            sic_code=ext_data.get("sic_code"),
            status="active",
        )
        return comp

    @classmethod
    def map_external_director(
        cls, ext_data: Dict[str, Any], company_id: UUID
    ) -> Director:
        """Maps external director records to internal SQLAlchemy model."""
        d = Director(
            id=uuid4(),
            company_id=company_id,
            first_name=ext_data.get("first_name", "").strip(),
            last_name=ext_data.get("last_name", "").strip(),
            dob=cls.parse_date(ext_data.get("dob")),
            nationality=cls.normalize_country(ext_data.get("nationality")),
            appointment_date=cls.parse_date(ext_data.get("appointment_date")),
            is_active=True,
            verification_status="unverified",
        )
        return d

    @classmethod
    def map_external_ubo(cls, ext_data: Dict[str, Any], company_id: UUID) -> UBO:
        """Maps external UBO records to internal SQLAlchemy model."""
        u = UBO(
            id=uuid4(),
            company_id=company_id,
            first_name=ext_data.get("first_name", "").strip(),
            last_name=ext_data.get("last_name", "").strip(),
            dob=cls.parse_date(ext_data.get("dob")),
            nationality=cls.normalize_country(ext_data.get("nationality")),
            ownership_percentage=float(ext_data.get("ownership_percentage") or 0.0),
            control_type=ext_data.get("control_type", "ownership").strip(),
            verification_status="unverified",
        )
        return u
