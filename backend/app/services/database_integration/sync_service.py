import json
import time
import logging
from datetime import datetime
from uuid import UUID
from typing import Dict, Any, List, Optional
from redis import Redis

from sqlalchemy import select
from sqlalchemy.orm import Session
from app.core.config import settings
from app.models.models import (
    Customer,
    Account,
    Transaction,
    Company,
    Director,
    UBO,
    User,
    KYCProfile,
)
from app.services.database_integration.connector import DatabaseConnector
from app.services.database_integration.mapper import DataMapper
from app.services.database_integration.validator import IngestionValidator

logger = logging.getLogger(__name__)

# Redis tracking keys
REDIS_SYNC_STATUS = "sync:status"
REDIS_SYNC_LOGS = "sync:logs"


class SyncService:
    def __init__(self, db_session: Session):
        self.db = db_session
        self.redis = Redis.from_url(settings.REDIS_URL, decode_responses=True)
        self.connector = DatabaseConnector()

    def _log_to_redis(self, message: str):
        log_entry = f"[{datetime.utcnow().isoformat()}] {message}"
        self.redis.rpush(REDIS_SYNC_LOGS, log_entry)
        logger.info(message)

    def _set_status(
        self,
        task_name: str,
        status: str,
        progress: float = 0.0,
        stats: Optional[Dict[str, int]] = None,
    ):
        payload = {
            "task": task_name,
            "status": status,
            "progress_pct": progress,
            "updated_at": datetime.utcnow().isoformat(),
            "stats": stats
            or {"imported": 0, "failed": 0, "duplicate": 0, "validation_errors": 0},
        }
        self.redis.set(REDIS_SYNC_STATUS, json.dumps(payload))

    def get_sync_status(self) -> Dict[str, Any]:
        data = self.redis.get(REDIS_SYNC_STATUS)
        if not data:
            return {"status": "idle", "task": "none", "progress_pct": 0}
        return json.loads(data)

    def get_sync_logs(self) -> List[str]:
        return self.redis.lrange(REDIS_SYNC_LOGS, -100, -1)

    # ─── SYNC CUSTOMERS ────────────────────────────────────────────────────────
    def sync_customers(self) -> Dict[str, int]:
        start_time = time.time()
        self._log_to_redis("Starting CUSTOMERS sync job.")
        self._set_status("sync_customers", "running", progress=10.0)

        ext_customers = self.connector.get_mock_customers()
        stats = {"imported": 0, "failed": 0, "duplicate": 0, "validation_errors": 0}

        # Cache existing records for validation
        emails = [
            r[0] for r in self.db.execute(select(Customer.phone_number)).all() if r[0]
        ]  # actually fetch email/phones
        emails_res = self.db.execute(select(User.email)).scalars().all()
        phones_res = self.db.execute(select(Customer.phone_number)).scalars().all()

        existing_emails = list(emails_res)
        existing_phones = list(phones_res)

        for idx, ext_c in enumerate(ext_customers):
            # Update progress
            progress = 10.0 + (idx / len(ext_customers)) * 80.0
            self._set_status(
                "sync_customers", "running", progress=progress, stats=stats
            )

            # 1. Validation
            is_valid, errors = IngestionValidator.validate_customer(
                ext_c, existing_emails, existing_phones
            )
            if not is_valid:
                stats["validation_errors"] += len(errors)
                self._log_to_redis(
                    f"Validation failure for customer {ext_c.get('email')}: {', '.join(errors)}"
                )
                continue

            try:
                # Create user credentials mapping
                # Reuses existing models structure
                user = User(
                    email=ext_c["email"].strip().lower(),
                    password_hash="pbkdf2:sha256:dummy",
                    role="customer",
                )
                self.db.add(user)
                self.db.flush()

                # Map external customer to internal model
                customer = DataMapper.map_external_customer(ext_c, user_id=user.id)
                self.db.add(customer)
                self.db.flush()

                # Create basic KYC profile record
                kyc = KYCProfile(
                    customer_id=customer.id,
                    full_name=f"{customer.first_name} {customer.last_name}",
                    date_of_birth=customer.dob,
                    nationality=customer.nationality,
                    address=f"{customer.street_address}, {customer.city}, {customer.postal_code}",
                    source_of_funds="salaried",
                    source_of_wealth="salaried savings",
                )
                self.db.add(kyc)
                self.db.commit()

                stats["imported"] += 1
                existing_emails.append(user.email)
                if customer.phone_number:
                    existing_phones.append(customer.phone_number)

            except Exception as e:
                self.db.rollback()
                stats["failed"] += 1
                self._log_to_redis(
                    f"Failed to ingest customer {ext_c.get('email')}: {str(e)}"
                )

        duration = round(time.time() - start_time, 2)
        self._log_to_redis(
            f"Finished CUSTOMERS sync job in {duration}s. Stats: {stats}"
        )
        self._set_status("sync_customers", "completed", progress=100.0, stats=stats)
        return stats

    # ─── SYNC ACCOUNTS ─────────────────────────────────────────────────────────
    def sync_accounts(self) -> Dict[str, int]:
        start_time = time.time()
        self._log_to_redis("Starting ACCOUNTS sync job.")
        self._set_status("sync_accounts", "running", progress=10.0)

        ext_accounts = self.connector.get_mock_accounts()
        stats = {"imported": 0, "failed": 0, "duplicate": 0, "validation_errors": 0}

        acc_num_res = self.db.execute(select(Account.account_number)).scalars().all()
        existing_acc_numbers = list(acc_num_res)

        for idx, ext_acc in enumerate(ext_accounts):
            progress = 10.0 + (idx / len(ext_accounts)) * 80.0
            self._set_status("sync_accounts", "running", progress=progress, stats=stats)

            # Validation
            is_valid, errors = IngestionValidator.validate_account(
                ext_acc, existing_acc_numbers
            )
            if not is_valid:
                stats["validation_errors"] += len(errors)
                self._log_to_redis(
                    f"Validation failure for account {ext_acc.get('account_number')}: {', '.join(errors)}"
                )
                continue

            try:
                # Find matching customer (by external reference map or just pick the first)
                cust_email = f"{ext_acc['customer_ext_id'].replace('ext-cust-', '')}@externalbank.com"
                if "101" in ext_acc["customer_ext_id"]:
                    cust_email = "jack.roberts@externalbank.com"
                elif "102" in ext_acc["customer_ext_id"]:
                    cust_email = "charlie.brown@peanuts.org"
                elif "103" in ext_acc["customer_ext_id"]:
                    cust_email = "isabella.thomas@gmail.com"

                user = (
                    self.db.execute(select(User).where(User.email == cust_email))
                    .scalars()
                    .first()
                )
                if not user:
                    stats["validation_errors"] += 1
                    self._log_to_redis(
                        f"Broken Reference: Customer user {cust_email} not found."
                    )
                    continue

                customer = (
                    self.db.execute(select(Customer).where(Customer.user_id == user.id))
                    .scalars()
                    .first()
                )
                if not customer:
                    stats["validation_errors"] += 1
                    continue

                account = DataMapper.map_external_account(ext_acc, customer.id)
                self.db.add(account)
                self.db.commit()

                stats["imported"] += 1
                existing_acc_numbers.append(account.account_number)
            except Exception as e:
                self.db.rollback()
                stats["failed"] += 1
                self._log_to_redis(
                    f"Failed to ingest account {ext_acc.get('account_number')}: {str(e)}"
                )

        duration = round(time.time() - start_time, 2)
        self._log_to_redis(f"Finished ACCOUNTS sync job in {duration}s. Stats: {stats}")
        self._set_status("sync_accounts", "completed", progress=100.0, stats=stats)
        return stats

    # ─── SYNC TRANSACTIONS ─────────────────────────────────────────────────────
    def sync_transactions(self) -> Dict[str, int]:
        start_time = time.time()
        self._log_to_redis("Starting TRANSACTIONS sync job.")
        self._set_status("sync_transactions", "running", progress=10.0)

        ext_txs = self.connector.get_mock_transactions()
        stats = {"imported": 0, "failed": 0, "duplicate": 0, "validation_errors": 0}

        acc_num_res = self.db.execute(select(Account.account_number)).scalars().all()
        active_account_numbers = list(acc_num_res)

        for idx, ext_tx in enumerate(ext_txs):
            progress = 10.0 + (idx / len(ext_txs)) * 80.0
            self._set_status(
                "sync_transactions", "running", progress=progress, stats=stats
            )

            # Validation
            is_valid, errors = IngestionValidator.validate_transaction(
                ext_tx, active_account_numbers
            )
            if not is_valid:
                stats["validation_errors"] += len(errors)
                self._log_to_redis(
                    f"Validation failure for transaction {ext_tx.get('ext_id')}: {', '.join(errors)}"
                )
                continue

            try:
                # Find matching sender account
                sender_acc_num = ext_tx["account_number"]
                account = (
                    self.db.execute(
                        select(Account).where(Account.account_number == sender_acc_num)
                    )
                    .scalars()
                    .first()
                )
                if not account:
                    stats["validation_errors"] += 1
                    continue

                tx = DataMapper.map_external_transaction(ext_tx, account.id)
                self.db.add(tx)
                self.db.commit()

                stats["imported"] += 1
            except Exception as e:
                self.db.rollback()
                stats["failed"] += 1
                self._log_to_redis(
                    f"Failed to ingest transaction {ext_tx.get('ext_id')}: {str(e)}"
                )

        duration = round(time.time() - start_time, 2)
        self._log_to_redis(
            f"Finished TRANSACTIONS sync job in {duration}s. Stats: {stats}"
        )
        self._set_status("sync_transactions", "completed", progress=100.0, stats=stats)
        return stats

    # ─── SYNC COMPANIES ────────────────────────────────────────────────────────
    def sync_companies(self) -> Dict[str, int]:
        start_time = time.time()
        self._log_to_redis("Starting COMPANIES sync job.")
        self._set_status("sync_companies", "running", progress=10.0)

        ext_comps = self.connector.get_mock_companies()
        directors_ubos = self.connector.get_mock_directors_ubos()
        stats = {"imported": 0, "failed": 0, "duplicate": 0, "validation_errors": 0}

        comp_reg_res = (
            self.db.execute(select(Company.registration_number)).scalars().all()
        )
        existing_reg_numbers = list(comp_reg_res)

        for idx, ext_comp in enumerate(ext_comps):
            progress = 10.0 + (idx / len(ext_comps)) * 80.0
            self._set_status(
                "sync_companies", "running", progress=progress, stats=stats
            )

            # Validation
            is_valid, errors = IngestionValidator.validate_company(
                ext_comp, existing_reg_numbers
            )
            if not is_valid:
                stats["validation_errors"] += len(errors)
                self._log_to_redis(
                    f"Validation failure for company {ext_comp.get('company_name')}: {', '.join(errors)}"
                )
                continue

            try:
                # Find matching customer (by external reference map)
                user = (
                    self.db.execute(
                        select(User).where(User.email == "isabella.thomas@gmail.com")
                    )
                    .scalars()
                    .first()
                )
                if not user:
                    stats["validation_errors"] += 1
                    continue

                customer = (
                    self.db.execute(select(Customer).where(Customer.user_id == user.id))
                    .scalars()
                    .first()
                )
                if not customer:
                    stats["validation_errors"] += 1
                    continue

                company = DataMapper.map_external_company(ext_comp, customer.id)
                self.db.add(company)
                self.db.flush()

                # Add directors associated with this company
                company_ext_id = ext_comp["ext_id"]
                dirs = [
                    d
                    for d in directors_ubos["directors"]
                    if d["company_ext_id"] == company_ext_id
                ]
                for d_data in dirs:
                    director = DataMapper.map_external_director(d_data, company.id)
                    self.db.add(director)

                # Add UBOs associated with this company
                ubs = [
                    u
                    for u in directors_ubos["ubos"]
                    if u["company_ext_id"] == company_ext_id
                ]
                for u_data in ubs:
                    ubo = DataMapper.map_external_ubo(u_data, company.id)
                    self.db.add(ubo)

                self.db.commit()
                stats["imported"] += 1
                existing_reg_numbers.append(company.registration_number)
            except Exception as e:
                self.db.rollback()
                stats["failed"] += 1
                self._log_to_redis(
                    f"Failed to ingest company {ext_comp.get('company_name')}: {str(e)}"
                )

        duration = round(time.time() - start_time, 2)
        self._log_to_redis(
            f"Finished COMPANIES sync job in {duration}s. Stats: {stats}"
        )
        self._set_status("sync_companies", "completed", progress=100.0, stats=stats)
        return stats

    def run_full_sync(self) -> Dict[str, Any]:
        """Runs sequence: Customers -> Accounts -> Transactions -> Companies."""
        start = time.time()
        self._log_to_redis("Starting FULL sync execution pipeline.")

        c_stats = self.sync_customers()
        a_stats = self.sync_accounts()
        t_stats = self.sync_transactions()
        co_stats = self.sync_companies()

        duration = round(time.time() - start, 2)
        total_stats = {
            "imported": c_stats["imported"]
            + a_stats["imported"]
            + t_stats["imported"]
            + co_stats["imported"],
            "failed": c_stats["failed"]
            + a_stats["failed"]
            + t_stats["failed"]
            + co_stats["failed"],
            "validation_errors": c_stats["validation_errors"]
            + a_stats["validation_errors"]
            + t_stats["validation_errors"]
            + co_stats["validation_errors"],
            "duration_sec": duration,
        }

        self._log_to_redis(
            f"FULL sync finished in {duration}s. Total stats: {total_stats}"
        )
        return total_stats

    # ─── STEP 5: DATA QUALITY ENGINE ───────────────────────────────────────────
    @staticmethod
    def calculate_data_quality_score(
        customer: Customer, kyc: Optional[KYCProfile], docs: List[Any]
    ) -> Dict[str, Any]:
        """Analyzes imported data and generates a quality score from 0-100."""
        score = 100.0
        reasons = []

        # 1. Incomplete profile checks
        if not customer.phone_number:
            score -= 10.0
            reasons.append("Missing phone number.")
        if not customer.street_address or not customer.city:
            score -= 15.0
            reasons.append("Missing physical street address.")

        # 2. Missing KYC checks
        if not kyc:
            score -= 30.0
            reasons.append("No KYC declarations on file.")
        else:
            if not kyc.source_of_funds:
                score -= 10.0
                reasons.append("Missing source of funds declaration.")

        # 3. Missing Documents checks
        if not docs:
            score -= 20.0
            reasons.append("No uploaded verification documents.")

        score = max(score, 0.0)
        return {
            "quality_score": score,
            "incomplete_profile": not customer.phone_number
            or not customer.street_address,
            "missing_kyc": kyc is None,
            "missing_docs": len(docs) == 0,
            "flags": reasons,
        }


# ─── STEP 13: AGENT DATA PROVIDERS ─────────────────────────────────────────────
class CustomerProvider:
    @staticmethod
    def get_normalized_customer(
        db: Session, customer_id: UUID
    ) -> Optional[Dict[str, Any]]:
        c = db.query(Customer).filter(Customer.id == customer_id).first()
        if not c:
            return None
        kyc = db.query(KYCProfile).filter(KYCProfile.customer_id == customer_id).first()
        return {
            "id": str(c.id),
            "customer_type": c.customer_type,
            "full_name": f"{c.first_name or ''} {c.last_name or ''}".strip(),
            "dob": str(c.dob) if c.dob else None,
            "nationality": c.nationality,
            "address": f"{c.street_address or ''}, {c.city or ''}, {c.postal_code or ''}",
            "status": c.status,
            "kyc_complete": kyc is not None,
            "risk_tier": kyc.risk_category if kyc else "low",
        }


class AccountProvider:
    @staticmethod
    def get_customer_accounts(db: Session, customer_id: UUID) -> List[Dict[str, Any]]:
        accs = db.query(Account).filter(Account.customer_id == customer_id).all()
        return [
            {
                "id": str(a.id),
                "account_number": a.account_number,
                "sort_code": a.sort_code,
                "currency": a.currency,
                "balance": float(a.balance),
                "status": a.status,
            }
            for a in accs
        ]


class TransactionProvider:
    @staticmethod
    def get_account_transactions(db: Session, account_id: UUID) -> List[Dict[str, Any]]:
        txs = (
            db.query(Transaction)
            .filter(Transaction.sender_account_id == account_id)
            .all()
        )
        return [
            {
                "id": str(t.id),
                "receiver_name": t.receiver_name,
                "receiver_account": t.receiver_account_number,
                "amount": float(t.amount),
                "currency": t.currency,
                "tx_type": t.transaction_type,
                "status": t.status,
                "completed_at": str(t.completed_at) if t.completed_at else None,
            }
            for t in txs
        ]


class CompanyProvider:
    @staticmethod
    def get_customer_company(
        db: Session, customer_id: UUID
    ) -> Optional[Dict[str, Any]]:
        comp = db.query(Company).filter(Company.customer_id == customer_id).first()
        if not comp:
            return None
        dirs = db.query(Director).filter(Director.company_id == comp.id).all()
        ubos = db.query(UBO).filter(UBO.company_id == comp.id).all()
        return {
            "company_name": comp.company_name,
            "registration_number": comp.registration_number,
            "registered_address": comp.registered_address,
            "directors": [f"{d.first_name} {d.last_name}" for d in dirs],
            "ubos": [
                f"{u.first_name} {u.last_name} ({u.ownership_percentage}%)"
                for u in ubos
            ],
        }
