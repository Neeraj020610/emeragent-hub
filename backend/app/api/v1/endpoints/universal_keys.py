from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.user import User
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
from app.services.universal_key.service import UniversalKeyService
from app.dependencies import get_current_user, require_role

router = APIRouter()
key_service = UniversalKeyService()


@router.post("/register-account", response_model=UniversalKeyResponse, status_code=status.HTTP_201_CREATED)
async def register_account_with_universal_key(
    payload: UniversalKeyAccountRegisterRequest,
    request: Request,
    current_user: User = Depends(require_role(["ADMIN", "MANAGER"])),
    db: Session = Depends(get_db),
):
    """
    Directly register an Emergent account with Universal API Key:
    - Only requires Account Display Name and Universal API Key.
    - Email is optional metadata only.
    - No Emergent email/password login or OTP required.
    - Performs validation against official proxy before registering.
    - Encrypts API key at rest before storing in DB.
    """
    client_ip = request.client.host if request.client else None
    return await key_service.register_account_with_key(
        db=db,
        payload=payload,
        current_user=current_user,
        client_ip=client_ip,
    )


@router.post("", response_model=UniversalKeyResponse, status_code=status.HTTP_201_CREATED)
async def add_universal_key(
    payload: UniversalKeyAddRequest,
    request: Request,
    current_user: User = Depends(require_role(["ADMIN", "MANAGER"])),
    db: Session = Depends(get_db),
):
    """Add an additional Universal API Key to an existing account."""
    client_ip = request.client.host if request.client else None
    return await key_service.add_key_to_account(
        db=db,
        payload=payload,
        current_user=current_user,
        client_ip=client_ip,
    )


@router.get("", response_model=List[UniversalKeyResponse])
def list_universal_keys(
    account_id: Optional[int] = Query(None, description="Filter keys by account ID"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """List all registered Universal API Keys with masked credentials."""
    return key_service.list_keys(db=db, current_user=current_user, account_id=account_id)


@router.get("/stats", response_model=UniversalKeyStatsResponse)
def get_universal_key_stats(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Get aggregated metrics and usage overview for Universal API Keys."""
    return key_service.get_dashboard_stats(db=db, current_user=current_user)


@router.get("/usage", response_model=List[UniversalKeyUsageResponse])
def get_usage_ledger(
    account_id: Optional[int] = Query(None, description="Filter by account ID"),
    limit: int = Query(50, ge=1, le=200),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Get historical LLM proxy usage ledger with tokens, duration, and models."""
    return key_service.list_usage_ledger(db=db, current_user=current_user, account_id=account_id, limit=limit)


@router.get("/{key_id}", response_model=UniversalKeyResponse)
def get_universal_key(
    key_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Get metadata for a specific Universal API Key (always masked)."""
    return key_service.get_key(db=db, key_id=key_id, current_user=current_user)


@router.put("/{key_id}", response_model=UniversalKeyResponse)
def update_universal_key(
    key_id: int,
    payload: UniversalKeyUpdateRequest,
    request: Request,
    current_user: User = Depends(require_role(["ADMIN", "MANAGER"])),
    db: Session = Depends(get_db),
):
    """Update key properties (name, proxy URL, active status)."""
    client_ip = request.client.host if request.client else None
    return key_service.update_key(
        db=db,
        key_id=key_id,
        payload=payload,
        current_user=current_user,
        client_ip=client_ip,
    )


@router.post("/{key_id}/validate", response_model=UniversalKeyValidateResponse)
async def validate_existing_key(
    key_id: int,
    request: Request,
    current_user: User = Depends(require_role(["ADMIN", "MANAGER"])),
    db: Session = Depends(get_db),
):
    """Re-validate an existing key against the official proxy without exposing the secret."""
    client_ip = request.client.host if request.client else None
    return await key_service.validate_existing_key(
        db=db,
        key_id=key_id,
        current_user=current_user,
        client_ip=client_ip,
    )


@router.delete("/{key_id}")
def delete_universal_key(
    key_id: int,
    request: Request,
    current_user: User = Depends(require_role(["ADMIN", "MANAGER"])),
    db: Session = Depends(get_db),
):
    """Revoke and delete a Universal API Key."""
    client_ip = request.client.host if request.client else None
    return key_service.delete_key(
        db=db,
        key_id=key_id,
        current_user=current_user,
        client_ip=client_ip,
    )


@router.post("/chat", response_model=UniversalKeyChatResponse)
async def execute_chat(
    payload: UniversalKeyChatRequest,
    request: Request,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Secure LiteLLM inference gateway:
    - Authorized users can issue inference prompts via official Emergent proxy.
    - Decrypts key in-memory only.
    - Verifies RBAC and personal consent where applicable.
    - Records prompt tokens, completion tokens, latency and cost.
    """
    client_ip = request.client.host if request.client else None
    return await key_service.execute_chat_inference(
        db=db,
        payload=payload,
        current_user=current_user,
        client_ip=client_ip,
    )

