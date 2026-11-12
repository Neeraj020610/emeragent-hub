import time
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from fastapi import HTTPException, status
from sqlalchemy.orm import Session
from sqlalchemy import func, desc

from app.core.security import encrypt_token, decrypt_token
from app.models.user import User
from app.models.account import EmergentAccount, AccountPermission, PersonalAccountConsent
from app.models.universal_key import UniversalApiKey, UniversalKeyUsage
from app.models.audit import AuditLog
from app.schemas.universal_key import (
    UniversalKeyAccountRegisterRequest,
    UniversalKeyAddRequest,
    UniversalKeyUpdateRequest,
    UniversalKeyResponse,
    UniversalKeyValidateResponse,
    UniversalKeyChatRequest,
    UniversalKeyChatResponse,
    UniversalKeyUsageResponse,
    UniversalKeyStatsResponse,
)
from app.services.universal_key.client import EmergentProxyClient


def utcnow():
    return datetime.now(timezone.utc)


def mask_key(prefix: str, last4: str) -> str:
    """Safely format masked key string without revealing raw secret."""
    return f"{prefix}••••••••••••{last4}"


class UniversalKeyService:
    def __init__(self, proxy_client: Optional[EmergentProxyClient] = None):
        self.proxy_client = proxy_client or EmergentProxyClient()

    def _format_key_response(self, key: UniversalApiKey, account: Optional[EmergentAccount] = None) -> UniversalKeyResponse:
        acc = account or key.account
        return UniversalKeyResponse(
            id=key.id,
            account_id=key.account_id,
            account_name=acc.account_name if acc else "Unknown",
            account_email=acc.email if acc else None,
            key_name=key.key_name,
            masked_key=mask_key(key.key_prefix, key.key_last4),
            key_prefix=key.key_prefix,
            key_last4=key.key_last4,
            proxy_base_url=key.proxy_base_url,
            is_active=key.is_active,
            validation_status=key.validation_status,
            validation_message=key.validation_message,
            last_validated_at=key.last_validated_at,
            created_at=key.created_at,
            updated_at=key.updated_at,
        )

    async def register_account_with_key(
        self,
        db: Session,
        payload: UniversalKeyAccountRegisterRequest,
        current_user: User,
        client_ip: Optional[str] = None,
    ) -> UniversalKeyResponse:
        """
        Direct registration of an Emergent account using ONLY:
        1. Account Display Name
        2. Universal API Key
        3. Optional email metadata (never used for auth)
        No Emergent email/password login or OTP required.
        Validates key against proxy before registration.
        """
        clean_key = payload.api_key.strip()
        proxy_url = (payload.proxy_base_url or "https://proxy.emergent.ai").strip()

        # 1. Validation check
        if payload.validate_first:
            val_res = await self.proxy_client.validate_key(clean_key, proxy_url)
            if not val_res.is_valid:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Universal API Key validation failed ({val_res.status_code}): {val_res.message}",
                )

        # 2. Extract prefix and suffix for safe display
        prefix = clean_key[:8] if len(clean_key) >= 12 else clean_key[:4]
        last4 = clean_key[-4:] if len(clean_key) >= 4 else clean_key

        # 3. Encrypt key before database storage
        encrypted_key = encrypt_token(clean_key)

        # 4. Generate unique account identifier
        uid = uuid.uuid4().hex[:8]
        account_identifier = f"emg-key-{uid}"

        # 5. Create distinct API-connected account
        # Distinguish clearly: auth_type="universal_key", connection_status="API_CONNECTED"
        account = EmergentAccount(
            account_identifier=account_identifier,
            account_name=payload.account_name.strip(),
            email=payload.email.strip() if payload.email else None,
            owner_user_id=current_user.id,
            owner_name=current_user.full_name,
            ownership_type=payload.ownership_type.upper(),
            description=payload.description,
            status="active",
            auth_type="universal_key",
            connection_status="API_CONNECTED",
            credit_sync_status="universal_proxy",
            last_connected_at=utcnow(),
        )
        db.add(account)
        db.flush()

        # 6. Create UniversalApiKey record
        uni_key = UniversalApiKey(
            account_id=account.id,
            key_name=f"{payload.account_name.strip()} Primary Key",
            api_key_enc=encrypted_key,
            key_prefix=prefix,
            key_last4=last4,
            proxy_base_url=proxy_url,
            is_active=True,
            created_by_user_id=current_user.id,
            last_validated_at=utcnow(),
            validation_status="VALID",
            validation_message="Key verified successfully against official Emergent proxy.",
        )
        db.add(uni_key)

        # 7. Grant creator account permissions
        perm = AccountPermission(
            user_id=current_user.id,
            account_id=account.id,
            can_view=True,
            can_execute=True,
            can_manage=True,
        )
        db.add(perm)

        # 8. Record audit log
        audit = AuditLog(
            user_id=current_user.id,
            action="universal_key_account_registered",
            resource_type="account",
            resource_id=str(account.id),
            details=(
                f"Registered account '{account.account_name}' ({account.account_identifier}) via "
                f"Universal API Key ({mask_key(prefix, last4)}). No email login required."
            ),
            ip_address=client_ip,
        )
        db.add(audit)
        db.commit()
        db.refresh(uni_key)
        db.refresh(account)

        return self._format_key_response(uni_key, account)

    async def add_key_to_account(
        self,
        db: Session,
        payload: UniversalKeyAddRequest,
        current_user: User,
        client_ip: Optional[str] = None,
    ) -> UniversalKeyResponse:
        """Add an additional Universal API Key to an existing account."""
        account = db.query(EmergentAccount).filter(EmergentAccount.id == payload.account_id).first()
        if not account:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Account not found")

        # Permission check
        user_role = current_user.role.name if current_user.role else "MEMBER"
        if user_role not in ("ADMIN", "MANAGER"):
            perm = (
                db.query(AccountPermission)
                .filter(AccountPermission.account_id == account.id, AccountPermission.user_id == current_user.id)
                .first()
            )
            if not perm or not perm.can_manage:
                raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Management permission required")

        clean_key = payload.api_key.strip()
        proxy_url = (payload.proxy_base_url or "https://proxy.emergent.ai").strip()

        if payload.validate_first:
            val_res = await self.proxy_client.validate_key(clean_key, proxy_url)
            if not val_res.is_valid:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Key validation failed ({val_res.status_code}): {val_res.message}",
                )

        prefix = clean_key[:8] if len(clean_key) >= 12 else clean_key[:4]
        last4 = clean_key[-4:] if len(clean_key) >= 4 else clean_key
        encrypted_key = encrypt_token(clean_key)

        uni_key = UniversalApiKey(
            account_id=account.id,
            key_name=payload.key_name.strip(),
            api_key_enc=encrypted_key,
            key_prefix=prefix,
            key_last4=last4,
            proxy_base_url=proxy_url,
            is_active=True,
            created_by_user_id=current_user.id,
            last_validated_at=utcnow(),
            validation_status="VALID",
            validation_message="Key verified successfully.",
        )
        db.add(uni_key)

        if account.connection_status == "DISCONNECTED":
            account.connection_status = "API_CONNECTED"

        audit = AuditLog(
            user_id=current_user.id,
            action="universal_key_added",
            resource_type="universal_key",
            resource_id=str(account.id),
            details=f"Added Universal API Key '{uni_key.key_name}' ({mask_key(prefix, last4)}) to account '{account.account_name}'",
            ip_address=client_ip,
        )
        db.add(audit)
        db.commit()
        db.refresh(uni_key)

        return self._format_key_response(uni_key, account)

    def list_keys(
        self,
        db: Session,
        current_user: User,
        account_id: Optional[int] = None,
    ) -> List[UniversalKeyResponse]:
        """List keys with masked credentials."""
        user_role = current_user.role.name if current_user.role else "MEMBER"
        query = db.query(UniversalApiKey).join(EmergentAccount)

        if account_id:
            query = query.filter(UniversalApiKey.account_id == account_id)

        if user_role != "ADMIN":
            permitted_ids = (
                db.query(AccountPermission.account_id)
                .filter(AccountPermission.user_id == current_user.id, AccountPermission.can_view == True)
                .subquery()
            )
            query = query.filter(
                (UniversalApiKey.account_id.in_(permitted_ids))
                | (EmergentAccount.owner_user_id == current_user.id)
            )

        keys = query.order_by(desc(UniversalApiKey.created_at)).all()
        return [self._format_key_response(k) for k in keys]

    def get_key(self, db: Session, key_id: int, current_user: User) -> UniversalKeyResponse:
        key = db.query(UniversalApiKey).filter(UniversalApiKey.id == key_id).first()
        if not key:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Universal API Key not found")
        return self._format_key_response(key)

    def update_key(
        self,
        db: Session,
        key_id: int,
        payload: UniversalKeyUpdateRequest,
        current_user: User,
        client_ip: Optional[str] = None,
    ) -> UniversalKeyResponse:
        key = db.query(UniversalApiKey).filter(UniversalApiKey.id == key_id).first()
        if not key:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Universal API Key not found")

        user_role = current_user.role.name if current_user.role else "MEMBER"
        if user_role not in ("ADMIN", "MANAGER"):
            perm = (
                db.query(AccountPermission)
                .filter(AccountPermission.account_id == key.account_id, AccountPermission.user_id == current_user.id)
                .first()
            )
            if not perm or not perm.can_manage:
                raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Management permission required")

        if payload.key_name is not None:
            key.key_name = payload.key_name.strip()
        if payload.proxy_base_url is not None:
            key.proxy_base_url = payload.proxy_base_url.strip()
        if payload.is_active is not None:
            key.is_active = payload.is_active

        key.updated_at = utcnow()
        db.commit()
        db.refresh(key)

        return self._format_key_response(key)

    async def validate_existing_key(
        self,
        db: Session,
        key_id: int,
        current_user: User,
        client_ip: Optional[str] = None,
    ) -> UniversalKeyValidateResponse:
        """Re-validate an existing stored key against the Emergent proxy."""
        key = db.query(UniversalApiKey).filter(UniversalApiKey.id == key_id).first()
        if not key:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Universal API Key not found")

        plain_key = decrypt_token(key.api_key_enc)
        if not plain_key:
            key.validation_status = "ERROR"
            key.validation_message = "Decryption failure"
            db.commit()
            return UniversalKeyValidateResponse(
                is_valid=False, status_code=500, message="Failed to decrypt stored API key.", latency_ms=0
            )

        val_res = await self.proxy_client.validate_key(plain_key, key.proxy_base_url)
        key.last_validated_at = utcnow()
        key.validation_status = "VALID" if val_res.is_valid else "INVALID"
        key.validation_message = val_res.message
        db.commit()

        # Audit
        audit = AuditLog(
            user_id=current_user.id,
            action="universal_key_validated",
            resource_type="universal_key",
            resource_id=str(key.id),
            details=f"Validated key '{key.key_name}': valid={val_res.is_valid}, status={val_res.status_code}",
            ip_address=client_ip,
        )
        db.add(audit)
        db.commit()

        return val_res

    def delete_key(
        self,
        db: Session,
        key_id: int,
        current_user: User,
        client_ip: Optional[str] = None,
    ) -> Dict[str, Any]:
        key = db.query(UniversalApiKey).filter(UniversalApiKey.id == key_id).first()
        if not key:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Universal API Key not found")

        user_role = current_user.role.name if current_user.role else "MEMBER"
        if user_role not in ("ADMIN", "MANAGER"):
            perm = (
                db.query(AccountPermission)
                .filter(AccountPermission.account_id == key.account_id, AccountPermission.user_id == current_user.id)
                .first()
            )
            if not perm or not perm.can_manage:
                raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Management permission required")

        account_id = key.account_id
        key_name = key.key_name
        masked = mask_key(key.key_prefix, key.key_last4)

        db.delete(key)
        db.flush()

        # Check remaining active keys for account
        remaining = db.query(UniversalApiKey).filter(UniversalApiKey.account_id == account_id).count()
        if remaining == 0:
            account = db.query(EmergentAccount).filter(EmergentAccount.id == account_id).first()
            if account and account.auth_type == "universal_key":
                account.connection_status = "DISCONNECTED"

        audit = AuditLog(
            user_id=current_user.id,
            action="universal_key_deleted",
            resource_type="universal_key",
            resource_id=str(key_id),
            details=f"Deleted Universal API Key '{key_name}' ({masked})",
            ip_address=client_ip,
        )
        db.add(audit)
        db.commit()

        return {"status": "success", "message": f"Universal API Key '{key_name}' deleted successfully."}

    async def execute_chat_inference(
        self,
        db: Session,
        payload: UniversalKeyChatRequest,
        current_user: User,
        client_ip: Optional[str] = None,
    ) -> UniversalKeyChatResponse:
        """
        Secure inference gateway:
        1. Validates user permission on target Emergent account.
        2. Personal account consent check if applicable.
        3. Decrypts key in-memory only.
        4. Invokes LiteLLM proxy.
        5. Logs usage record and audit event.
        """
        # Determine target key & account
        if payload.key_id:
            key = db.query(UniversalApiKey).filter(UniversalApiKey.id == payload.key_id).first()
            if not key or not key.is_active:
                raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Active Universal API Key not found")
            account = key.account
        elif payload.account_id:
            account = db.query(EmergentAccount).filter(EmergentAccount.id == payload.account_id).first()
            if not account:
                raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Account not found")
            key = (
                db.query(UniversalApiKey)
                .filter(UniversalApiKey.account_id == account.id, UniversalApiKey.is_active == True)
                .first()
            )
            if not key:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"No active Universal API Key registered for account '{account.account_name}'",
                )
        else:
            # Pick first available active key accessible to user
            user_role = current_user.role.name if current_user.role else "MEMBER"
            query = db.query(UniversalApiKey).join(EmergentAccount).filter(UniversalApiKey.is_active == True)
            if user_role != "ADMIN":
                permitted_ids = (
                    db.query(AccountPermission.account_id)
                    .filter(AccountPermission.user_id == current_user.id, AccountPermission.can_execute == True)
                    .subquery()
                )
                query = query.filter(
                    (UniversalApiKey.account_id.in_(permitted_ids))
                    | (EmergentAccount.owner_user_id == current_user.id)
                )
            key = query.first()
            if not key:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="No active Universal API Key found accessible to your account.",
                )
            account = key.account

        # Access check
        user_role = current_user.role.name if current_user.role else "MEMBER"
        if user_role != "ADMIN" and account.owner_user_id != current_user.id:
            perm = (
                db.query(AccountPermission)
                .filter(AccountPermission.account_id == account.id, AccountPermission.user_id == current_user.id)
                .first()
            )
            if not perm or not (perm.can_execute or perm.can_manage):
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail=f"Execution permission required for account '{account.account_name}'",
                )

        # Personal account consent enforcement
        if account.ownership_type == "PERSONAL" and account.owner_user_id != current_user.id:
            consent = (
                db.query(PersonalAccountConsent)
                .filter(
                    PersonalAccountConsent.account_id == account.id,
                    PersonalAccountConsent.authorized_member_id == current_user.id,
                    PersonalAccountConsent.is_active == True,
                )
                .first()
            )
            if not consent:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail=f"Active personal account consent required to execute using account '{account.account_name}'",
                )

        plain_key = decrypt_token(key.api_key_enc)
        if not plain_key:
            raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to decrypt key")

        messages_dict = [{"role": m.role, "content": m.content} for m in payload.messages]

        try:
            inference_res = await self.proxy_client.execute_chat(
                api_key=plain_key,
                proxy_base_url=key.proxy_base_url,
                model=payload.model,
                messages=messages_dict,
                temperature=payload.temperature or 0.7,
                max_tokens=payload.max_tokens or 500,
            )
        except Exception as ex:
            # Log failed usage record
            usage_rec = UniversalKeyUsage(
                key_id=key.id,
                account_id=account.id,
                user_id=current_user.id,
                request_id=f"req-err-{uuid.uuid4().hex[:8]}",
                model=payload.model,
                prompt_tokens=0,
                completion_tokens=0,
                total_tokens=0,
                cost=0.0,
                duration_ms=0,
                status="ERROR",
                error_reason=str(ex),
            )
            db.add(usage_rec)
            db.commit()
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail=f"Inference proxy execution error: {str(ex)}",
            )

        # Log successful usage record
        usage_rec = UniversalKeyUsage(
            key_id=key.id,
            account_id=account.id,
            user_id=current_user.id,
            request_id=inference_res["request_id"],
            model=inference_res["model"],
            prompt_tokens=inference_res["prompt_tokens"],
            completion_tokens=inference_res["completion_tokens"],
            total_tokens=inference_res["total_tokens"],
            cost=inference_res.get("cost"),
            duration_ms=inference_res["duration_ms"],
            status="SUCCESS",
        )
        db.add(usage_rec)

        audit = AuditLog(
            user_id=current_user.id,
            action="universal_key_chat_executed",
            resource_type="universal_key",
            resource_id=str(key.id),
            details=(
                f"Executed chat inference model='{inference_res['model']}' "
                f"tokens={inference_res['total_tokens']} account='{account.account_name}'"
            ),
            ip_address=client_ip,
        )
        db.add(audit)
        db.commit()

        return UniversalKeyChatResponse(
            request_id=inference_res["request_id"],
            account_id=account.id,
            key_id=key.id,
            model=inference_res["model"],
            content=inference_res["content"],
            prompt_tokens=inference_res["prompt_tokens"],
            completion_tokens=inference_res["completion_tokens"],
            total_tokens=inference_res["total_tokens"],
            cost=inference_res.get("cost"),
            duration_ms=inference_res["duration_ms"],
            status="SUCCESS",
        )

    def list_usage_ledger(
        self,
        db: Session,
        current_user: User,
        account_id: Optional[int] = None,
        limit: int = 50,
    ) -> List[UniversalKeyUsageResponse]:
        user_role = current_user.role.name if current_user.role else "MEMBER"
        query = db.query(UniversalKeyUsage).join(EmergentAccount)

        if account_id:
            query = query.filter(UniversalKeyUsage.account_id == account_id)

        if user_role != "ADMIN":
            permitted_ids = (
                db.query(AccountPermission.account_id)
                .filter(AccountPermission.user_id == current_user.id, AccountPermission.can_view == True)
                .subquery()
            )
            query = query.filter(
                (UniversalKeyUsage.account_id.in_(permitted_ids))
                | (EmergentAccount.owner_user_id == current_user.id)
            )

        records = query.order_by(desc(UniversalKeyUsage.created_at)).limit(limit).all()

        results = []
        for r in records:
            acc_name = r.account.account_name if r.account else "Unknown"
            u_name = r.user.full_name if r.user else "System"
            results.append(
                UniversalKeyUsageResponse(
                    id=r.id,
                    key_id=r.key_id,
                    account_id=r.account_id,
                    account_name=acc_name,
                    user_id=r.user_id,
                    user_name=u_name,
                    request_id=r.request_id,
                    model=r.model,
                    prompt_tokens=r.prompt_tokens,
                    completion_tokens=r.completion_tokens,
                    total_tokens=r.total_tokens,
                    cost=float(r.cost) if r.cost is not None else None,
                    duration_ms=r.duration_ms,
                    status=r.status,
                    error_reason=r.error_reason,
                    created_at=r.created_at,
                )
            )
        return results

    def get_dashboard_stats(self, db: Session, current_user: User) -> UniversalKeyStatsResponse:
        user_role = current_user.role.name if current_user.role else "MEMBER"
        key_query = db.query(UniversalApiKey).join(EmergentAccount)
        usage_query = db.query(UniversalKeyUsage).join(EmergentAccount)

        if user_role != "ADMIN":
            permitted_ids = (
                db.query(AccountPermission.account_id)
                .filter(AccountPermission.user_id == current_user.id, AccountPermission.can_view == True)
                .subquery()
            )
            key_query = key_query.filter(
                (UniversalApiKey.account_id.in_(permitted_ids)) | (EmergentAccount.owner_user_id == current_user.id)
            )
            usage_query = usage_query.filter(
                (UniversalKeyUsage.account_id.in_(permitted_ids)) | (EmergentAccount.owner_user_id == current_user.id)
            )

        total_keys = key_query.count()
        active_keys = key_query.filter(UniversalApiKey.is_active == True).count()

        total_requests = usage_query.count()
        successful_requests = usage_query.filter(UniversalKeyUsage.status == "SUCCESS").count()
        failed_requests = total_requests - successful_requests

        total_tokens = db.query(func.coalesce(func.sum(UniversalKeyUsage.total_tokens), 0)).scalar() or 0
        total_cost = db.query(func.coalesce(func.sum(UniversalKeyUsage.cost), 0.0)).scalar() or 0.0

        return UniversalKeyStatsResponse(
            total_keys=total_keys,
            active_keys=active_keys,
            total_requests=total_requests,
            successful_requests=successful_requests,
            failed_requests=failed_requests,
            total_tokens=int(total_tokens),
            total_cost=float(total_cost),
        )

