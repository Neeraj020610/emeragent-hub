from typing import List, Optional
from datetime import datetime, timezone
from decimal import Decimal
from fastapi import APIRouter, Depends, HTTPException, Request, UploadFile, File, Form, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.user import User
from app.models.account import EmergentAccount
from app.models.credit import CreditSnapshot, CreditEvent
from app.schemas.credit import (
    CreditSnapshotResponse,
    CreditEventCreate,
    CreditEventResponse,
    CreditManualEntryRequest,
    CSVImportSummary,
)
from app.integrations.credits.csv_importer import CreditCSVImporter
from app.dependencies import get_current_user, require_role, record_audit

router = APIRouter()


@router.get("/snapshots", response_model=List[CreditSnapshotResponse])
def list_credit_snapshots(
    account_id: Optional[int] = None,
    limit: int = 50,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    query = db.query(CreditSnapshot)
    if account_id:
        query = query.filter(CreditSnapshot.account_id == account_id)
    return query.order_by(CreditSnapshot.recorded_at.desc()).limit(limit).all()


@router.get("/events", response_model=List[CreditEventResponse])
def list_credit_events(
    account_id: Optional[int] = None,
    limit: int = 50,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    query = db.query(CreditEvent)
    if account_id:
        query = query.filter(CreditEvent.account_id == account_id)
    return query.order_by(CreditEvent.event_timestamp.desc()).limit(limit).all()


@router.post("/manual", response_model=CreditSnapshotResponse, status_code=status.HTTP_201_CREATED)
def record_manual_credit_entry(
    request: Request,
    payload: CreditManualEntryRequest,
    current_user: User = Depends(require_role(["ADMIN", "MANAGER"])),
    db: Session = Depends(get_db),
):
    account = db.query(EmergentAccount).filter(EmergentAccount.id == payload.account_id).first()
    if not account:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Account not found.")

    snapshot = CreditSnapshot(
        account_id=account.id,
        recorded_at=datetime.now(timezone.utc),
        available_credits=payload.available_credits,
        consumed_credits=payload.consumed_credits or Decimal("0.0000"),
        total_allocated=payload.total_allocated,
        balance_source="manual",
        is_estimate=False,
    )
    db.add(snapshot)

    # Sync AccountCreditBudget
    from app.models.autonomous import AccountCreditBudget
    budget = db.query(AccountCreditBudget).filter(AccountCreditBudget.account_id == account.id).first()
    if budget:
        budget.verified_current_balance = payload.available_credits
        if payload.total_allocated:
            budget.starting_balance = payload.total_allocated
        elif budget.starting_balance == Decimal("0.0000"):
            budget.starting_balance = payload.available_credits
        budget.balance_source = "manual"
        budget.last_balance_validated_at = datetime.now(timezone.utc)
    else:
        budget = AccountCreditBudget(
            account_id=account.id,
            starting_balance=payload.total_allocated or payload.available_credits,
            verified_current_balance=payload.available_credits,
            credit_usage=Decimal("0.0000"),
            reserved_credits=Decimal("0.0000"),
            ceiling_percentage=Decimal("50.00"),
            balance_source="manual",
            last_balance_validated_at=datetime.now(timezone.utc),
            is_eligible=True,
            universal_api_usage=Decimal("0.0000"),
            platform_build_usage=Decimal("0.0000"),
        )
        db.add(budget)

    # Also log credit event
    event = CreditEvent(
        account_id=account.id,
        event_type="adjustment",
        amount=payload.available_credits,
        balance_after=payload.available_credits,
        user_id=current_user.id,
        notes=payload.notes or "Manual administrative entry",
        event_timestamp=datetime.now(timezone.utc),
    )
    db.add(event)
    db.commit()
    db.refresh(snapshot)

    record_audit(
        db=db,
        action="credit_manual_entry",
        resource_type="credit_snapshot",
        resource_id=str(snapshot.id),
        user_id=current_user.id,
        ip_address=request.client.host if request.client else None,
        details=f"Recorded manual balance of {payload.available_credits} for account {account.account_identifier}",
    )

    return snapshot


@router.post("/import-csv", response_model=CSVImportSummary)
async def import_credits_csv(
    request: Request,
    file: UploadFile = File(...),
    current_user: User = Depends(require_role(["ADMIN", "MANAGER"])),
    db: Session = Depends(get_db),
):
    contents = await file.read()
    try:
        csv_text = contents.decode("utf-8")
    except UnicodeDecodeError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Uploaded CSV file is not valid UTF-8 text.",
        )

    summary = CreditCSVImporter.process_csv(csv_text, db, filename=file.filename or "import.csv")

    record_audit(
        db=db,
        action="credit_csv_import",
        resource_type="credit_snapshot",
        user_id=current_user.id,
        ip_address=request.client.host if request.client else None,
        details=f"Imported CSV {summary['filename']}: {summary['successful_imports']} successful, {summary['failed_rows']} failed",
    )

    return CSVImportSummary(**summary)
