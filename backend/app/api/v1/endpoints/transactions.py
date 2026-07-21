"""
Transactions API — Phase 8
===========================
Full CRUD + CSV bulk import + pagination/filtering/sorting.
After every import, automatically triggers TransactionMonitoringService
to detect suspicious patterns and create Alerts/Cases.
"""

import csv
import io
import logging
from datetime import datetime, date
from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, UploadFile, File, Request, status
from sqlalchemy import func, and_, or_
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select

from app.core.database import get_db
from app.dependencies.auth import get_current_user, verify_compliance_officer
from app.models.models import Account, Alert, Customer, Transaction, User
from app.schemas.schemas import (
    TransactionCreate, TransactionResponse, TransactionUpdate,
    PaginatedTransactions,
)
from app.services.audit_service import AuditService
from app.services.transaction_monitoring_service import analyse_and_alert

logger = logging.getLogger(__name__)
router = APIRouter()


def _get_client_ip(request: Request) -> str:
    forwarded = request.headers.get("X-Forwarded-For")
    return forwarded.split(",")[0].strip() if forwarded else (request.client.host if request.client else "unknown")


# ── GET /transactions ─────────────────────────────────────────────────────────

@router.get("/", response_model=PaginatedTransactions)
async def list_transactions(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    customer_id: Optional[UUID] = Query(None),
    account_id: Optional[UUID] = Query(None),
    status: Optional[str] = Query(None),
    transaction_type: Optional[str] = Query(None),
    currency: Optional[str] = Query(None),
    min_amount: Optional[float] = Query(None),
    max_amount: Optional[float] = Query(None),
    date_from: Optional[date] = Query(None),
    date_to: Optional[date] = Query(None),
    search: Optional[str] = Query(None, description="Search receiver name or reference"),
    sort_by: str = Query("created_at", description="Field to sort by"),
    sort_dir: str = Query("desc", description="asc or desc"),
    current_user: User = Depends(verify_compliance_officer),
    db: AsyncSession = Depends(get_db),
):
    """List transactions with full pagination, filtering, and sorting."""
    q = select(Transaction)

    # Filter by customer (via account)
    if customer_id:
        account_ids_result = await db.execute(
            select(Account.id).where(Account.customer_id == customer_id)
        )
        acc_ids = [r[0] for r in account_ids_result.fetchall()]
        if not acc_ids:
            return PaginatedTransactions(total=0, page=page, page_size=page_size, items=[])
        q = q.where(Transaction.sender_account_id.in_(acc_ids))

    if account_id:
        q = q.where(Transaction.sender_account_id == account_id)
    if status:
        q = q.where(Transaction.status == status)
    if transaction_type:
        q = q.where(Transaction.transaction_type == transaction_type)
    if currency:
        q = q.where(Transaction.currency == currency.upper())
    if min_amount is not None:
        q = q.where(Transaction.amount >= min_amount)
    if max_amount is not None:
        q = q.where(Transaction.amount <= max_amount)
    if date_from:
        q = q.where(Transaction.created_at >= datetime.combine(date_from, datetime.min.time()))
    if date_to:
        q = q.where(Transaction.created_at <= datetime.combine(date_to, datetime.max.time()))
    if search:
        q = q.where(
            or_(
                Transaction.receiver_name.ilike(f"%{search}%"),
                Transaction.reference.ilike(f"%{search}%"),
                Transaction.receiver_account_number.ilike(f"%{search}%"),
            )
        )

    # Count
    count_q = select(func.count()).select_from(q.subquery())
    total = (await db.execute(count_q)).scalar_one()

    # Sort
    sort_col = getattr(Transaction, sort_by, Transaction.created_at)
    if sort_dir == "asc":
        q = q.order_by(sort_col.asc())
    else:
        q = q.order_by(sort_col.desc())

    # Paginate
    q = q.offset((page - 1) * page_size).limit(page_size)
    items = (await db.execute(q)).scalars().all()

    return PaginatedTransactions(total=total, page=page, page_size=page_size, items=items)


# ── GET /transactions/{id} ────────────────────────────────────────────────────

@router.get("/{transaction_id}", response_model=TransactionResponse)
async def get_transaction(
    transaction_id: UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(Transaction).where(Transaction.id == transaction_id))
    tx = result.scalars().first()
    if not tx:
        raise HTTPException(status_code=404, detail="Transaction not found.")

    # RBAC: customers can only see their own transactions
    if current_user.role == "customer":
        result2 = await db.execute(select(Account).where(Account.id == tx.sender_account_id))
        account = result2.scalars().first()
        if not account:
            raise HTTPException(status_code=404, detail="Transaction not found.")
        result3 = await db.execute(select(Customer).where(Customer.id == account.customer_id))
        customer = result3.scalars().first()
        if not customer or customer.user_id != current_user.id:
            raise HTTPException(status_code=403, detail="Not authorized.")

    return tx


# ── POST /transactions ────────────────────────────────────────────────────────

@router.post("/", response_model=TransactionResponse, status_code=201)
async def create_transaction(
    tx_in: TransactionCreate,
    request: Request,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Create a single transaction and run suspicious activity monitoring."""
    # Resolve sender account
    result = await db.execute(
        select(Account).where(
            Account.account_number == tx_in.sender_account_number,
            Account.sort_code == tx_in.sender_sort_code,
        )
    )
    account = result.scalars().first()
    if not account:
        raise HTTPException(status_code=404, detail=f"Sender account {tx_in.sender_account_number} not found.")

    # RBAC: customers can only create tx for their own account
    if current_user.role == "customer":
        result2 = await db.execute(select(Customer).where(Customer.id == account.customer_id))
        customer = result2.scalars().first()
        if not customer or customer.user_id != current_user.id:
            raise HTTPException(status_code=403, detail="Not authorized to create transactions for this account.")

    tx = Transaction(
        sender_account_id=account.id,
        receiver_account_number=tx_in.receiver_account_number,
        receiver_sort_code=tx_in.receiver_sort_code,
        receiver_name=tx_in.receiver_name,
        receiver_country=tx_in.receiver_country,
        amount=tx_in.amount,
        currency=tx_in.currency.upper(),
        transaction_type=tx_in.transaction_type,
        status="completed",
        reference=tx_in.reference,
        completed_at=datetime.utcnow(),
    )
    db.add(tx)
    await db.flush()  # get tx.id

    # Audit log
    await AuditService.log(
        db=db,
        user_id=current_user.id,
        action="CREATE_TRANSACTION",
        entity_name="transaction",
        entity_id=tx.id,
        new_values={
            "amount": float(tx_in.amount),
            "currency": tx_in.currency,
            "receiver": tx_in.receiver_name,
            "receiver_country": tx_in.receiver_country,
            "type": tx_in.transaction_type,
        },
        ip_address=_get_client_ip(request),
    )

    await db.commit()
    await db.refresh(tx)

    # Run monitoring (will create Alerts + Case if patterns found)
    try:
        await analyse_and_alert(db, tx, account)
    except Exception as exc:
        logger.error(f"Monitoring error for tx {tx.id}: {exc}")

    return tx


# ── POST /transactions/import ─────────────────────────────────────────────────

@router.post("/import", status_code=202)
async def import_transactions_csv(
    file: UploadFile = File(...),
    request: Request = None,
    current_user: User = Depends(verify_compliance_officer),
    db: AsyncSession = Depends(get_db),
):
    """
    Bulk import transactions from a CSV file.
    Expected columns:
        sender_account_number, sender_sort_code, receiver_account_number,
        receiver_sort_code, receiver_name, receiver_country, amount,
        currency, transaction_type, reference (optional)
    """
    if not file.filename.endswith(".csv"):
        raise HTTPException(status_code=400, detail="Only CSV files are accepted.")

    content = await file.read()
    try:
        text = content.decode("utf-8-sig")
    except UnicodeDecodeError:
        text = content.decode("latin-1")

    reader = csv.DictReader(io.StringIO(text))
    required_cols = {
        "sender_account_number", "sender_sort_code",
        "receiver_account_number", "receiver_sort_code",
        "receiver_name", "receiver_country", "amount",
        "currency", "transaction_type",
    }

    imported = 0
    errors = []
    created_txs = []

    rows = list(reader)
    if not rows:
        raise HTTPException(status_code=400, detail="CSV file is empty.")

    # Validate header
    actual_cols = set(rows[0].keys())
    missing = required_cols - actual_cols
    if missing:
        raise HTTPException(
            status_code=400,
            detail=f"Missing CSV columns: {', '.join(sorted(missing))}",
        )

    for row_num, row in enumerate(rows, start=2):
        try:
            # Resolve account
            account_result = await db.execute(
                select(Account).where(
                    Account.account_number == row["sender_account_number"].strip(),
                    Account.sort_code == row["sender_sort_code"].strip(),
                )
            )
            account = account_result.scalars().first()
            if not account:
                errors.append(f"Row {row_num}: Account {row['sender_account_number']} not found — skipped")
                continue

            amount_val = float(row["amount"].strip().replace(",", ""))
            if amount_val <= 0:
                errors.append(f"Row {row_num}: Amount must be > 0 — skipped")
                continue

            tx = Transaction(
                sender_account_id=account.id,
                receiver_account_number=row["receiver_account_number"].strip(),
                receiver_sort_code=row["receiver_sort_code"].strip(),
                receiver_name=row["receiver_name"].strip(),
                receiver_country=row["receiver_country"].strip(),
                amount=amount_val,
                currency=row.get("currency", "GBP").strip().upper(),
                transaction_type=row["transaction_type"].strip().lower(),
                status="completed",
                reference=row.get("reference", "").strip() or None,
                completed_at=datetime.utcnow(),
            )
            db.add(tx)
            await db.flush()

            await AuditService.log(
                db=db,
                user_id=current_user.id,
                action="CSV_IMPORT_TRANSACTION",
                entity_name="transaction",
                entity_id=tx.id,
                new_values={"row": row_num, "amount": amount_val, "file": file.filename},
                ip_address=_get_client_ip(request) if request else None,
            )

            created_txs.append((tx, account))
            imported += 1

        except Exception as exc:
            errors.append(f"Row {row_num}: {exc}")

    await db.commit()

    # Run monitoring for all imported transactions
    monitoring_alerts_total = 0
    for tx, account in created_txs:
        try:
            await db.refresh(tx)
            alerts = await analyse_and_alert(db, tx, account)
            monitoring_alerts_total += len(alerts)
        except Exception as exc:
            logger.error(f"Monitoring error for CSV tx {tx.id}: {exc}")

    return {
        "status": "completed",
        "imported": imported,
        "errors_count": len(errors),
        "alerts_generated": monitoring_alerts_total,
        "errors": errors[:20],  # Return first 20 errors
        "message": f"Successfully imported {imported} transactions. {monitoring_alerts_total} alert(s) generated.",
    }


# ── PUT /transactions/{id} ────────────────────────────────────────────────────

@router.put("/{transaction_id}", response_model=TransactionResponse)
async def update_transaction(
    transaction_id: UUID,
    tx_in: TransactionUpdate,
    request: Request,
    current_user: User = Depends(verify_compliance_officer),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(Transaction).where(Transaction.id == transaction_id))
    tx = result.scalars().first()
    if not tx:
        raise HTTPException(status_code=404, detail="Transaction not found.")

    old_values = {
        "status": tx.status,
        "reference": tx.reference,
    }

    update_data = tx_in.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(tx, field, value)

    await AuditService.log(
        db=db,
        user_id=current_user.id,
        action="UPDATE_TRANSACTION",
        entity_name="transaction",
        entity_id=tx.id,
        old_values=old_values,
        new_values=update_data,
        ip_address=_get_client_ip(request),
    )

    await db.commit()
    await db.refresh(tx)
    return tx


# ── DELETE /transactions/{id} ─────────────────────────────────────────────────

@router.delete("/{transaction_id}", status_code=204)
async def delete_transaction(
    transaction_id: UUID,
    request: Request,
    current_user: User = Depends(verify_compliance_officer),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(Transaction).where(Transaction.id == transaction_id))
    tx = result.scalars().first()
    if not tx:
        raise HTTPException(status_code=404, detail="Transaction not found.")

    await AuditService.log(
        db=db,
        user_id=current_user.id,
        action="DELETE_TRANSACTION",
        entity_name="transaction",
        entity_id=tx.id,
        old_values={"amount": float(tx.amount), "status": tx.status},
        ip_address=_get_client_ip(request),
    )

    await db.delete(tx)
    await db.commit()
    return None


# ── GET /transactions/customer/{customer_id} ──────────────────────────────────

@router.get("/customer/{customer_id}", response_model=PaginatedTransactions)
async def get_customer_transactions(
    customer_id: UUID,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Get all transactions for a specific customer (across all accounts)."""
    # RBAC
    if current_user.role == "customer":
        result = await db.execute(select(Customer).where(Customer.id == customer_id))
        customer = result.scalars().first()
        if not customer or customer.user_id != current_user.id:
            raise HTTPException(status_code=403, detail="Not authorized.")

    acc_result = await db.execute(
        select(Account.id).where(Account.customer_id == customer_id)
    )
    acc_ids = [r[0] for r in acc_result.fetchall()]
    if not acc_ids:
        return PaginatedTransactions(total=0, page=page, page_size=page_size, items=[])

    q = select(Transaction).where(Transaction.sender_account_id.in_(acc_ids))
    total = (await db.execute(select(func.count()).select_from(q.subquery()))).scalar_one()
    items = (await db.execute(
        q.order_by(Transaction.created_at.desc())
        .offset((page - 1) * page_size).limit(page_size)
    )).scalars().all()

    return PaginatedTransactions(total=total, page=page, page_size=page_size, items=items)
