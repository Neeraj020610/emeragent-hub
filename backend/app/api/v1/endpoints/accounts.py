from typing import List, Optional
from datetime import datetime, timezone
import math
from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from sqlalchemy.orm import Session
from sqlalchemy import or_, desc, asc

from app.database import get_db
from app.models.user import User
from app.models.account import EmergentAccount, AccountPermission, AccountConnection
from app.models.credit import CreditSnapshot
from app.models.audit import AuditLog
from app.schemas.account import (
    EmergentAccountCreate,
    EmergentAccountUpdate,
    EmergentAccountResponse,
    AccountListResponse,
    AccountConnectionResponse,
    AccountMemberAssignRequest,
    AccountMemberResponse,
)
from app.schemas.audit import AuditLogResponse
from app.services.account_service import AccountConnectionService
from app.integrations.emergent.service import EmergentIntegrationService
from app.dependencies import get_current_user, require_role, record_audit

router = APIRouter()
connection_service = AccountConnectionService()
emergent_integration_service = EmergentIntegrationService()


def _format_account_response(acc: EmergentAccount, db: Session) -> EmergentAccountResponse:
    latest_snap = (
        db.query(CreditSnapshot)
        .filter(CreditSnapshot.account_id == acc.id)
        .order_by(CreditSnapshot.recorded_at.desc())
        .first()
    )
    members_count = db.query(AccountPermission).filter(AccountPermission.account_id == acc.id).count()
    conn = db.query(AccountConnection).filter(AccountConnection.account_id == acc.id).first()
    from app.models.universal_key import UniversalApiKey
    uni_keys_count = db.query(UniversalApiKey).filter(UniversalApiKey.account_id == acc.id, UniversalApiKey.is_active == True).count()

    conn_resp = None
    if conn:
        conn_resp = AccountConnectionResponse(
            id=conn.id,
            account_id=conn.account_id,
            provider=conn.provider,
            connection_type=conn.connection_type,
            status=conn.status,
            token_expires_at=conn.token_expires_at,
            last_health_check=conn.last_health_check,
            error_message=conn.error_message,
            has_access_token=bool(conn.access_token_enc),
            has_refresh_token=bool(conn.refresh_token_enc),
            created_at=conn.created_at,
        )

    from app.models.otp import MailboxAccount
    mailbox = db.query(MailboxAccount).filter(MailboxAccount.account_id == acc.id).first()
    mb_email = mailbox.email_address if mailbox else None

    return EmergentAccountResponse(
        id=acc.id,
        account_identifier=acc.account_identifier,
        account_name=acc.account_name,
        email=acc.email,
        mailbox_email=mb_email,
        organization=acc.organization,
        owner_user_id=acc.owner_user_id,
        owner_name=acc.owner_name,
        ownership_type=acc.ownership_type,
        description=acc.description,
        status=acc.status,
        auth_type=acc.auth_type,
        connection_status=acc.connection_status,
        credit_sync_status=acc.credit_sync_status,
        last_connected_at=acc.last_connected_at,
        last_synced_at=acc.last_synced_at,
        created_at=acc.created_at,
        updated_at=acc.updated_at,
        latest_credit_balance=latest_snap.available_credits if latest_snap else None,
        assigned_members_count=members_count,
        has_universal_key=uni_keys_count > 0,
        universal_keys_count=uni_keys_count,
        has_saved_password=bool(acc.encrypted_password),
        connection=conn_resp,
    )


@router.get("", response_model=List[EmergentAccountResponse])
def list_accounts(
    search: Optional[str] = Query(None, description="Search by email, name or account ID"),
    ownership_type: Optional[str] = Query(None, description="COMPANY_OWNED or PERSONAL"),
    connection_status: Optional[str] = Query(None, description="CONNECTED, DISCONNECTED, etc."),
    sort_by: str = Query("account_name", description="account_name, created_at, or account_identifier"),
    sort_order: str = Query("asc", description="asc or desc"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    user_role = current_user.role.name if current_user.role else "MEMBER"
    query = db.query(EmergentAccount)

    if user_role == "ADMIN":
        pass  # Admin accesses all accounts
    else:
        # Permitted accounts query
        permitted_ids = (
            db.query(AccountPermission.account_id)
            .filter(AccountPermission.user_id == current_user.id, AccountPermission.can_view == True)
            .subquery()
        )
        query = query.filter(
            or_(
                EmergentAccount.id.in_(permitted_ids),
                EmergentAccount.owner_user_id == current_user.id,
            )
        )

    # Search filter
    if search and search.strip():
        term = f"%{search.strip().lower()}%"
        query = query.filter(
            or_(
                EmergentAccount.email.ilike(term),
                EmergentAccount.account_name.ilike(term),
                EmergentAccount.account_identifier.ilike(term),
            )
        )

    # Ownership filter
    if ownership_type:
        query = query.filter(EmergentAccount.ownership_type == ownership_type.upper())

    # Connection status filter
    if connection_status:
        query = query.filter(EmergentAccount.connection_status == connection_status.upper())

    # Sorting
    sort_col = getattr(EmergentAccount, sort_by, EmergentAccount.account_name)
    if sort_order.lower() == "desc":
        query = query.order_by(desc(sort_col))
    else:
        query = query.order_by(asc(sort_col))

    accounts = query.all()
    return [_format_account_response(acc, db) for acc in accounts]


@router.post("", response_model=EmergentAccountResponse, status_code=status.HTTP_201_CREATED)
def create_account(
    request: Request,
    payload: EmergentAccountCreate,
    current_user: User = Depends(require_role(["ADMIN", "MANAGER"])),
    db: Session = Depends(get_db),
):
    import uuid
    from app.models.session import AccountSession
    from app.models.otp import MailboxAccount
    from app.config import settings

    account_ident = payload.account_identifier
    if not account_ident or not account_ident.strip():
        safe_prefix = "".join(c for c in payload.account_name.upper() if c.isalnum())[:4] or "CORE"
        account_ident = f"EMG-{safe_prefix}-{uuid.uuid4().hex[:4].upper()}"

    existing = (
        db.query(EmergentAccount)
        .filter(EmergentAccount.account_identifier == account_ident)
        .first()
    )
    if existing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Account with identifier '{account_ident}' already exists.",
        )

    owner_user_id = payload.owner_user_id or current_user.id
    owner_name = payload.owner_name
    if not owner_name:
        owner = db.query(User).filter(User.id == owner_user_id).first()
        owner_name = owner.full_name if owner else current_user.full_name

    from app.core.security import encrypt_token
    raw_pwd = (payload.password or "").strip()
    enc_pwd = encrypt_token(raw_pwd) if raw_pwd and raw_pwd != "interactive_auth" else None

    account = EmergentAccount(
        account_identifier=account_ident,
        account_name=payload.account_name,
        email=payload.email,
        organization=payload.organization,
        owner_user_id=owner_user_id,
        owner_name=owner_name,
        ownership_type=payload.ownership_type.upper(),
        description=payload.description,
        status=payload.status,
        auth_type=payload.auth_type,
        encrypted_password=enc_pwd,
        connection_status=payload.connection_status or "DISCONNECTED",
        credit_sync_status=payload.credit_sync_status or "manual_only",
    )
    db.add(account)
    db.commit()
    db.refresh(account)

    # Initialize AccountSession
    sess = AccountSession(
        account_id=account.id,
        session_token=f"sess-init-{uuid.uuid4().hex[:12]}",
        auth_method="browser_profile",
        session_status="NOT_CONNECTED",
        reauth_required=False,
        authenticated_by_user_id=current_user.id,
    )
    db.add(sess)

    # If mailbox_email provided, map to MailboxAccount
    if payload.mailbox_email:
        mb = db.query(MailboxAccount).filter(MailboxAccount.email_address == payload.mailbox_email).first()
        if not mb:
            mb = MailboxAccount(
                email_address=payload.mailbox_email,
                employee_name=account.account_name,
                provider="internal_mail_api",
                api_base_url=settings.EMAIL_API_BASE_URL,
                account_id=account.id,
                ownership_type=account.ownership_type,
                is_active=True,
                verified_access=True,
            )
            db.add(mb)
        else:
            mb.account_id = account.id
            mb.is_active = True
            mb.verified_access = True

    # Create associated connection record
    connection_service.get_or_create_connection(db, account)

    # Automatically grant creator management permissions
    perm = AccountPermission(
        user_id=current_user.id,
        account_id=account.id,
        can_view=True,
        can_execute=True,
        can_manage=True,
    )
    db.add(perm)
    db.commit()

    record_audit(
        db=db,
        action="account_created",
        resource_type="account",
        resource_id=str(account.id),
        user_id=current_user.id,
        ip_address=request.client.host if request.client else None,
        details=f"Created Emergent account {account.account_identifier} ({account.account_name}) with ownership {account.ownership_type}",
    )

    return _format_account_response(account, db)


@router.get("/{account_id}", response_model=EmergentAccountResponse)
def get_account(
    account_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    account = db.query(EmergentAccount).filter(EmergentAccount.id == account_id).first()
    if not account:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Account not found.")

    user_role = current_user.role.name if current_user.role else "MEMBER"
    if user_role != "ADMIN" and account.owner_user_id != current_user.id:
        perm = (
            db.query(AccountPermission)
            .filter(
                AccountPermission.account_id == account_id,
                AccountPermission.user_id == current_user.id,
                AccountPermission.can_view == True,
            )
            .first()
        )
        if not perm:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access to this account is unauthorized.")

    return _format_account_response(account, db)


@router.patch("/{account_id}", response_model=EmergentAccountResponse)
@router.put("/{account_id}", response_model=EmergentAccountResponse)
def update_account(
    account_id: int,
    request: Request,
    payload: EmergentAccountUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    account = db.query(EmergentAccount).filter(EmergentAccount.id == account_id).first()
    if not account:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Account not found.")

    user_role = current_user.role.name if current_user.role else "MEMBER"
    is_owner = account.owner_user_id == current_user.id

    # Check permission
    if user_role != "ADMIN" and not is_owner:
        perm = (
            db.query(AccountPermission)
            .filter(
                AccountPermission.account_id == account_id,
                AccountPermission.user_id == current_user.id,
                AccountPermission.can_manage == True,
            )
            .first()
        )
        if not perm:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Management permission required to update account.")

    # Members cannot modify ownership
    if payload.ownership_type is not None and user_role not in ["ADMIN"] and not is_owner:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Only account owner or Admin may change ownership type.")

    if payload.account_name is not None:
        account.account_name = payload.account_name
    if payload.email is not None:
        account.email = payload.email
    if payload.organization is not None:
        account.organization = payload.organization
    if payload.owner_user_id is not None:
        account.owner_user_id = payload.owner_user_id
    if payload.owner_name is not None:
        account.owner_name = payload.owner_name
    if payload.ownership_type is not None:
        account.ownership_type = payload.ownership_type.upper()
    if payload.description is not None:
        account.description = payload.description
    if payload.status is not None:
        account.status = payload.status
    if payload.auth_type is not None:
        account.auth_type = payload.auth_type
    if payload.connection_status is not None:
        account.connection_status = payload.connection_status.upper()
    if payload.credit_sync_status is not None:
        account.credit_sync_status = payload.credit_sync_status

    account.updated_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(account)

    record_audit(
        db=db,
        action="account_updated",
        resource_type="account",
        resource_id=str(account.id),
        user_id=current_user.id,
        ip_address=request.client.host if request.client else None,
        details=f"Updated account {account.account_identifier} ({account.account_name})",
    )

    return _format_account_response(account, db)


@router.delete("/{account_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_account(
    account_id: int,
    request: Request,
    current_user: User = Depends(require_role(["ADMIN"])),
    db: Session = Depends(get_db),
):
    account = db.query(EmergentAccount).filter(EmergentAccount.id == account_id).first()
    if not account:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Account not found.")

    record_audit(
        db=db,
        action="account_deleted",
        resource_type="account",
        resource_id=str(account.id),
        user_id=current_user.id,
        ip_address=request.client.host if request.client else None,
        details=f"Deleted Emergent account {account.account_identifier}",
    )

    db.delete(account)
    db.commit()
    return None


@router.post("/{account_id}/sync")
def sync_account_connection(
    account_id: int,
    request: Request,
    current_user: User = Depends(require_role(["ADMIN", "MANAGER"])),
    db: Session = Depends(get_db),
):
    account = db.query(EmergentAccount).filter(EmergentAccount.id == account_id).first()
    if not account:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Account not found.")

    status_info = emergent_integration_service.check_connection_status(account.account_identifier)
    account.last_synced_at = datetime.now(timezone.utc)
    db.commit()

    record_audit(
        db=db,
        action="account_synced",
        resource_type="account",
        resource_id=str(account.id),
        user_id=current_user.id,
        ip_address=request.client.host if request.client else None,
        details=f"Health sync invoked for {account.account_identifier}",
    )

    return {
        "account_id": account.id,
        "account_identifier": account.account_identifier,
        "connection_status": account.connection_status,
        "sync_result": status_info,
        "last_synced_at": account.last_synced_at,
    }


# =========================================================================
# Connection & OAuth Lifecycle Endpoints (Section 7)
# =========================================================================

@router.post("/{account_id}/connect")
def connect_account(
    account_id: int,
    request: Request,
    auth_code: Optional[str] = Query(None, description="Optional OAuth authorization code"),
    current_user: User = Depends(require_role(["ADMIN", "MANAGER"])),
    db: Session = Depends(get_db),
):
    account = db.query(EmergentAccount).filter(EmergentAccount.id == account_id).first()
    if not account:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Account not found.")

    result = connection_service.connect_account(db, account, auth_code=auth_code)

    record_audit(
        db=db,
        action="account_connected",
        resource_type="account",
        resource_id=str(account.id),
        user_id=current_user.id,
        ip_address=request.client.host if request.client else None,
        details=f"Connection requested for {account.account_identifier}: status={result['status']}",
    )
    return result


@router.get("/{account_id}/connection", response_model=AccountConnectionResponse)
def get_account_connection(
    account_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    account = db.query(EmergentAccount).filter(EmergentAccount.id == account_id).first()
    if not account:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Account not found.")

    conn = connection_service.get_or_create_connection(db, account)
    connection_service.check_health(db, account)
    db.refresh(conn)

    return AccountConnectionResponse(
        id=conn.id,
        account_id=conn.account_id,
        provider=conn.provider,
        connection_type=conn.connection_type,
        status=conn.status,
        token_expires_at=conn.token_expires_at,
        last_health_check=conn.last_health_check,
        error_message=conn.error_message,
        has_access_token=bool(conn.access_token_enc),
        has_refresh_token=bool(conn.refresh_token_enc),
        created_at=conn.created_at,
    )


@router.post("/{account_id}/reconnect")
def reconnect_account(
    account_id: int,
    request: Request,
    current_user: User = Depends(require_role(["ADMIN", "MANAGER"])),
    db: Session = Depends(get_db),
):
    account = db.query(EmergentAccount).filter(EmergentAccount.id == account_id).first()
    if not account:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Account not found.")

    result = connection_service.reconnect_account(db, account)

    record_audit(
        db=db,
        action="account_reconnected",
        resource_type="account",
        resource_id=str(account.id),
        user_id=current_user.id,
        ip_address=request.client.host if request.client else None,
        details=f"Reconnect initiated for {account.account_identifier}: status={result['status']}",
    )
    return result


@router.post("/{account_id}/disconnect")
def disconnect_account(
    account_id: int,
    request: Request,
    current_user: User = Depends(require_role(["ADMIN", "MANAGER"])),
    db: Session = Depends(get_db),
):
    account = db.query(EmergentAccount).filter(EmergentAccount.id == account_id).first()
    if not account:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Account not found.")

    result = connection_service.disconnect_account(db, account)

    record_audit(
        db=db,
        action="account_disconnected",
        resource_type="account",
        resource_id=str(account.id),
        user_id=current_user.id,
        ip_address=request.client.host if request.client else None,
        details=f"Account {account.account_identifier} disconnected and credentials revoked.",
    )
    return result


# =========================================================================
# Team Member Account Assignments (Section 6 & 7)
# =========================================================================

@router.get("/{account_id}/members", response_model=List[AccountMemberResponse])
def list_account_members(
    account_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    account = db.query(EmergentAccount).filter(EmergentAccount.id == account_id).first()
    if not account:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Account not found.")

    perms = db.query(AccountPermission).filter(AccountPermission.account_id == account_id).all()
    results = []
    for p in perms:
        u = p.user
        results.append(
            AccountMemberResponse(
                id=p.id,
                user_id=p.user_id,
                account_id=p.account_id,
                email=u.email,
                full_name=u.full_name,
                role_name=u.role.name if u.role else "MEMBER",
                can_view=p.can_view,
                can_execute=p.can_execute,
                can_manage=p.can_manage,
                created_at=p.created_at,
            )
        )
    return results


@router.post("/{account_id}/members", response_model=AccountMemberResponse, status_code=status.HTTP_201_CREATED)
def assign_account_member(
    account_id: int,
    request: Request,
    payload: AccountMemberAssignRequest,
    current_user: User = Depends(require_role(["ADMIN", "MANAGER"])),
    db: Session = Depends(get_db),
):
    account = db.query(EmergentAccount).filter(EmergentAccount.id == account_id).first()
    if not account:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Account not found.")

    target_user = db.query(User).filter(User.id == payload.user_id).first()
    if not target_user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Target user not found.")

    # Rule from Section 6: PERSONAL accounts require explicit account-owner authorization
    user_role = current_user.role.name if current_user.role else "MEMBER"
    if account.ownership_type == "PERSONAL" and user_role != "ADMIN" and account.owner_user_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Personal accounts require explicit authorization by the account owner to assign team members.",
        )

    # Check if assignment already exists
    perm = (
        db.query(AccountPermission)
        .filter(AccountPermission.account_id == account_id, AccountPermission.user_id == payload.user_id)
        .first()
    )
    if perm:
        perm.can_view = payload.can_view
        perm.can_execute = payload.can_execute
        perm.can_manage = payload.can_manage
    else:
        perm = AccountPermission(
            user_id=payload.user_id,
            account_id=account_id,
            can_view=payload.can_view,
            can_execute=payload.can_execute,
            can_manage=payload.can_manage,
        )
        db.add(perm)

    db.commit()
    db.refresh(perm)

    record_audit(
        db=db,
        action="account_member_assigned",
        resource_type="account_permission",
        resource_id=str(perm.id),
        user_id=current_user.id,
        ip_address=request.client.host if request.client else None,
        details=f"Assigned member {target_user.email} to account {account.account_identifier} (view={perm.can_view}, exec={perm.can_execute}, manage={perm.can_manage})",
    )

    return AccountMemberResponse(
        id=perm.id,
        user_id=perm.user_id,
        account_id=perm.account_id,
        email=target_user.email,
        full_name=target_user.full_name,
        role_name=target_user.role.name if target_user.role else "MEMBER",
        can_view=perm.can_view,
        can_execute=perm.can_execute,
        can_manage=perm.can_manage,
        created_at=perm.created_at,
    )


@router.delete("/{account_id}/members/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
def remove_account_member(
    account_id: int,
    user_id: int,
    request: Request,
    current_user: User = Depends(require_role(["ADMIN", "MANAGER"])),
    db: Session = Depends(get_db),
):
    account = db.query(EmergentAccount).filter(EmergentAccount.id == account_id).first()
    if not account:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Account not found.")

    perm = (
        db.query(AccountPermission)
        .filter(AccountPermission.account_id == account_id, AccountPermission.user_id == user_id)
        .first()
    )
    if not perm:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Member assignment not found.")

    record_audit(
        db=db,
        action="account_member_revoked",
        resource_type="account_permission",
        resource_id=str(perm.id),
        user_id=current_user.id,
        ip_address=request.client.host if request.client else None,
        details=f"Revoked access for user ID {user_id} on account {account.account_identifier}",
    )

    db.delete(perm)
    db.commit()
    return None


@router.get("/{account_id}/activity", response_model=List[AuditLogResponse])
def get_account_activity(
    account_id: int,
    limit: int = 50,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    account = db.query(EmergentAccount).filter(EmergentAccount.id == account_id).first()
    if not account:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Account not found.")

    logs = (
        db.query(AuditLog)
        .filter(
            or_(
                AuditLog.resource_id == str(account_id),
                AuditLog.details.ilike(f"%{account.account_identifier}%"),
            )
        )
        .order_by(AuditLog.created_at.desc())
        .limit(limit)
        .all()
    )
    return logs
