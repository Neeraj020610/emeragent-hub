import asyncio
import logging
from datetime import datetime, timezone
from decimal import Decimal
from typing import Optional, Tuple

from app.database import SessionLocal
from app.models.account import EmergentAccount
from app.models.session import AccountSession
from app.models.autonomous import AccountCreditBudget
from app.models.credit import CreditSnapshot
from app.models.audit import AuditLog
from app.core.security import decrypt_token

logger = logging.getLogger(__name__)


def enforce_single_active_account(active_account_id: int):
    """
    Enforces the single-active-account policy:
    - Only active_account_id remains CONNECTED and ACTIVE.
    - All other connected accounts are transitioned to STANDBY state.
    """
    db = SessionLocal()
    try:
        now = datetime.now(timezone.utc)
        # Update other connected accounts to STANDBY
        other_accounts = (
            db.query(EmergentAccount)
            .filter(
                EmergentAccount.id != active_account_id,
                EmergentAccount.connection_status == "CONNECTED",
            )
            .all()
        )
        for acc in other_accounts:
            acc.connection_status = "STANDBY"
            acc.updated_at = now
            sess = db.query(AccountSession).filter(AccountSession.account_id == acc.id).first()
            if sess and sess.session_status == "ACTIVE":
                sess.session_status = "STANDBY"
                sess.updated_at = now

        db.commit()
    except Exception as e:
        logger.warning(f"Error enforcing single active account: {e}")
    finally:
        db.close()


async def auto_failover_exhausted_account(exhausted_account_id: int) -> Optional[int]:
    """
    Called when an active account's credits are completely consumed (balance <= 0):
    1. Marks the exhausted account as EXHAUSTED / INACTIVE.
    2. Searches for the next available standby account with encrypted credentials in the vault.
    3. Automatically triggers headless login with Phx Email OTP retrieval.
    4. Upon successful login & balance verification, sets the new account as the single ACTIVE worker.
    """
    db = SessionLocal()
    next_account = None
    try:
        now = datetime.now(timezone.utc)
        # 1. Mark exhausted account
        ex_acc = db.query(EmergentAccount).filter(EmergentAccount.id == exhausted_account_id).first()
        ex_name = ex_acc.account_name if ex_acc else f"Account #{exhausted_account_id}"
        if ex_acc:
            ex_acc.connection_status = "EXHAUSTED"
            ex_acc.updated_at = now
            sess = db.query(AccountSession).filter(AccountSession.account_id == exhausted_account_id).first()
            if sess:
                sess.session_status = "EXPIRED"
                sess.reauth_required = True
                sess.reauth_reason = "100% credits exhausted. Auto-switched to next account."
                sess.updated_at = now

            bud = db.query(AccountCreditBudget).filter(AccountCreditBudget.account_id == exhausted_account_id).first()
            if bud:
                bud.is_eligible = False
                bud.ineligibility_reason = "Credits fully exhausted (0 Cr remaining)."

            audit = AuditLog(
                user_id=ex_acc.owner_user_id or 1,
                action="account_credits_exhausted",
                resource_type="account",
                resource_id=str(exhausted_account_id),
                details=f"Account '{ex_name}' consumed all available credits. Auto-failover initiated.",
            )
            db.add(audit)
            db.commit()

        # 2. Pick next eligible standby account
        candidates = (
            db.query(EmergentAccount)
            .filter(
                EmergentAccount.id != exhausted_account_id,
                EmergentAccount.connection_status.in_(["STANDBY", "DISCONNECTED", "CONNECTED"]),
                EmergentAccount.encrypted_password.isnot(None),
            )
            .order_by(EmergentAccount.id.asc())
            .all()
        )

        for cand in candidates:
            # Check if candidate has credits remaining
            latest_snap = (
                db.query(CreditSnapshot)
                .filter(CreditSnapshot.account_id == cand.id)
                .order_by(CreditSnapshot.recorded_at.desc())
                .first()
            )
            if latest_snap and latest_snap.available_credits is not None and latest_snap.available_credits <= Decimal("0"):
                continue
            next_account = cand
            break

    finally:
        db.close()

    if not next_account:
        logger.warning(f"Auto-failover: No eligible standby accounts with vault passwords found.")
        return None

    # 3. Trigger automated login for next_account
    logger.info(f"Auto-failover: Launching next account {next_account.id} ({next_account.account_name})...")
    from app.services.session.login_automation import execute_automated_login, scrape_credits_from_active_session

    pwd = decrypt_token(next_account.encrypted_password) if next_account.encrypted_password else None
    if not pwd:
        return None

    try:
        # Run automated login in background task
        await execute_automated_login(
            account_id=next_account.id,
            email=next_account.email,
            password=pwd,
            mailbox_email=next_account.email,
        )

        # Scrape and record live balance
        balance = await scrape_credits_from_active_session(next_account.id)
        if balance is not None and balance > 0:
            enforce_single_active_account(next_account.id)
            logger.info(f"Auto-failover SUCCESS: Account {next_account.account_name} is now ACTIVE with {balance} credits.")
            return next_account.id
    except Exception as err:
        logger.error(f"Auto-failover failed for account {next_account.id}: {err}")

    return None

