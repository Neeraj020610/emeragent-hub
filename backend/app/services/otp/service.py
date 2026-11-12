"""
OTP Management Service
Phase 3 Implementation for Emergent Central Hub

Coordinates:
- Mailbox-to-account mapping
- Strict security and owner-authorization validation
- Mailbox-specific concurrency control
- Integration switch and verification status guards
- Background orchestrator polling and result retrieval
"""
import uuid
import logging
from datetime import datetime, timedelta, timezone
from typing import List, Optional

from fastapi import HTTPException, status
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError

from app.config import settings
from app.models.user import User
from app.models.account import EmergentAccount
from app.models.otp import MailboxAccount, OTPRequest
from app.schemas.otp import (
    MailboxAccountCreate,
    MailboxAccountUpdate,
    MailboxAccountResponse,
    OTPRequestCreate,
    OTPRequestResponse,
    OTPStatusResponse,
    OTPResultResponse,
)
from app.services.otp.mail_api import EmailApiClient
from app.services.otp.validator import validate_create_command_response
from app.services.otp.security import (
    verify_user_otp_permission,
    claim_transient_otp,
    is_transient_otp_available,
)
from app.services.otp.redis_store import RedisUnavailableError
from app.services.otp.orchestrator import OTPOrchestrator
from app.dependencies import record_audit

logger = logging.getLogger("emergent.otp.service")


class OTPService:
    def __init__(
        self,
        mail_client: Optional[EmailApiClient] = None,
        orchestrator: Optional[OTPOrchestrator] = None,
    ):
        self.mail_client = mail_client or EmailApiClient()
        self.orchestrator = orchestrator or OTPOrchestrator(mail_client=self.mail_client)

    # -------------------------------------------------------------
    # Mailbox Management
    # -------------------------------------------------------------
    def list_mailboxes(self, db: Session) -> List[MailboxAccountResponse]:
        mailboxes = db.query(MailboxAccount).order_by(MailboxAccount.created_at.asc()).all()
        return [MailboxAccountResponse.model_validate(mb) for mb in mailboxes]

    def create_mailbox(
        self,
        payload: MailboxAccountCreate,
        current_user: User,
        db: Session,
        ip_address: Optional[str] = None,
    ) -> MailboxAccountResponse:
        existing = db.query(MailboxAccount).filter(MailboxAccount.email_address == payload.email_address).first()
        if existing:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Mailbox with email '{payload.email_address}' is already registered.",
            )

        if payload.account_id:
            account = db.query(EmergentAccount).filter(EmergentAccount.id == payload.account_id).first()
            if not account:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=f"Emergent account ID {payload.account_id} not found.",
                )

        mailbox = MailboxAccount(
            email_address=str(payload.email_address),
            employee_name=payload.employee_name.strip(),
            provider="internal_mail_api",
            api_base_url=payload.api_base_url or settings.EMAIL_API_BASE_URL,
            account_id=payload.account_id,
            ownership_type=payload.ownership_type,
            is_active=payload.is_active,
            verified_access=payload.verified_access,
            notes=payload.notes,
        )
        db.add(mailbox)
        db.commit()
        db.refresh(mailbox)

        record_audit(
            db=db,
            action="mailbox_registered",
            resource_type="mailbox_account",
            resource_id=str(mailbox.id),
            user_id=current_user.id,
            ip_address=ip_address,
            details=f"Registered mailbox {mailbox.email_address} mapped to employee {mailbox.employee_name}",
        )
        return MailboxAccountResponse.model_validate(mailbox)

    def update_mailbox(
        self,
        mailbox_id: int,
        payload: MailboxAccountUpdate,
        current_user: User,
        db: Session,
        ip_address: Optional[str] = None,
    ) -> MailboxAccountResponse:
        mailbox = db.query(MailboxAccount).filter(MailboxAccount.id == mailbox_id).first()
        if not mailbox:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Mailbox not found.",
            )

        if payload.employee_name is not None:
            mailbox.employee_name = payload.employee_name.strip()
        if payload.account_id is not None:
            if payload.account_id > 0:
                acc = db.query(EmergentAccount).filter(EmergentAccount.id == payload.account_id).first()
                if not acc:
                    raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Associated Emergent account not found.")
                mailbox.account_id = acc.id
            else:
                mailbox.account_id = None
        if payload.ownership_type is not None:
            mailbox.ownership_type = payload.ownership_type
        if payload.is_active is not None:
            mailbox.is_active = payload.is_active
        if payload.verified_access is not None:
            mailbox.verified_access = payload.verified_access
        if payload.notes is not None:
            mailbox.notes = payload.notes

        db.commit()
        db.refresh(mailbox)

        record_audit(
            db=db,
            action="mailbox_updated",
            resource_type="mailbox_account",
            resource_id=str(mailbox.id),
            user_id=current_user.id,
            ip_address=ip_address,
            details=f"Updated mailbox {mailbox.email_address} settings",
        )
        return MailboxAccountResponse.model_validate(mailbox)

    def toggle_mailbox_verification(
        self,
        mailbox_id: int,
        verify: bool,
        current_user: User,
        db: Session,
        ip_address: Optional[str] = None,
    ) -> MailboxAccountResponse:
        mailbox = db.query(MailboxAccount).filter(MailboxAccount.id == mailbox_id).first()
        if not mailbox:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Mailbox not found.")

        mailbox.verified_access = verify
        db.commit()
        db.refresh(mailbox)

        record_audit(
            db=db,
            action="mailbox_verification_updated",
            resource_type="mailbox_account",
            resource_id=str(mailbox.id),
            user_id=current_user.id,
            ip_address=ip_address,
            details=f"Admin set verified_access={verify} for mailbox {mailbox.email_address}",
        )
        return MailboxAccountResponse.model_validate(mailbox)

    # -------------------------------------------------------------
    # OTP Requests & Workflow
    # -------------------------------------------------------------
    async def create_otp_request(
        self,
        payload: OTPRequestCreate,
        current_user: User,
        db: Session,
        ip_address: Optional[str] = None,
    ) -> OTPRequestResponse:
        """
        Executes Step 1 through Step 3 of the OTP workflow:
        1. Find mailbox & account
        2. Validate user & owner permissions
        3. Mailbox concurrency lock check
        4. Integration switch & verification check
        5. Dispatch create-email-command.asp
        6. Start background polling orchestrator
        """
        # 1. Identify Mailbox
        mailbox: Optional[MailboxAccount] = None
        account: Optional[EmergentAccount] = None

        if payload.mailbox_id:
            mailbox = db.query(MailboxAccount).filter(MailboxAccount.id == payload.mailbox_id).first()
            if not mailbox:
                raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Mailbox account not found.")
            if mailbox.account_id:
                account = db.query(EmergentAccount).filter(EmergentAccount.id == mailbox.account_id).first()

        if not mailbox and payload.account_id:
            account = db.query(EmergentAccount).filter(EmergentAccount.id == payload.account_id).first()
            if not account:
                raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Emergent account not found.")
            mailbox = db.query(MailboxAccount).filter(MailboxAccount.account_id == account.id).first()
            if not mailbox:
                # Fallback: check mailbox with matching email
                mailbox = db.query(MailboxAccount).filter(MailboxAccount.email_address == account.email).first()

        if not mailbox:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="No registered mailbox is configured for this account. Please map a mailbox first.",
            )

        if not mailbox.is_active:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Mailbox {mailbox.email_address} is currently disabled.",
            )

        # 2. Security & Permission Validation
        try:
            verify_user_otp_permission(
                user=current_user,
                account=account,
                mailbox=mailbox,
                owner_consent_confirmed=payload.owner_consent_confirmed,
                db=db,
            )
        except ValueError as e:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(e))

        # 3. Mailbox-Specific Concurrency Check
        active_conflict = (
            db.query(OTPRequest)
            .filter(
                OTPRequest.mailbox_id == mailbox.id,
                OTPRequest.status.in_(["pending", "polling"]),
            )
            .first()
        )
        if active_conflict:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=(
                    f"A retrieval request is already active for mailbox {mailbox.email_address} "
                    f"(Request ID #{active_conflict.id}, correlation: {active_conflict.correlation_id}). "
                    f"Please wait for it to complete or cancel it before initiating a new one."
                ),
            )

        now = datetime.now(timezone.utc)
        expires_at = now + timedelta(minutes=payload.validity_minutes)
        correlation_id = f"cmd_{uuid.uuid4().hex[:12]}"

        # 4. Check Global Integration Disable Switch & Mailbox Verification
        if not settings.EMAIL_API_ENABLED:
            otp_req = OTPRequest(
                mailbox_id=mailbox.id,
                account_id=account.id if account else mailbox.account_id,
                requested_by_user_id=current_user.id,
                status="blocked_unverified",
                correlation_id=correlation_id,
                command_id=None,
                sender_filter=payload.sender_filter,
                subject_filter=payload.subject_filter,
                error_reason="Email API integration is disabled globally pending administrative access control verification.",
                expires_at=expires_at,
            )
            db.add(otp_req)
            db.commit()
            db.refresh(otp_req)

            record_audit(
                db=db,
                action="otp_request_blocked",
                resource_type="otp_request",
                resource_id=str(otp_req.id),
                user_id=current_user.id,
                ip_address=ip_address,
                details=f"Blocked OTP request {correlation_id} (Global EMAIL_API_ENABLED is false)",
            )
            return self._build_response(otp_req, account, mailbox)

        if not mailbox.verified_access:
            otp_req = OTPRequest(
                mailbox_id=mailbox.id,
                account_id=account.id if account else mailbox.account_id,
                requested_by_user_id=current_user.id,
                status="blocked_unverified",
                correlation_id=correlation_id,
                command_id=None,
                sender_filter=payload.sender_filter,
                subject_filter=payload.subject_filter,
                error_reason="Mailbox access is unverified. Admin must verify provider authorization before active OTP retrieval.",
                expires_at=expires_at,
            )
            db.add(otp_req)
            db.commit()
            db.refresh(otp_req)

            record_audit(
                db=db,
                action="otp_request_blocked",
                resource_type="otp_request",
                resource_id=str(otp_req.id),
                user_id=current_user.id,
                ip_address=ip_address,
                details=f"Blocked OTP request {correlation_id} for unverified mailbox {mailbox.email_address}",
            )
            return self._build_response(otp_req, account, mailbox)

        # 5. Dispatch External API Command: GET /create-email-command.asp
        try:
            employee_name = mailbox.employee_name or (current_user.full_name or "SystemOperator")
            cmd_resp = await self.mail_client.create_email_command(
                email_address=mailbox.email_address,
                employee_name=employee_name,
                command_type="Inbox",
            )
            is_valid, command_id, err = validate_create_command_response(cmd_resp)
            if not is_valid or not command_id:
                otp_req = OTPRequest(
                    mailbox_id=mailbox.id,
                    account_id=account.id if account else mailbox.account_id,
                    requested_by_user_id=current_user.id,
                    status="failed",
                    correlation_id=correlation_id,
                    command_id=None,
                    sender_filter=payload.sender_filter,
                    subject_filter=payload.subject_filter,
                    error_reason=err or "Invalid response from create-email-command",
                    expires_at=expires_at,
                    completed_at=now,
                )
                db.add(otp_req)
                db.commit()
                db.refresh(otp_req)
                return self._build_response(otp_req, account, mailbox)

            # Check command_id uniqueness to prevent collision / cross-request replay
            duplicate_cmd = db.query(OTPRequest).filter(OTPRequest.command_id == command_id).first()
            if duplicate_cmd:
                logger.error(f"Collision: command_id '{command_id}' already used by request #{duplicate_cmd.id}")
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail=f"Security Alert: Reused commandId '{command_id}' returned by email API. Request rejected to prevent collision.",
                )

        except HTTPException:
            raise

        except Exception as e:
            logger.error(f"Error calling create-email-command: {str(e)}")
            otp_req = OTPRequest(
                mailbox_id=mailbox.id,
                account_id=account.id if account else mailbox.account_id,
                requested_by_user_id=current_user.id,
                status="failed",
                correlation_id=correlation_id,
                command_id=None,
                sender_filter=payload.sender_filter,
                subject_filter=payload.subject_filter,
                error_reason=f"Failed to communicate with email API: {str(e)}",
                expires_at=expires_at,
                completed_at=now,
            )
            db.add(otp_req)
            db.commit()
            db.refresh(otp_req)
            return self._build_response(otp_req, account, mailbox)

        # 6. Command Created Successfully: Save and Launch Polling
        otp_req = OTPRequest(
            mailbox_id=mailbox.id,
            account_id=account.id if account else mailbox.account_id,
            requested_by_user_id=current_user.id,
            status="pending",
            correlation_id=correlation_id,
            command_id=command_id,
            sender_filter=payload.sender_filter,
            subject_filter=payload.subject_filter,
            expires_at=expires_at,
        )
        try:
            db.add(otp_req)
            db.commit()
            db.refresh(otp_req)
        except IntegrityError:
            db.rollback()
            logger.error(f"IntegrityError: Duplicate commandId '{command_id}' on insert")
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Security Alert: Reused or concurrent duplicate commandId '{command_id}'. Request rejected.",
            )

        # Launch background polling engine
        self.orchestrator.start_polling(otp_req.id)

        record_audit(
            db=db,
            action="otp_request_dispatched",
            resource_type="otp_request",
            resource_id=str(otp_req.id),
            user_id=current_user.id,
            ip_address=ip_address,
            details=f"Dispatched commandId {command_id} for {mailbox.email_address} (correlation {correlation_id})",
        )
        return self._build_response(otp_req, account, mailbox)

    def get_otp_status(self, request_id: int, current_user: User, db: Session) -> OTPStatusResponse:
        req = db.query(OTPRequest).filter(OTPRequest.id == request_id).first()
        if not req:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="OTP request not found.")

        # Check permission to view status
        is_admin = current_user.role and current_user.role.name.upper() in ("ADMIN", "SUPERADMIN")
        if not is_admin and req.requested_by_user_id != current_user.id:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access denied.")

        ready = (req.status == "completed") and is_transient_otp_available(req.id)

        return OTPStatusResponse(
            request_id=req.id,
            status=req.status,
            correlation_id=req.correlation_id,
            command_id=req.command_id,
            attempts_count=req.attempts_count,
            is_ready=ready,
            error_reason=req.error_reason,
            expires_at=req.expires_at,
        )

    def claim_otp_result(
        self,
        request_id: int,
        current_user: User,
        db: Session,
        ip_address: Optional[str] = None,
    ) -> OTPResultResponse:
        req = db.query(OTPRequest).filter(OTPRequest.id == request_id).first()
        if not req:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="OTP request not found.")

        is_admin = current_user.role and current_user.role.name.upper() in ("ADMIN", "SUPERADMIN")
        if not is_admin and req.requested_by_user_id != current_user.id:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access denied to retrieved OTP.")

        if req.status != "completed":
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"OTP retrieval is not completed (current status: {req.status}).",
            )

        # Atomic one-time claim from Redis strictly bound to request, user, mailbox, and account
        try:
            otp_code = claim_transient_otp(
                request_id=req.id,
                user_id=current_user.id,
                mailbox_id=req.mailbox_id,
                account_id=req.account_id,
                is_admin=is_admin,
            )
        except RedisUnavailableError as e:
            record_audit(
                db=db,
                action="otp_claim_service_unavailable",
                resource_type="otp_request",
                resource_id=str(req.id),
                user_id=current_user.id,
                ip_address=ip_address,
                details=f"Redis transient storage unreachable when claiming OTP for correlation {req.correlation_id}",
            )
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="OTP transient storage service (Redis) is currently unavailable. Please retry later.",
            ) from e
        if not otp_code:
            raise HTTPException(
                status_code=status.HTTP_410_GONE,
                detail="OTP code has expired from transient memory or has already been retrieved (atomic one-time claim enforced).",
            )

        now = datetime.now(timezone.utc)

        # Audit log OTP retrieval (NEVER write OTP code to audit details)
        record_audit(
            db=db,
            action="otp_code_retrieved",
            resource_type="otp_request",
            resource_id=str(req.id),
            user_id=current_user.id,
            ip_address=ip_address,
            details=f"Requester claimed OTP code for correlation {req.correlation_id}",
        )

        return OTPResultResponse(
            request_id=req.id,
            correlation_id=req.correlation_id,
            otp_code=otp_code,
            retrieved_at=now,
            expires_at=req.expires_at,
        )

    # -------------------------------------------------------------
    # Personal Account Server-Side Consent Management (Phase 3.1)
    # -------------------------------------------------------------
    def grant_personal_consent(
        self,
        account_id: int,
        authorized_member_id: int,
        current_user: User,
        db: Session,
        scope: str = "OTP_RETRIEVAL",
        expires_in_days: Optional[int] = 30,
        ip_address: Optional[str] = None,
    ):
        from app.models.account import PersonalAccountConsent
        account = db.query(EmergentAccount).filter(EmergentAccount.id == account_id).first()
        if not account:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Account not found.")

        is_admin = current_user.role and current_user.role.name.upper() in ("ADMIN", "SUPERADMIN")
        if not is_admin and account.owner_user_id != current_user.id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Only the account owner or an Administrator can grant personal account consent.",
            )

        # Deactivate any existing active consent for this member & account
        existing = (
            db.query(PersonalAccountConsent)
            .filter(
                PersonalAccountConsent.account_id == account_id,
                PersonalAccountConsent.authorized_member_id == authorized_member_id,
                PersonalAccountConsent.is_active == True,
            )
            .all()
        )
        now = datetime.now(timezone.utc)
        for c in existing:
            c.is_active = False
            c.revoked_at = now

        expires_at = now + timedelta(days=expires_in_days) if expires_in_days else None

        is_owner = bool(account.owner_user_id == current_user.id)
        actor_label = f"Account Owner #{current_user.id}" if is_owner else f"Administrator #{current_user.id} on behalf of Owner #{account.owner_user_id}"

        consent = PersonalAccountConsent(
            account_id=account.id,
            owner_user_id=account.owner_user_id or current_user.id,
            authorized_member_id=authorized_member_id,
            granted_by_user_id=current_user.id,
            permission_scope=scope,
            is_active=True,
            approved_at=now,
            expires_at=expires_at,
        )
        db.add(consent)
        db.commit()
        db.refresh(consent)

        record_audit(
            db=db,
            action="personal_consent_granted",
            resource_type="personal_account_consent",
            resource_id=str(consent.id),
            user_id=current_user.id,
            ip_address=ip_address,
            details=f"{actor_label} granted personal consent for member #{authorized_member_id} on account '{account.account_name}' (scope: {scope})",
        )
        return consent

    def revoke_personal_consent(
        self,
        consent_id: int,
        current_user: User,
        db: Session,
        ip_address: Optional[str] = None,
    ):
        from app.models.account import PersonalAccountConsent
        consent = db.query(PersonalAccountConsent).filter(PersonalAccountConsent.id == consent_id).first()
        if not consent:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Consent record not found.")

        is_admin = current_user.role and current_user.role.name.upper() in ("ADMIN", "SUPERADMIN")
        if not is_admin and consent.owner_user_id != current_user.id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Only the account owner or an Administrator can revoke personal account consent.",
            )

        consent.is_active = False
        consent.revoked_at = datetime.now(timezone.utc)
        db.commit()
        db.refresh(consent)

        record_audit(
            db=db,
            action="personal_consent_revoked",
            resource_type="personal_account_consent",
            resource_id=str(consent.id),
            user_id=current_user.id,
            ip_address=ip_address,
            details=f"Revoked personal consent #{consent.id} for member #{consent.authorized_member_id}",
        )
        return consent

    def list_personal_consents(
        self,
        account_id: int,
        current_user: User,
        db: Session,
    ):
        from app.models.account import PersonalAccountConsent
        account = db.query(EmergentAccount).filter(EmergentAccount.id == account_id).first()
        if not account:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Account not found.")

        is_admin = current_user.role and current_user.role.name.upper() in ("ADMIN", "SUPERADMIN")
        if not is_admin and account.owner_user_id != current_user.id:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access denied.")

        return (
            db.query(PersonalAccountConsent)
            .filter(PersonalAccountConsent.account_id == account_id)
            .order_by(PersonalAccountConsent.approved_at.desc())
            .all()
        )

    def cancel_otp_request(
        self,
        request_id: int,
        current_user: User,
        db: Session,
        ip_address: Optional[str] = None,
    ) -> OTPRequestResponse:
        req = db.query(OTPRequest).filter(OTPRequest.id == request_id).first()
        if not req:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="OTP request not found.")

        is_admin = current_user.role and current_user.role.name.upper() in ("ADMIN", "SUPERADMIN")
        if not is_admin and req.requested_by_user_id != current_user.id:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access denied.")

        if req.status in ("completed", "failed", "cancelled"):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Cannot cancel request in '{req.status}' state.",
            )

        req.status = "cancelled"
        req.error_reason = "Cancelled by user"
        req.completed_at = datetime.now(timezone.utc)
        db.commit()
        db.refresh(req)

        # Cancel background task
        self.orchestrator.cancel_task(req.id)

        record_audit(
            db=db,
            action="otp_request_cancelled",
            resource_type="otp_request",
            resource_id=str(req.id),
            user_id=current_user.id,
            ip_address=ip_address,
            details=f"User cancelled OTP request {req.correlation_id}",
        )
        mailbox = db.query(MailboxAccount).filter(MailboxAccount.id == req.mailbox_id).first()
        account = db.query(EmergentAccount).filter(EmergentAccount.id == req.account_id).first() if req.account_id else None
        return self._build_response(req, account, mailbox)

    def list_history(
        self,
        current_user: User,
        db: Session,
        account_id: Optional[int] = None,
        mailbox_id: Optional[int] = None,
        limit: int = 50,
    ) -> List[OTPRequestResponse]:
        query = db.query(OTPRequest).order_by(OTPRequest.created_at.desc())
        if account_id:
            query = query.filter(OTPRequest.account_id == account_id)
        if mailbox_id:
            query = query.filter(OTPRequest.mailbox_id == mailbox_id)

        requests = query.limit(limit).all()
        results = []
        for r in requests:
            account = db.query(EmergentAccount).filter(EmergentAccount.id == r.account_id).first() if r.account_id else None
            mailbox = db.query(MailboxAccount).filter(MailboxAccount.id == r.mailbox_id).first() if r.mailbox_id else None
            results.append(self._build_response(r, account, mailbox))
        return results

    def _build_response(
        self,
        req: OTPRequest,
        account: Optional[EmergentAccount],
        mailbox: Optional[MailboxAccount],
    ) -> OTPRequestResponse:
        return OTPRequestResponse(
            id=req.id,
            mailbox_id=req.mailbox_id,
            account_id=req.account_id,
            account_name=account.account_name if account else (mailbox.account.account_name if mailbox and mailbox.account else None),
            mailbox_email=mailbox.email_address if mailbox else None,
            employee_name=mailbox.employee_name if mailbox else None,
            requested_by_user_id=req.requested_by_user_id,
            status=req.status,
            correlation_id=req.correlation_id,
            command_id=req.command_id,
            attempts_count=req.attempts_count,
            error_reason=req.error_reason,
            sender_filter=req.sender_filter,
            subject_filter=req.subject_filter,
            expires_at=req.expires_at,
            received_at=req.received_at,
            completed_at=req.completed_at,
            created_at=req.created_at,
            is_verified=bool(req.otp_code_hash),
        )

