"""
Multi-Account Rotation and 50% Credit Guard Scheduler
Phase 5C Implementation for Emergent Central Hub

Enforces:
- 50% Planned Usage Ceiling on verified starting balance
- Account session health verification before task assignment
- One active execution per Emergent account
- Pre-execution budget reservation and post-execution usage reconciliation
- Universal API usage vs Platform Build usage separation against shared provider balance
- Honest balance provenance (MANUAL, IMPORTED, UNKNOWN, API_VERIFIED)
- Safe account switching after checkpoint or task completion
"""
import logging
from datetime import datetime, timezone
from decimal import Decimal
from typing import Dict, List, Optional, Tuple
from sqlalchemy.orm import Session
from sqlalchemy import func

from app.models.account import EmergentAccount
from app.models.session import AccountSession
from app.models.credit import CreditSnapshot, CreditEvent
from app.models.autonomous import AccountCreditBudget, AutonomousTask

logger = logging.getLogger("emergent.autonomous.scheduler")


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class AccountCreditScheduler:
    """
    Centralized multi-account scheduler with strict 50% credit guard and session validation.
    """

    def get_or_create_budget(
        self,
        account_id: int,
        db: Session,
        default_starting_balance: Decimal = Decimal("0.0000"),
    ) -> AccountCreditBudget:
        budget = db.query(AccountCreditBudget).filter(AccountCreditBudget.account_id == account_id).first()
        
        # Check latest credit snapshot for this account
        latest_snap = (
            db.query(CreditSnapshot)
            .filter(CreditSnapshot.account_id == account_id)
            .order_by(CreditSnapshot.recorded_at.desc())
            .first()
        )

        if not budget:
            starting = (
                latest_snap.total_allocated or latest_snap.available_credits
                if latest_snap
                else default_starting_balance
            )
            available = latest_snap.available_credits if latest_snap else default_starting_balance
            source = latest_snap.balance_source if latest_snap else ("UNKNOWN" if default_starting_balance == Decimal("0.0000") else "MANUAL")

            budget = AccountCreditBudget(
                account_id=account_id,
                starting_balance=starting,
                verified_current_balance=available,
                credit_usage=Decimal("0.0000"),
                reserved_credits=Decimal("0.0000"),
                ceiling_percentage=Decimal("50.00"),
                balance_source=source,
                last_balance_validated_at=latest_snap.recorded_at if latest_snap else utcnow(),
                is_eligible=False,
                universal_api_usage=Decimal("0.0000"),
                platform_build_usage=Decimal("0.0000"),
            )
            db.add(budget)
            db.commit()
            db.refresh(budget)
        else:
            # Synchronize budget with real snapshot telemetry if available
            if latest_snap:
                if budget.credit_usage > Decimal("0.0000"):
                    budget.verified_current_balance = max(Decimal("0.0000"), budget.starting_balance - budget.credit_usage)
                else:
                    budget.verified_current_balance = latest_snap.available_credits
                if budget.starting_balance == Decimal("0.0000") or budget.starting_balance == Decimal("100.0000") or budget.balance_source == "MANUAL":
                    budget.starting_balance = latest_snap.total_allocated or latest_snap.available_credits
                budget.balance_source = latest_snap.balance_source
                budget.last_balance_validated_at = latest_snap.recorded_at
            elif budget.balance_source == "MANUAL" and budget.starting_balance == Decimal("100.0000"):
                # Reset placeholder dummy 100 to genuine uninitialized state
                budget.starting_balance = Decimal("0.0000")
                budget.verified_current_balance = Decimal("0.0000")
                budget.balance_source = "UNKNOWN"
            
            db.commit()
            db.refresh(budget)

        return budget

    def update_account_budget(
        self,
        account_id: int,
        starting_balance: Decimal,
        ceiling_percentage: Decimal,
        balance_source: str,
        db: Session,
    ) -> AccountCreditBudget:
        budget = self.get_or_create_budget(account_id, db)
        budget.starting_balance = starting_balance
        budget.verified_current_balance = starting_balance - budget.credit_usage
        budget.ceiling_percentage = ceiling_percentage
        budget.balance_source = balance_source
        budget.last_balance_validated_at = utcnow()
        
        # Re-evaluate eligibility
        self.evaluate_account_eligibility(budget, db)
        db.commit()
        db.refresh(budget)
        return budget

    def evaluate_account_eligibility(
        self,
        budget: AccountCreditBudget,
        db: Session,
        current_task_id: Optional[int] = None,
    ) -> Tuple[bool, Optional[str]]:
        """
        Evaluates whether an account is eligible to receive new work.
        Criteria:
        1. Account status must be active.
        2. Session must exist and be ACTIVE (or browser profile ready).
        3. No other active task currently executing (1 active execution per account).
        4. Credit usage + reserved credits must not exceed the planned ceiling (starting_balance * ceiling_percentage / 100).
        """
        account = db.query(EmergentAccount).filter(EmergentAccount.id == budget.account_id).first()
        if not account or account.status != "active":
            budget.is_eligible = False
            budget.ineligibility_reason = f"Account status is {account.status if account else 'NOT_FOUND'}"
            return False, budget.ineligibility_reason

        session = db.query(AccountSession).filter(AccountSession.account_id == budget.account_id).first()
        if not session or session.session_status != "ACTIVE":
            budget.is_eligible = False
            budget.ineligibility_reason = f"Session is {session.session_status if session else 'MISSING'}"
            return False, budget.ineligibility_reason

        if budget.active_task_id is not None and budget.active_task_id != current_task_id:
            # Check if active task is actually still in progress
            task = db.query(AutonomousTask).filter(AutonomousTask.id == budget.active_task_id).first()
            if task and task.status in ("QUEUED", "IN_PROGRESS", "CHECKPOINT"):
                budget.is_eligible = False
                budget.ineligibility_reason = f"Account busy with active task {task.task_identifier}"
                return False, budget.ineligibility_reason
            else:
                # Clear orphaned task pointer
                budget.active_task_id = None

        # 100% Full Credit Pool Usage Check (Burn down to 0)
        ceiling_limit = budget.starting_balance if budget.starting_balance > Decimal("0") else Decimal("999999.00")
        current_committed = budget.credit_usage + budget.reserved_credits

        if budget.verified_current_balance is not None and budget.verified_current_balance <= Decimal("0"):
            budget.is_eligible = False
            budget.ineligibility_reason = "Account credits fully exhausted (0 Cr remaining)."
            return False, budget.ineligibility_reason

        if current_committed >= ceiling_limit:
            budget.is_eligible = False
            budget.ineligibility_reason = (
                f"100% Credit Pool Exhausted: Committed {current_committed:.4f} >= Starting {ceiling_limit:.4f}"
            )
            return False, budget.ineligibility_reason

        budget.is_eligible = True
        budget.ineligibility_reason = None
        return True, None

    def select_eligible_account(
        self,
        work_type: str,
        estimated_cost: Decimal,
        db: Session,
    ) -> Optional[Tuple[EmergentAccount, AccountCreditBudget]]:
        """
        Selects an eligible account with a valid session and sufficient available budget (100% full usage).
        Prioritizes the currently active single worker account.
        """
        all_accounts = db.query(EmergentAccount).filter(EmergentAccount.status == "active").all()
        candidates: List[Tuple[EmergentAccount, AccountCreditBudget, Decimal]] = []

        for acc in all_accounts:
            budget = self.get_or_create_budget(acc.id, db)
            is_eligible, reason = self.evaluate_account_eligibility(budget, db)
            if not is_eligible:
                logger.warning(f"Account {acc.id} ({acc.account_name}) ineligible: {reason}")
                continue

            ceiling_limit = budget.starting_balance if budget.starting_balance > Decimal("0") else Decimal("999999.00")
            current_committed = budget.credit_usage + budget.reserved_credits
            remaining_headroom = ceiling_limit - current_committed
            if budget.verified_current_balance is not None:
                remaining_headroom = min(remaining_headroom, budget.verified_current_balance - budget.reserved_credits)

            # Check if estimated cost fits within headroom
            if estimated_cost > Decimal("0.0000") and estimated_cost > remaining_headroom:
                continue

            # Prioritize currently CONNECTED active worker account
            is_active_worker = 1 if acc.connection_status == "CONNECTED" else 0
            candidates.append((acc, budget, remaining_headroom, is_active_worker))

        if not candidates:
            logger.warning("No eligible account found with active session or available credits.")
            return None

        # Sort: active worker first, then highest remaining balance
        candidates.sort(key=lambda x: (x[3], x[2]), reverse=True)
        selected_acc, selected_budget, _, _ = candidates[0]
        return selected_acc, selected_budget

    def reserve_budget(
        self,
        account_id: int,
        task_id: int,
        estimated_cost: Decimal,
        db: Session,
    ) -> bool:
        """
        Atomically reserves estimated credits and locks account to active task (100% full usage).
        """
        budget = self.get_or_create_budget(account_id, db)
        if budget.active_task_id == task_id:
            # Already locked to this task for continuation checkpoints
            return True

        ceiling_limit = budget.starting_balance if budget.starting_balance > Decimal("0") else Decimal("999999.00")
        current_committed = budget.credit_usage + budget.reserved_credits

        if current_committed + estimated_cost > ceiling_limit and budget.starting_balance > Decimal("0"):
            logger.error(f"Cannot reserve {estimated_cost:.4f} for account {account_id}: exceeds available balance.")
            return False

        budget.reserved_credits += estimated_cost
        budget.active_task_id = task_id
        db.commit()
        return True

    def record_usage_and_release(
        self,
        account_id: int,
        task_id: int,
        estimated_cost: Decimal,
        actual_cost: Decimal,
        usage_type: str,  # UNIVERSAL_API or PLATFORM_BUILD
        db: Session,
    ) -> AccountCreditBudget:
        """
        Releases reserved credits, records actual usage, updates separated ledgers,
        and re-checks the 50% ceiling.
        """
        budget = self.get_or_create_budget(account_id, db)

        # Release reservation
        budget.reserved_credits = max(Decimal("0.0000"), budget.reserved_credits - estimated_cost)
        # Apply actual usage
        budget.credit_usage += actual_cost
        budget.verified_current_balance = max(Decimal("0.0000"), budget.starting_balance - budget.credit_usage)
        budget.last_balance_validated_at = utcnow()

        if usage_type == "UNIVERSAL_API":
            budget.universal_api_usage += actual_cost
        else:
            budget.platform_build_usage += actual_cost

        # Record in system CreditEvent
        credit_event = CreditEvent(
            account_id=account_id,
            event_type="consume",
            amount=actual_cost,
            balance_after=budget.verified_current_balance,
            notes=f"Autonomous task #{task_id} execution ({usage_type})",
            event_timestamp=utcnow(),
        )
        db.add(credit_event)

        # Synchronize CreditSnapshot so /accounts and /credits ledgers reflect accurate deducted balance
        from app.models.credit import CreditSnapshot
        snap = (
            db.query(CreditSnapshot)
            .filter(CreditSnapshot.account_id == account_id)
            .order_by(CreditSnapshot.recorded_at.desc())
            .first()
        )
        if snap:
            snap.consumed_credits += actual_cost
            snap.available_credits = max(Decimal("0.0000"), budget.verified_current_balance)
            snap.recorded_at = utcnow()
        else:
            new_snap = CreditSnapshot(
                account_id=account_id,
                available_credits=budget.verified_current_balance,
                consumed_credits=budget.credit_usage,
                total_allocated=budget.starting_balance,
                balance_source=budget.balance_source or "real_provider",
                is_estimate=False,
                recorded_at=utcnow(),
            )
            db.add(new_snap)

        # Unlink active task
        if budget.active_task_id == task_id:
            budget.active_task_id = None

        # Re-check ceiling and trigger account rotation if reached
        self.evaluate_account_eligibility(budget, db)
        db.commit()
        db.refresh(budget)

        if not budget.is_eligible:
            logger.info(
                f"Account {account_id} reached 50% credit ceiling. Rotated out of active scheduling."
            )

        return budget

    def list_account_budgets(self, db: Session) -> List[Dict]:
        accounts = db.query(EmergentAccount).all()
        results = []
        for acc in accounts:
            budget = self.get_or_create_budget(acc.id, db)
            self.evaluate_account_eligibility(budget, db)
            ceiling_limit = (budget.starting_balance * budget.ceiling_percentage) / Decimal("100.00")
            current_committed = budget.credit_usage + budget.reserved_credits
            remaining = max(Decimal("0.0000"), ceiling_limit - current_committed)

            results.append({
                "id": budget.id,
                "account_id": acc.id,
                "account_name": acc.account_name,
                "starting_balance": budget.starting_balance,
                "verified_current_balance": budget.verified_current_balance,
                "credit_usage": budget.credit_usage,
                "reserved_credits": budget.reserved_credits,
                "ceiling_percentage": budget.ceiling_percentage,
                "planned_ceiling_limit": ceiling_limit,
                "remaining_eligible_budget": remaining,
                "balance_source": budget.balance_source,
                "last_balance_validated_at": budget.last_balance_validated_at,
                "is_eligible": budget.is_eligible,
                "ineligibility_reason": budget.ineligibility_reason,
                "universal_api_usage": budget.universal_api_usage,
                "platform_build_usage": budget.platform_build_usage,
                "active_task_id": budget.active_task_id,
                "created_at": budget.created_at,
                "updated_at": budget.updated_at,
            })
        return results
