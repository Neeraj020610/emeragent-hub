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


MIN_USABLE_CREDITS = Decimal("5.0")


def enforce_single_active_account(active_account_id: int):
    """
    Enforces the single-active-account policy:
    - Only active_account_id remains CONNECTED and ACTIVE.
    - All other connected accounts are transitioned to STANDBY state.
    """
    db = SessionLocal()
    try:
        now = datetime.now(timezone.utc)
        # 1. Activate the primary worker
        act_acc = db.query(EmergentAccount).filter(EmergentAccount.id == active_account_id).first()
        if act_acc:
            act_acc.connection_status = "CONNECTED"
            act_acc.last_connected_at = now
            act_acc.updated_at = now
        act_sess = db.query(AccountSession).filter(AccountSession.account_id == active_account_id).first()
        if not act_sess:
            import uuid
            act_sess = AccountSession(
                account_id=active_account_id,
                session_token=f"sess-{uuid.uuid4().hex[:16]}",
                auth_method="browser_profile",
                session_status="ACTIVE",
                reauth_required=False,
                last_active_at=now,
            )
            db.add(act_sess)
        else:
            act_sess.session_status = "ACTIVE"
            act_sess.reauth_required = False
            act_sess.reauth_reason = None
            act_sess.last_active_at = now
            act_sess.updated_at = now

        # 2. Transition all other connected/active accounts to STANDBY
        other_accounts = (
            db.query(EmergentAccount)
            .filter(
                EmergentAccount.id != active_account_id,
                EmergentAccount.connection_status.in_(["CONNECTED", "ACTIVE"]),
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


def get_or_failover_active_account(db) -> Optional[EmergentAccount]:
    """
    Returns the single currently active account with credits >= 5.0.
    If the active account is missing or has < 5.0 credits, automatically promotes
    the next eligible standby account with >= 5.0 credits immediately.
    """
    now = datetime.now(timezone.utc)

    # 1. Check current connected account
    active = (
        db.query(EmergentAccount)
        .filter(EmergentAccount.connection_status == "CONNECTED")
        .first()
    )

    if active:
        latest_snap = (
            db.query(CreditSnapshot)
            .filter(CreditSnapshot.account_id == active.id)
            .order_by(CreditSnapshot.id.desc())
            .first()
        )
        if latest_snap and latest_snap.available_credits is not None and latest_snap.available_credits >= MIN_USABLE_CREDITS:
            return active
        else:
            logger.info(f"Active account '{active.account_name}' ({active.id}) credits depleted (< 5.0 Cr). Marking EXHAUSTED and failing over to next standby.")
            active.connection_status = "EXHAUSTED"
            active.updated_at = now
            sess = db.query(AccountSession).filter(AccountSession.account_id == active.id).first()
            if sess:
                sess.session_status = "EXPIRED"
                sess.reauth_required = True
                sess.reauth_reason = "Credits depleted (< 5 Cr). Auto-switched to next standby."
                sess.updated_at = now
            db.commit()

    # 2. Find next eligible account in STANDBY with >= 5.0 credits
    standbys = (
        db.query(EmergentAccount)
        .filter(EmergentAccount.connection_status == "STANDBY")
        .order_by(EmergentAccount.id.asc())
        .all()
    )

    for cand in standbys:
        snap = (
            db.query(CreditSnapshot)
            .filter(CreditSnapshot.account_id == cand.id)
            .order_by(CreditSnapshot.id.desc())
            .first()
        )
        if snap and snap.available_credits is not None and snap.available_credits < MIN_USABLE_CREDITS:
            continue

        # Promote candidate directly to single active worker
        enforce_single_active_account(cand.id)
        db.refresh(cand)
        logger.info(f"Auto-Failover SUCCESS: Promoted Standby Account #{cand.id} ({cand.account_name}) with {snap.available_credits if snap else 110} Cr to ACTIVE Worker.")
        return cand

    logger.warning("No standby accounts with >= 5.0 credits found in pool.")
    return None


def handle_account_logged_in(account_id: int):
    """
    Enforces that an already ACTIVE account with positive credits is NEVER preempted:
    - If there is already an active worker with positive credits, the newly logged-in account
      is placed safely in STANDBY state in the queue.
    - If there is NO active worker with positive credits, this account becomes the active worker.
    """
    db = SessionLocal()
    try:
        now = datetime.now(timezone.utc)
        # Check if another account is already CONNECTED and ACTIVE with positive credits
        active_candidate = (
            db.query(EmergentAccount)
            .join(AccountSession, EmergentAccount.id == AccountSession.account_id)
            .filter(
                EmergentAccount.id != account_id,
                EmergentAccount.connection_status == "CONNECTED",
                AccountSession.session_status == "ACTIVE",
            )
            .first()
        )

        has_active_worker = False
        if active_candidate:
            latest_snap = (
                db.query(CreditSnapshot)
                .filter(CreditSnapshot.account_id == active_candidate.id)
                .order_by(CreditSnapshot.id.desc())
                .first()
            )
            if latest_snap and latest_snap.available_credits and latest_snap.available_credits >= MIN_USABLE_CREDITS:
                has_active_worker = True

        acc = db.query(EmergentAccount).filter(EmergentAccount.id == account_id).first()
        sess = db.query(AccountSession).filter(AccountSession.account_id == account_id).first()

        if has_active_worker:
            # Active worker already exists with positive balance! Place this account in STANDBY
            if acc:
                acc.connection_status = "STANDBY"
                acc.last_connected_at = now
                acc.updated_at = now
            if sess:
                sess.session_status = "STANDBY"
                sess.reauth_required = False
                sess.reauth_reason = None
                sess.last_active_at = now
                sess.updated_at = now
            db.commit()
            logger.info(f"Account {account_id} placed in STANDBY queue because active worker {active_candidate.id} still has credits.")
        else:
            # No active worker exists with positive credits. Promote this account to single active worker
            db.close()
            enforce_single_active_account(account_id)
            return
    except Exception as e:
        logger.warning(f"Error in handle_account_logged_in: {e}")
    finally:
        try:
            db.close()
        except Exception:
            pass


async def auto_failover_exhausted_account(exhausted_account_id: int) -> Optional[int]:
    """
    Called when an active account's credits drop below minimum usable threshold (< 5 Cr):
    1. Marks the exhausted account as EXHAUSTED / INACTIVE.
    2. Searches for the next available standby account with credits >= 5.0 (ordered FIFO by account.id).
    3. If next account is already in STANDBY or has active browser profile, promotes it immediately.
    4. Otherwise triggers headless login with Phx Email OTP retrieval.
    5. Sets the new account as the single ACTIVE worker.
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
                sess.reauth_reason = "Credits depleted (< 5 Cr remaining). Auto-switched to next account."
                sess.updated_at = now

            bud = db.query(AccountCreditBudget).filter(AccountCreditBudget.account_id == exhausted_account_id).first()
            if bud:
                bud.verified_current_balance = Decimal("0.0000")
                bud.is_eligible = False
                bud.ineligibility_reason = "Credits depleted (< 5 Cr remaining: 0.00 Cr)."
                bud.last_balance_validated_at = now
                if bud.starting_balance and bud.starting_balance > 0:
                    bud.credit_usage = bud.starting_balance

            db.add(CreditSnapshot(
                account_id=exhausted_account_id,
                available_credits=Decimal("0.0000"),
                consumed_credits=bud.credit_usage if bud else Decimal("0.0000"),
                total_allocated=bud.starting_balance if bud else Decimal("0.0000"),
                balance_source="REAL_PROVIDER",
                is_estimate=False,
            ))

            audit = AuditLog(
                user_id=ex_acc.owner_user_id or 1,
                action="account_credits_exhausted",
                resource_type="account",
                resource_id=str(exhausted_account_id),
                details=f"Account '{ex_name}' credits dropped below 5 Cr. Marked inactive and auto-failover initiated.",
            )
            db.add(audit)
            db.commit()

        # 2. Pick next eligible standby account or unlogged candidate with credentials
        candidates = (
            db.query(EmergentAccount)
            .filter(
                EmergentAccount.id != exhausted_account_id,
                EmergentAccount.connection_status != "EXHAUSTED",
                EmergentAccount.status == "active",
            )
            .order_by(EmergentAccount.id.asc())
            .all()
        )

        for cand in candidates:
            # Skip any account explicitly marked EXHAUSTED
            if (cand.connection_status or "").upper() == "EXHAUSTED":
                continue

            # If account is already in STANDBY or CONNECTED, verify it has usable credits
            if (cand.connection_status or "").upper() in ("STANDBY", "CONNECTED"):
                latest_snap = (
                    db.query(CreditSnapshot)
                    .filter(CreditSnapshot.account_id == cand.id)
                    .order_by(CreditSnapshot.id.desc())
                    .first()
                )
                if latest_snap and latest_snap.available_credits is not None and latest_snap.available_credits < MIN_USABLE_CREDITS:
                    continue
                bud = db.query(AccountCreditBudget).filter(AccountCreditBudget.account_id == cand.id).first()
                if bud and bud.verified_current_balance is not None and bud.verified_current_balance < MIN_USABLE_CREDITS:
                    continue

                next_account = cand
                break
            else:
                # Account is unlogged (DISCONNECTED / LOGIN REQUIRED). Check if it has credentials
                if cand.encrypted_password:
                    next_account = cand
                    break

    finally:
        db.close()

    if not next_account:
        logger.warning("Auto-failover: No eligible standby accounts with >= 5 credits found.")
        return None

    # 3. Promote next account
    logger.info(f"Auto-failover: Next account selected is {next_account.id} ({next_account.account_name})...")

    # If the candidate is already in STANDBY, promote directly
    if (next_account.connection_status or "").upper() == "STANDBY":
        enforce_single_active_account(next_account.id)
        logger.info(f"Auto-failover SUCCESS: Account {next_account.account_name} promoted directly from STANDBY to Active Worker.")
        return next_account.id

    from app.services.session.login_automation import execute_automated_login, scrape_credits_from_active_session
    pwd = decrypt_token(next_account.encrypted_password) if next_account.encrypted_password else None
    if not pwd:
        # Still promote it if it has an active session/profile
        enforce_single_active_account(next_account.id)
        return next_account.id

    try:
        await execute_automated_login(
            account_id=next_account.id,
            email=next_account.email,
            password=pwd,
            mailbox_email=next_account.email,
        )
        balance = await scrape_credits_from_active_session(next_account.id)
        if balance is not None and balance >= float(MIN_USABLE_CREDITS):
            enforce_single_active_account(next_account.id)
            logger.info(f"Auto-failover SUCCESS: Account {next_account.account_name} is now ACTIVE with {balance} credits.")
            return next_account.id
        elif balance is not None and balance < float(MIN_USABLE_CREDITS):
            # Also below 5 credits! Recursively failover to next
            return await auto_failover_exhausted_account(next_account.id)
    except Exception as err:
        logger.error(f"Auto-failover failed for account {next_account.id}: {err}")

    return None

