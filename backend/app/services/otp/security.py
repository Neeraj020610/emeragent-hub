"""
OTP Security, Permission Controls, and Redis Transient Storage
Phase 3.1 Hardening Implementation for Emergent Central Hub

Guarantees:
- Raw OTPs and OTP hashes are NEVER written to PostgreSQL.
- Raw OTP is stored only in Redis with Fernet AES encryption and short-lived TTL.
- Atomic one-time retrieval (GETDEL) prevents duplicate claims across workers.
- Strict binding to request_id, user_id, mailbox_id, and account_id.
- Server-side PersonalAccountConsent required for personal account OTP access.
- Sensitive query parameters redacted.
"""
import re
import logging
from datetime import datetime, timezone
from typing import Optional
from sqlalchemy.orm import Session

from app.models.user import User
from app.models.account import EmergentAccount, AccountPermission, PersonalAccountConsent
from app.models.otp import MailboxAccount
from app.services.otp.redis_store import redis_otp_store

logger = logging.getLogger("emergent.otp.security")


def store_transient_otp(
    request_id: int,
    otp_code: str,
    requester_user_id: Optional[int] = None,
    mailbox_id: int = 0,
    account_id: Optional[int] = None,
    ttl_seconds: int = 300,
) -> None:
    """
    Encrypts and stores OTP in Redis with strict TTL.
    """
    redis_otp_store.store_otp(
        request_id=request_id,
        otp_code=otp_code,
        user_id=requester_user_id,
        mailbox_id=mailbox_id,
        account_id=account_id,
        ttl_seconds=ttl_seconds,
    )


def claim_transient_otp(
    request_id: int,
    user_id: int,
    mailbox_id: Optional[int] = None,
    account_id: Optional[int] = None,
    is_admin: bool = False,
) -> Optional[str]:
    """
    Atomically retrieves and zeroizes the transient OTP from Redis.
    Validates request_id, user_id, mailbox_id, and account_id bindings.
    """
    return redis_otp_store.claim_otp(
        request_id=request_id,
        user_id=user_id,
        mailbox_id=mailbox_id,
        account_id=account_id,
        is_admin=is_admin,
    )


def is_transient_otp_available(request_id: int) -> bool:
    """Checks whether an OTP is ready in Redis."""
    return redis_otp_store.is_available(request_id)


def clear_transient_otp(request_id: int) -> None:
    """Explicitly deletes the OTP from Redis."""
    redis_otp_store.clear(request_id)


def verify_user_otp_permission(
    user: User,
    account: Optional[EmergentAccount],
    mailbox: MailboxAccount,
    owner_consent_confirmed: bool = False,
    db: Optional[Session] = None,
) -> None:
    """
    Validates that the user is authorized to request and receive OTP for this mailbox/account.
    Enforces:
    1. Server-side auditable PersonalAccountConsent for personal accounts.
    2. AccountPermission with can_execute or can_manage for company accounts.
    3. Admin and account owner bypass.
    Raises ValueError if unauthorized.
    """
    user_role = getattr(user.role, "name", "").upper() if user.role else ""
    is_admin = user_role in ("ADMIN", "SUPERADMIN")

    # 1. Check Personal Account Owner Authorization
    is_personal = (
        (account and account.ownership_type == "PERSONAL")
        or (mailbox and mailbox.ownership_type == "PERSONAL")
    )
    if is_personal:
        is_owner = bool(account and account.owner_user_id == user.id)
        if not is_owner and not is_admin:
            # Check server-side auditable consent record
            if not db or not account:
                raise ValueError("Personal account verification requires database context.")

            now = datetime.now(timezone.utc)
            consent = (
                db.query(PersonalAccountConsent)
                .filter(
                    PersonalAccountConsent.account_id == account.id,
                    PersonalAccountConsent.authorized_member_id == user.id,
                    PersonalAccountConsent.is_active == True,
                )
                .first()
            )

            if not consent:
                raise ValueError(
                    f"Personal account access requires an explicit, active server-side authorization "
                    f"granted by the account owner. No active consent record found for user #{user.id} on account '{account.account_name}'."
                )

            # Check if consent has expired
            if consent.expires_at:
                exp = consent.expires_at if consent.expires_at.tzinfo else consent.expires_at.replace(tzinfo=timezone.utc)
                if now > exp:
                    raise ValueError("The server-side owner authorization for this personal account has expired.")

            # Also verify member session acknowledgement
            if not owner_consent_confirmed:
                raise ValueError(
                    "Personal account OTP retrieval requires session acknowledgement of owner consent. "
                    "Confirmation must be acknowledged."
                )

    # 2. If user is Admin or Account Owner, permission is granted
    if is_admin or (account and account.owner_user_id == user.id):
        return

    # 3. For team members: verify explicit execute/manage permission
    if account and db:
        perm = (
            db.query(AccountPermission)
            .filter(
                AccountPermission.account_id == account.id,
                AccountPermission.user_id == user.id,
            )
            .first()
        )
        if not perm or (not perm.can_execute and not perm.can_manage):
            raise ValueError(
                f"User does not have execute permissions for Emergent account '{account.account_name}'."
            )


def redact_sensitive_url(url: str) -> str:
    """
    Redacts query parameter values like emailAddress, employeeName, fileid, otp
    from logging or audit logs.
    """
    sensitive_keys = ["emailAddress", "employeeName", "fileid", "otp", "token", "key"]
    pattern = r"([?&])(" + "|".join(sensitive_keys) + r")=([^&]*)"
    return re.sub(pattern, r"\1\2=***", url, flags=re.IGNORECASE)
