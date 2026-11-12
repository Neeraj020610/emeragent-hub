from datetime import datetime
from decimal import Decimal
from typing import Optional, List
from pydantic import BaseModel


class CreditSnapshotResponse(BaseModel):
    id: int
    account_id: int
    recorded_at: datetime
    available_credits: Decimal
    consumed_credits: Decimal
    total_allocated: Optional[Decimal] = None
    balance_source: str
    is_estimate: bool
    created_at: datetime

    class Config:
        from_attributes = True


class CreditEventCreate(BaseModel):
    account_id: int
    event_type: str  # consume, deposit, adjustment, refund
    amount: Decimal
    job_id: Optional[int] = None
    notes: Optional[str] = None


class CreditEventResponse(BaseModel):
    id: int
    account_id: int
    event_type: str
    amount: Decimal
    balance_after: Optional[Decimal] = None
    job_id: Optional[int] = None
    user_id: Optional[int] = None
    notes: Optional[str] = None
    event_timestamp: datetime
    created_at: datetime

    class Config:
        from_attributes = True


class CreditManualEntryRequest(BaseModel):
    account_id: int
    available_credits: Decimal
    consumed_credits: Optional[Decimal] = Decimal("0.0000")
    total_allocated: Optional[Decimal] = None
    notes: Optional[str] = None


class CSVImportSummary(BaseModel):
    filename: str
    total_rows: int
    successful_imports: int
    failed_rows: int
    errors: List[str]
