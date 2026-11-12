"""
OTP and Email API Endpoints
Phase 3 Implementation for Emergent Central Hub
"""
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.user import User
from app.schemas.otp import (
    MailboxAccountCreate,
    MailboxAccountUpdate,
    MailboxAccountResponse,
    OTPRequestCreate,
    OTPRequestResponse,
    OTPStatusResponse,
    OTPResultResponse,
    PersonalConsentCreate,
    PersonalConsentResponse,
)
from app.services.otp.service import OTPService
from app.core.security import verify_otp_code
from app.models.otp import OTPRequest
from app.dependencies import get_current_user, require_role

router = APIRouter()
otp_service = OTPService()


# ------------------------------------------------------------------
# Mailbox Management Endpoints
# ------------------------------------------------------------------
@router.get("/mailboxes", response_model=List[MailboxAccountResponse])
def list_mailboxes(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """List all registered mailboxes and their Emergent account mappings."""
    return otp_service.list_mailboxes(db=db)


@router.post("/mailboxes", response_model=MailboxAccountResponse, status_code=status.HTTP_201_CREATED)
def create_mailbox(
    payload: MailboxAccountCreate,
    request: Request,
    current_user: User = Depends(require_role(["ADMIN"])),
    db: Session = Depends(get_db),
):
    """Register and map a new mailbox to an employee and optional Emergent account."""
    client_ip = request.client.host if request.client else None
    return otp_service.create_mailbox(payload=payload, current_user=current_user, db=db, ip_address=client_ip)


@router.patch("/mailboxes/{mailbox_id}", response_model=MailboxAccountResponse)
def update_mailbox(
    mailbox_id: int,
    payload: MailboxAccountUpdate,
    request: Request,
    current_user: User = Depends(require_role(["ADMIN"])),
    db: Session = Depends(get_db),
):
    """Update mailbox mappings, employee name, or active status."""
    client_ip = request.client.host if request.client else None
    return otp_service.update_mailbox(mailbox_id=mailbox_id, payload=payload, current_user=current_user, db=db, ip_address=client_ip)


@router.post("/mailboxes/{mailbox_id}/verify-access", response_model=MailboxAccountResponse)
def toggle_mailbox_verification(
    mailbox_id: int,
    request: Request,
    verify: bool = Query(..., description="Whether access control compliance is verified"),
    current_user: User = Depends(require_role(["ADMIN"])),
    db: Session = Depends(get_db),
):
    """
    Enables/disables verified access for a mailbox.
    Only ADMINs may verify after confirming email API access control compliance.
    """
    client_ip = request.client.host if request.client else None
    return otp_service.toggle_mailbox_verification(
        mailbox_id=mailbox_id,
        verify=verify,
        current_user=current_user,
        db=db,
        ip_address=client_ip,
    )


# ------------------------------------------------------------------
# OTP Workflow Endpoints
# ------------------------------------------------------------------
@router.post("/request", response_model=OTPRequestResponse, status_code=status.HTTP_201_CREATED)
async def create_otp_request(
    payload: OTPRequestCreate,
    request: Request,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Initiates an OTP retrieval request:
    - Validates account and personal owner authorization.
    - Enforces mailbox concurrency lock.
    - Dispatches create-email-command.asp.
    - Launches background retry orchestrator if verified.
    """
    client_ip = request.client.host if request.client else None
    return await otp_service.create_otp_request(
        payload=payload,
        current_user=current_user,
        db=db,
        ip_address=client_ip,
    )


@router.get("/requests", response_model=List[OTPRequestResponse])
@router.get("/history", response_model=List[OTPRequestResponse])
def list_otp_history(
    account_id: Optional[int] = None,
    mailbox_id: Optional[int] = None,
    limit: int = 50,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """List OTP requests history with correlation metadata."""
    return otp_service.list_history(
        current_user=current_user,
        db=db,
        account_id=account_id,
        mailbox_id=mailbox_id,
        limit=limit,
    )


@router.get("/{request_id}/status", response_model=OTPStatusResponse)
def get_otp_status(
    request_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Polls real-time status and attempts count for an active request."""
    return otp_service.get_otp_status(request_id=request_id, current_user=current_user, db=db)


@router.get("/{request_id}/result", response_model=OTPResultResponse)
def get_otp_result(
    request_id: int,
    request: Request,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Securely claims the retrieved OTP from short-lived transient memory.
    Restricted to authorized requester or Admin.
    """
    client_ip = request.client.host if request.client else None
    return otp_service.claim_otp_result(
        request_id=request_id,
        current_user=current_user,
        db=db,
        ip_address=client_ip,
    )


@router.post("/{request_id}/cancel", response_model=OTPRequestResponse)
def cancel_otp_request(
    request_id: int,
    request: Request,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Cancels a pending or polling request and releases the mailbox lock."""
    client_ip = request.client.host if request.client else None
    return otp_service.cancel_otp_request(
        request_id=request_id,
        current_user=current_user,
        db=db,
        ip_address=client_ip,
    )


# ------------------------------------------------------------------
# Personal Account Server-Side Consent Endpoints (Phase 3.1)
# ------------------------------------------------------------------
@router.post("/consents", response_model=PersonalConsentResponse, status_code=status.HTTP_201_CREATED)
def grant_personal_consent(
    account_id: int,
    payload: PersonalConsentCreate,
    request: Request,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Grants explicit, server-side consent for a team member to retrieve OTPs for a personal account.
    Restricted to account owner or Admin.
    """
    client_ip = request.client.host if request.client else None
    consent = otp_service.grant_personal_consent(
        account_id=account_id,
        authorized_member_id=payload.authorized_member_id,
        current_user=current_user,
        db=db,
        scope=payload.permission_scope,
        expires_in_days=payload.expires_in_days,
        ip_address=client_ip,
    )
    # Populate response email if available
    member_user = db.query(User).filter(User.id == consent.authorized_member_id).first()
    res = PersonalConsentResponse.model_validate(consent)
    res.authorized_member_email = member_user.email if member_user else None
    return res


@router.post("/consents/{consent_id}/revoke", response_model=PersonalConsentResponse)
def revoke_personal_consent(
    consent_id: int,
    request: Request,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Revokes a previously granted personal account consent.
    Restricted to account owner or Admin.
    """
    client_ip = request.client.host if request.client else None
    consent = otp_service.revoke_personal_consent(
        consent_id=consent_id,
        current_user=current_user,
        db=db,
        ip_address=client_ip,
    )
    member_user = db.query(User).filter(User.id == consent.authorized_member_id).first()
    res = PersonalConsentResponse.model_validate(consent)
    res.authorized_member_email = member_user.email if member_user else None
    return res


@router.get("/accounts/{account_id}/consents", response_model=List[PersonalConsentResponse])
def list_account_consents(
    account_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Lists active and historical personal account consent records."""
    consents = otp_service.list_personal_consents(account_id=account_id, current_user=current_user, db=db)
    results = []
    for c in consents:
        member_user = db.query(User).filter(User.id == c.authorized_member_id).first()
        res = PersonalConsentResponse.model_validate(c)
        res.authorized_member_email = member_user.email if member_user else None
        results.append(res)
    return results
