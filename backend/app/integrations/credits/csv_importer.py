import csv
import io
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
from typing import Dict, Any, List, Tuple
from sqlalchemy.orm import Session
from app.models.account import EmergentAccount
from app.models.credit import CreditSnapshot, CreditEvent


class CreditCSVImporter:
    """
    Parses, validates, and ingests credit data from CSV files.
    Ensures safe numeric parsing with Decimal types.
    """

    @staticmethod
    def process_csv(csv_content: str, db: Session, filename: str = "import.csv") -> Dict[str, Any]:
        reader = csv.DictReader(io.StringIO(csv_content))
        total_rows = 0
        successful_imports = 0
        failed_rows = 0
        errors: List[str] = []

        # Required headers check
        required_headers = {"account_identifier", "available_credits"}
        if not reader.fieldnames or not required_headers.issubset(set(reader.fieldnames)):
            return {
                "filename": filename,
                "total_rows": 0,
                "successful_imports": 0,
                "failed_rows": 0,
                "errors": [f"Missing required headers. Required: {list(required_headers)}. Found: {reader.fieldnames}"],
            }

        for row_idx, row in enumerate(reader, start=1):
            total_rows += 1
            account_ident = row.get("account_identifier", "").strip()
            avail_str = row.get("available_credits", "").strip()
            consumed_str = row.get("consumed_credits", "0.0").strip() or "0.0"
            allocated_str = row.get("total_allocated", "").strip()

            if not account_ident:
                failed_rows += 1
                errors.append(f"Row {row_idx}: Missing account_identifier")
                continue

            account = db.query(EmergentAccount).filter(EmergentAccount.account_identifier == account_ident).first()
            if not account:
                failed_rows += 1
                errors.append(f"Row {row_idx}: Account '{account_ident}' not found in hub")
                continue

            try:
                available_credits = Decimal(avail_str)
                consumed_credits = Decimal(consumed_str)
                total_allocated = Decimal(allocated_str) if allocated_str else None
            except InvalidOperation:
                failed_rows += 1
                errors.append(f"Row {row_idx}: Invalid decimal format for credits")
                continue

            snapshot = CreditSnapshot(
                account_id=account.id,
                recorded_at=datetime.now(timezone.utc),
                available_credits=available_credits,
                consumed_credits=consumed_credits,
                total_allocated=total_allocated,
                balance_source="csv_import",
                is_estimate=False,
            )
            db.add(snapshot)

            from app.models.autonomous import AccountCreditBudget
            budget = db.query(AccountCreditBudget).filter(AccountCreditBudget.account_id == account.id).first()
            if budget:
                budget.verified_current_balance = available_credits
                if total_allocated:
                    budget.starting_balance = total_allocated
                elif budget.starting_balance == Decimal("0.0000"):
                    budget.starting_balance = available_credits
                budget.balance_source = "csv_import"
                budget.last_balance_validated_at = datetime.now(timezone.utc)
            else:
                budget = AccountCreditBudget(
                    account_id=account.id,
                    starting_balance=total_allocated or available_credits,
                    verified_current_balance=available_credits,
                    credit_usage=consumed_credits,
                    reserved_credits=Decimal("0.0000"),
                    ceiling_percentage=Decimal("50.00"),
                    balance_source="csv_import",
                    last_balance_validated_at=datetime.now(timezone.utc),
                    is_eligible=True,
                    universal_api_usage=Decimal("0.0000"),
                    platform_build_usage=Decimal("0.0000"),
                )
                db.add(budget)

            event = CreditEvent(
                account_id=account.id,
                event_type="adjustment",
                amount=available_credits,
                balance_after=available_credits,
                notes=f"CSV bulk import from {filename}",
                event_timestamp=datetime.now(timezone.utc),
            )
            db.add(event)
            successful_imports += 1

        db.commit()

        return {
            "filename": filename,
            "total_rows": total_rows,
            "successful_imports": successful_imports,
            "failed_rows": failed_rows,
            "errors": errors,
        }
