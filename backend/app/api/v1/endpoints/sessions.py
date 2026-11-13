import asyncio
import os
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.user import User
from app.schemas.session import (
    AccountSessionAuthenticateRequest,
    AccountSessionResponse,
    AccountSessionSwitchResponse,
    AccountSessionStats,
    AccountSessionSecureLoginRequest,
    AccountSessionSecureLoginResponse,
    AccountSessionSubmitOTPRequest,
    AccountSessionSubmitOTPResponse,
)
from app.services.session.manager import MultiAccountSessionManager
from app.dependencies import get_current_user, require_role

router = APIRouter()
session_manager = MultiAccountSessionManager()


@router.get("", response_model=List[AccountSessionResponse])
def list_account_sessions(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    List independent sessions across all Emergent accounts.
    Shows connection status, authentication method, expiry, and re-authentication required flags.
    """
    return session_manager.list_sessions(db=db, current_user=current_user)


@router.get("/stats", response_model=AccountSessionStats)
def get_session_stats(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Get aggregated metrics on active, disconnected, and re-authentication required sessions."""
    return session_manager.get_session_stats(db=db, current_user=current_user)


@router.post("/{account_id}/authenticate", response_model=AccountSessionResponse)
def authenticate_account_session(
    account_id: int,
    payload: AccountSessionAuthenticateRequest,
    request: Request,
    current_user: User = Depends(require_role(["ADMIN", "MANAGER"])),
    db: Session = Depends(get_db),
):
    """
    Authenticate an Emergent account once.
    Saves an encrypted session context (OAuth, MCP, or isolated browser profile) that persists across restarts.
    """
    client_ip = request.client.host if request.client else None
    return session_manager.authenticate_account_session(
        db=db,
        account_id=account_id,
        payload=payload,
        current_user=current_user,
        client_ip=client_ip,
    )


@router.post("/{account_id}/switch", response_model=AccountSessionSwitchResponse)
def switch_active_session(
    account_id: int,
    request: Request,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Switch active session to target account:
    - Reuses the existing valid session without re-prompting for email/password/OTP.
    - Other accounts remain independently authenticated.
    """
    client_ip = request.client.host if request.client else None
    return session_manager.switch_active_session(
        db=db,
        account_id=account_id,
        current_user=current_user,
        client_ip=client_ip,
    )


@router.post("/{account_id}/validate", response_model=AccountSessionResponse)
def validate_account_session(
    account_id: int,
    request: Request,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Check session token validity, expiration, and update health status."""
    client_ip = request.client.host if request.client else None
    return session_manager.validate_session(
        db=db,
        account_id=account_id,
        current_user=current_user,
        client_ip=client_ip,
    )


@router.post("/{account_id}/launch-browser")
def launch_isolated_browser(
    account_id: int,
    request: Request,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Launch a native isolated browser instance (Chrome or Edge) dedicated to this account.
    Uses account-specific user-data-dir so web login sessions remain isolated and persist across reboots.
    """
    client_ip = request.client.host if request.client else None
    return session_manager.launch_browser_profile(
        db=db,
        account_id=account_id,
        current_user=current_user,
        client_ip=client_ip,
    )


@router.post("/{account_id}/disconnect")
def disconnect_account_session(
    account_id: int,
    request: Request,
    current_user: User = Depends(require_role(["ADMIN", "MANAGER"])),
    db: Session = Depends(get_db),
):
    """
    Disconnects this specific account session.
    All other account sessions remain completely unaffected and actively authenticated.
    """
    client_ip = request.client.host if request.client else None
    return session_manager.disconnect_account_session(
        db=db,
        account_id=account_id,
        current_user=current_user,
        client_ip=client_ip,
    )


@router.post("/{account_id}/revoke")
def revoke_account_session(
    account_id: int,
    request: Request,
    current_user: User = Depends(require_role(["ADMIN", "MANAGER"])),
    db: Session = Depends(get_db),
):
    """Revokes session tokens and purges isolated browser profile state."""
    client_ip = request.client.host if request.client else None
    return session_manager.revoke_account_session(
        db=db,
        account_id=account_id,
        current_user=current_user,
        client_ip=client_ip,
    )


@router.post("/{account_id}/secure-login", response_model=AccountSessionSecureLoginResponse)
async def secure_account_login(
    account_id: int,
    payload: AccountSessionSecureLoginRequest,
    request: Request,
    current_user: User = Depends(require_role(["ADMIN", "MANAGER"])),
    db: Session = Depends(get_db),
):
    """
    Phase 6.5: Accepts real Emergent credentials in-memory over authenticated API.
    Opens isolated browser profile to https://app.emergent.sh and executes login.
    Never persists plaintext password. Automates OTP via Phx Email API with manual fallback.
    """
    from app.models.account import EmergentAccount
    from app.core.security import encrypt_token, decrypt_token

    account = db.query(EmergentAccount).filter(EmergentAccount.id == account_id).first()
    submitted_pwd = (payload.password or "").strip()
    if account:
        if submitted_pwd and submitted_pwd != "interactive_auth":
            account.encrypted_password = encrypt_token(submitted_pwd)
            db.commit()
        elif not submitted_pwd and account.encrypted_password:
            payload.password = decrypt_token(account.encrypted_password)

    client_ip = request.client.host if request.client else None
    return await session_manager.secure_account_login(
        db=db,
        account_id=account_id,
        payload=payload,
        current_user=current_user,
        client_ip=client_ip,
    )


@router.post("/{account_id}/submit-otp", response_model=AccountSessionSubmitOTPResponse)
async def submit_manual_otp(
    account_id: int,
    payload: AccountSessionSubmitOTPRequest,
    request: Request,
    current_user: User = Depends(require_role(["ADMIN", "MANAGER"])),
    db: Session = Depends(get_db),
):
    """Submits manual OTP code and marks session verified ACTIVE ONLY IF genuinely verified on Emergent."""
    from app.services.session.login_automation import verify_manual_otp_and_authenticate

    client_ip = request.client.host if request.client else None
    clean_code = payload.otp_code.strip()

    # 1. Strictly verify on Emergent browser session first
    success, msg = await verify_manual_otp_and_authenticate(account_id, clean_code)
    if not success:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=msg,
        )

    # 2. Only if Emergent accepted and opened dashboard, mark session and account active in DB
    return session_manager.submit_manual_otp(
        db=db,
        account_id=account_id,
        payload=payload,
        current_user=current_user,
        client_ip=client_ip,
    )


@router.post("/{account_id}/confirm-dashboard", response_model=AccountSessionResponse)
async def confirm_dashboard_verification(
    account_id: int,
    request: Request,
    current_user: User = Depends(require_role(["ADMIN", "MANAGER"])),
    db: Session = Depends(get_db),
):
    """Confirms authenticated Emergent dashboard was opened in isolated browser and marks session ACTIVE."""
    client_ip = request.client.host if request.client else None
    res = session_manager.confirm_dashboard_verification(
        db=db,
        account_id=account_id,
        current_user=current_user,
        client_ip=client_ip,
    )

    # Immediately synchronize credits from live Emergent dashboard
    try:
        from app.services.session.login_automation import scrape_credits_from_active_session
        await scrape_credits_from_active_session(account_id)
    except Exception:
        pass

    return res


@router.post("/{account_id}/start-automated-login")
async def start_automated_login(
    account_id: int,
    payload: AccountSessionSecureLoginRequest,
    request: Request,
    current_user: User = Depends(require_role(["ADMIN", "MANAGER"])),
    db: Session = Depends(get_db),
):
    """
    Starts end-to-end automated Emergent authentication in background task:
    - Opens headed Chrome
    - Fills email & password
    - Waits for OTP screen
    - Calls Phx Email API (employeeName='Mahendra Vishnoi')
    - Auto-types OTP into Emergent
    - Verifies dashboard and marks session ACTIVE
    """
    from app.services.session.login_automation import execute_automated_login
    from app.models.account import EmergentAccount
    from app.models.session import AccountSession
    from app.core.security import encrypt_token, decrypt_token

    account = db.query(EmergentAccount).filter(EmergentAccount.id == account_id).first()
    resolved_pwd = (payload.password or "").strip()
    if account:
        if resolved_pwd and resolved_pwd != "interactive_auth":
            account.encrypted_password = encrypt_token(resolved_pwd)
        elif not resolved_pwd and account.encrypted_password:
            resolved_pwd = decrypt_token(account.encrypted_password)
        account.connection_status = "PENDING"

    session = db.query(AccountSession).filter(AccountSession.account_id == account_id).first()
    if session:
        session.session_status = "LOGIN_IN_PROGRESS"
        session.reauth_required = False
        session.reauth_reason = "Automated login in progress..."
    if account or session:
        db.commit()

    client_ip = request.client.host if request.client else None

    # Spawn asynchronous background task
    asyncio.create_task(
        execute_automated_login(
            account_id=account_id,
            email=payload.email,
            password=resolved_pwd,
            mailbox_email=payload.mailbox_email or payload.email,
            user_id=current_user.id,
            client_ip=client_ip,
        )
    )

    return {
        "status": "STARTED",
        "account_id": account_id,
        "message": "Automated login workflow started. Streaming live progress...",
    }


@router.get("/{account_id}/login-snapshot")
def get_login_snapshot(account_id: int):
    """Serves the latest Playwright login-screen PNG snapshot directly from backend without Next.js static cache."""
    shot_path = f"d:/emargent/frontend/public/login_snapshots/acc_{account_id}.png"
    if not os.path.exists(shot_path):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Snapshot not available yet")
    return FileResponse(
        shot_path,
        media_type="image/png",
        headers={"Cache-Control": "no-store, no-cache, must-revalidate, max-age=0"},
    )


@router.get("/{account_id}/login-progress")
def get_login_progress(
    account_id: int,
    current_user: User = Depends(get_current_user),
):
    """Returns real-time progress logs and status for automated Emergent login."""
    from app.services.session.login_automation import get_progress

    return get_progress(account_id)


@router.post("/{account_id}/abort-login")
def abort_account_login(
    account_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(["ADMIN", "MANAGER"])),
):
    """
    Aborts in-progress login attempt. Cancels automation state and restores account to DISCONNECTED.
    """
    from app.models.account import EmergentAccount
    from app.models.session import AccountSession
    from app.services.session.login_automation import login_progress

    if account_id in login_progress:
        login_progress[account_id]["status"] = "CANCELLED"
        login_progress[account_id]["step"] = "Login cancelled by user"
        login_progress[account_id]["is_complete"] = True

    account = db.query(EmergentAccount).filter(EmergentAccount.id == account_id).first()
    if account:
        if account.connection_status in ["LOGIN_IN_PROGRESS", "PENDING"]:
            account.connection_status = "DISCONNECTED"
    sess = db.query(AccountSession).filter(AccountSession.account_id == account_id).first()
    if sess and sess.session_status == "LOGIN_IN_PROGRESS":
        sess.session_status = "EXPIRED"
        sess.reauth_required = True
        sess.reauth_reason = "Sign In cancelled. Please Sign In again."
    db.commit()

    return {"status": "SUCCESS", "message": "Login cancelled. Account remains disconnected."}


@router.post("/{account_id}/sync-credits")
async def sync_account_credits(
    account_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(["ADMIN", "MANAGER"])),
):
    """
    Queries active Emergent session to scrape real-time credit balance and saves a CreditSnapshot.
    """
    from app.services.session.login_automation import scrape_credits_from_active_session

    balance = await scrape_credits_from_active_session(account_id)
    if balance is None:
        return {
            "status": "SESSION_EXPIRED",
            "account_id": account_id,
            "available_credits": None,
            "message": "Emergent browser session has expired. Account marked as Login Required — please click Sign In / Re-auth.",
        }
    return {
        "status": "SUCCESS",
        "account_id": account_id,
        "available_credits": balance,
        "message": f"Credit balance synced: {balance} credits",
    }



