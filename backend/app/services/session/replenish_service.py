"""
Standby Pool Replenishment Service for Emergent Central Hub
Continuously maintains a pool of 3-5 authenticated and ready accounts in the STANDBY queue.
"""
import asyncio
import logging
from datetime import datetime, timezone
from decimal import Decimal
from typing import Optional

from app.database import SessionLocal
from app.models.account import EmergentAccount
from app.models.session import AccountSession
from app.models.autonomous import AccountCreditBudget
from app.models.credit import CreditSnapshot
from app.core.security import decrypt_token
from app.services.session.failover_service import MIN_USABLE_CREDITS, enforce_single_active_account

logger = logging.getLogger("emergent.session.replenish")

TARGET_STANDBY_BUFFER = 3
_is_replenishing = False


async def replenish_standby_pool_once() -> Optional[int]:
    """
    Checks the number of ready accounts in CONNECTED/STANDBY state with credits >= 5.0.
    If below TARGET_STANDBY_BUFFER, automatically logs into the next available DISCONNECTED
    account using saved credentials and Phoenix email OTP.
    Returns the account_id if an account was successfully logged in and queued, else None.
    """
    global _is_replenishing
    if _is_replenishing:
        logger.debug("Standby replenishment already in progress. Skipping pass.")
        return None

    _is_replenishing = True
    try:
        db = SessionLocal()
        next_to_login: Optional[EmergentAccount] = None
        try:
            # 1. Count currently authenticated, healthy accounts with credits >= 5.0
            ready_accounts = (
                db.query(EmergentAccount)
                .join(AccountSession, EmergentAccount.id == AccountSession.account_id)
                .filter(
                    EmergentAccount.connection_status.in_(["CONNECTED", "STANDBY"]),
                    EmergentAccount.status == "active",
                    AccountSession.session_status.in_(["ACTIVE", "STANDBY"]),
                    AccountSession.reauth_required.is_(False),
                )
                .all()
            )

            valid_ready = []
            for acc in ready_accounts:
                snap = (
                    db.query(CreditSnapshot)
                    .filter(CreditSnapshot.account_id == acc.id)
                    .order_by(CreditSnapshot.id.desc())
                    .first()
                )
                # A truly ready account MUST have a verified snapshot with >= 5.0 credits!
                if not snap or snap.available_credits is None or snap.available_credits < MIN_USABLE_CREDITS:
                    continue
                valid_ready.append(acc)

            ready_count = len(valid_ready)
            logger.info(f"Standby pool status: {ready_count}/{TARGET_STANDBY_BUFFER} truly ready accounts with >= 5 Cr.")

            if ready_count >= TARGET_STANDBY_BUFFER:
                return None

            # Fast-path: Check if any account already has a snapshot >= 5.0 Cr and just needs promotion to STANDBY
            existing_pos_accounts = (
                db.query(EmergentAccount)
                .filter(
                    EmergentAccount.status == "active",
                    EmergentAccount.connection_status != "EXHAUSTED",
                    ~EmergentAccount.connection_status.in_(["STANDBY", "CONNECTED"]),
                )
                .order_by(EmergentAccount.id.asc())
                .all()
            )
            for pos_acc in existing_pos_accounts:
                ls = db.query(CreditSnapshot).filter(CreditSnapshot.account_id == pos_acc.id).order_by(CreditSnapshot.id.desc()).first()
                if ls and ls.available_credits is not None and ls.available_credits >= MIN_USABLE_CREDITS:
                    logger.info(f"Fast-promoting Account #{pos_acc.id} ('{pos_acc.account_name}') with {ls.available_credits} Cr to STANDBY pool!")
                    has_active = db.query(EmergentAccount).filter(EmergentAccount.connection_status == "CONNECTED").first()
                    now = datetime.now(timezone.utc)
                    pos_acc.connection_status = "STANDBY" if has_active else "CONNECTED"
                    pos_acc.last_connected_at = now
                    pos_acc.updated_at = now
                    
                    sess = db.query(AccountSession).filter(AccountSession.account_id == pos_acc.id).first()
                    if not sess:
                        import uuid
                        sess = AccountSession(
                            account_id=pos_acc.id,
                            session_token=f"sess-{uuid.uuid4().hex[:16]}",
                            auth_method="browser_profile",
                            session_status=pos_acc.connection_status,
                            reauth_required=False,
                            last_active_at=now,
                        )
                        db.add(sess)
                    else:
                        sess.session_status = pos_acc.connection_status
                        sess.reauth_required = False
                        sess.last_active_at = now
                        sess.updated_at = now

                    bud = db.query(AccountCreditBudget).filter(AccountCreditBudget.account_id == pos_acc.id).first()
                    if bud:
                        bud.is_eligible = True
                        bud.ineligibility_reason = None
                        bud.verified_current_balance = ls.available_credits

                    db.commit()
                    return pos_acc.id

            # 2. Pick next unlogged candidate account with saved password
            # CRITICAL: STRICTLY IGNORE any accounts with connection_status == 'EXHAUSTED'
            candidates = (
                db.query(EmergentAccount)
                .filter(
                    EmergentAccount.connection_status.in_(["DISCONNECTED", "LOGIN_REQUIRED", "PENDING", None]),
                    EmergentAccount.connection_status != "EXHAUSTED",
                    EmergentAccount.status == "active",
                    EmergentAccount.encrypted_password.isnot(None),
                )
                .order_by(EmergentAccount.id.asc())
                .all()
            )

            for cand in candidates:
                if (cand.connection_status or "").upper() == "EXHAUSTED":
                    continue
                sess = db.query(AccountSession).filter(AccountSession.account_id == cand.id).first()
                if sess and sess.reauth_reason and "Credits depleted" in sess.reauth_reason:
                    continue

                next_to_login = cand
                break

        finally:
            db.close()

        if not next_to_login:
            logger.info("Standby replenisher: No available disconnected accounts with credentials found.")
            return None

        # 3. Decrypt credentials and execute automated login
        pwd = decrypt_token(next_to_login.encrypted_password)
        if not pwd:
            logger.warning(f"Could not decrypt password for Account #{next_to_login.id}.")
            return None

        logger.info(
            f"Standby replenisher: Auto-authenticating Account #{next_to_login.id} "
            f"('{next_to_login.account_name}' - {next_to_login.email}) to replenish standby buffer..."
        )

        from app.services.session.login_automation import execute_automated_login, scrape_credits_from_active_session

        try:
            await asyncio.wait_for(
                execute_automated_login(
                    account_id=next_to_login.id,
                    email=next_to_login.email,
                    password=pwd,
                    mailbox_email=next_to_login.email,
                    keep_open=False,
                ),
                timeout=120.0,
            )

            # Scrape live balance from genuine Emergent dashboard
            balance = await scrape_credits_from_active_session(next_to_login.id)
            now = datetime.now(timezone.utc)

            db2 = SessionLocal()
            try:
                acc_obj = db2.query(EmergentAccount).filter(EmergentAccount.id == next_to_login.id).first()
                sess_obj = db2.query(AccountSession).filter(AccountSession.account_id == next_to_login.id).first()
                bud_obj = db2.query(AccountCreditBudget).filter(AccountCreditBudget.account_id == next_to_login.id).first()

                if balance is not None and balance >= float(MIN_USABLE_CREDITS):
                    # Check if an active worker account is already connected
                    existing_active = (
                        db2.query(EmergentAccount)
                        .filter(EmergentAccount.connection_status == "CONNECTED")
                        .first()
                    )

                    if existing_active and existing_active.id != next_to_login.id:
                        # Place in STANDBY queue
                        if acc_obj:
                            acc_obj.connection_status = "STANDBY"
                            acc_obj.last_connected_at = now
                            acc_obj.updated_at = now
                        if sess_obj:
                            sess_obj.session_status = "STANDBY"
                            sess_obj.reauth_required = False
                            sess_obj.reauth_reason = None
                            sess_obj.last_active_at = now
                            sess_obj.updated_at = now
                        if bud_obj:
                            bud_obj.is_eligible = True
                            bud_obj.ineligibility_reason = None
                            bud_obj.verified_current_balance = Decimal(str(balance))
                        logger.info(
                            f"Standby replenisher SUCCESS: Account #{next_to_login.id} ('{next_to_login.account_name}') "
                            f"queued into STANDBY pool with {balance} Cr."
                        )
                    else:
                        # Promote as the active worker
                        enforce_single_active_account(next_to_login.id)
                        logger.info(
                            f"Standby replenisher SUCCESS: Account #{next_to_login.id} ('{next_to_login.account_name}') "
                            f"promoted to ACTIVE Worker with {balance} Cr."
                        )

                    db2.commit()
                    return next_to_login.id

                elif balance is not None and balance < float(MIN_USABLE_CREDITS):
                    # Account genuinely had < 5 Cr. Mark as EXHAUSTED so it's not retried
                    if acc_obj:
                        acc_obj.connection_status = "EXHAUSTED"
                        acc_obj.updated_at = now
                    if sess_obj:
                        sess_obj.session_status = "EXPIRED"
                        sess_obj.reauth_required = True
                        sess_obj.reauth_reason = f"Live credits below 5 Cr: {balance} Cr"
                        sess_obj.updated_at = now
                    if bud_obj:
                        bud_obj.is_eligible = False
                        bud_obj.ineligibility_reason = f"Credits depleted: {balance} Cr"
                        bud_obj.verified_current_balance = Decimal(str(balance))
                    db2.commit()
                    logger.info(f"Account #{next_to_login.id} has {balance} Cr (< 5 Cr). Marked EXHAUSTED.")
                    return None

            finally:
                db2.close()

        except Exception as login_err:
            logger.warning(f"Standby replenish login failed for Account #{next_to_login.id}: {login_err}")
            db3 = SessionLocal()
            try:
                acc_err = db3.query(EmergentAccount).filter(EmergentAccount.id == next_to_login.id).first()
                if acc_err:
                    acc_err.connection_status = "LOGIN_REQUIRED"
                    db3.commit()
            finally:
                db3.close()

    except Exception as e:
        logger.warning(f"Standby replenisher loop note: {e}")
    finally:
        _is_replenishing = False

    return None
