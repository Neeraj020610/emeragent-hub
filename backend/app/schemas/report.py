from decimal import Decimal
from typing import List, Optional
from pydantic import BaseModel


class AccountCreditReport(BaseModel):
    account_id: int
    account_identifier: str
    account_name: str
    available_credits: Decimal
    consumed_credits: Decimal
    total_allocated: Optional[Decimal] = None
    balance_source: str
    is_estimate: bool


class DailyConsumptionPoint(BaseModel):
    date: str
    credits_consumed: Decimal
    jobs_executed: int


class UsageReportSummary(BaseModel):
    total_accounts: int
    connected_accounts: int
    disconnected_accounts: int
    total_available_credits: Decimal
    today_consumption: Decimal
    monthly_consumption: Decimal
    active_build_jobs: int
    failed_build_jobs: int
    account_reports: List[AccountCreditReport]
    consumption_trend: List[DailyConsumptionPoint]
