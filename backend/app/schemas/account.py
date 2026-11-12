from datetime import datetime
from decimal import Decimal
from typing import Optional, List
from pydantic import BaseModel, EmailStr, ConfigDict


class AccountPermissionBase(BaseModel):
    user_id: int
    account_id: int
    can_view: bool = True
    can_execute: bool = False
    can_manage: bool = False


class AccountPermissionCreate(AccountPermissionBase):
    pass


class AccountPermissionResponse(AccountPermissionBase):
    id: int
    created_at: datetime
    model_config = ConfigDict(from_attributes=True)


class AccountMemberAssignRequest(BaseModel):
    user_id: int
    can_view: bool = True
    can_execute: bool = False
    can_manage: bool = False


class AccountMemberResponse(BaseModel):
    id: int
    user_id: int
    account_id: int
    email: EmailStr
    full_name: str
    role_name: str
    can_view: bool
    can_execute: bool
    can_manage: bool
    created_at: datetime
    model_config = ConfigDict(from_attributes=True)


class AccountConnectionResponse(BaseModel):
    id: int
    account_id: int
    provider: str
    connection_type: str
    status: str  # CONNECTED, DISCONNECTED, EXPIRED, AUTHORIZATION_REQUIRED, ERROR, PENDING
    token_expires_at: Optional[datetime] = None
    last_health_check: Optional[datetime] = None
    error_message: Optional[str] = None
    has_access_token: bool = False
    has_refresh_token: bool = False
    created_at: datetime
    model_config = ConfigDict(from_attributes=True)


class EmergentAccountBase(BaseModel):
    account_identifier: Optional[str] = None
    account_name: str
    email: Optional[str] = None
    organization: Optional[str] = None
    owner_user_id: Optional[int] = None
    owner_name: Optional[str] = None
    ownership_type: str = "COMPANY_OWNED"  # COMPANY_OWNED, PERSONAL
    description: Optional[str] = None
    status: str = "active"
    auth_type: str = "oauth"


class EmergentAccountCreate(EmergentAccountBase):
    email: Optional[str] = None
    password: Optional[str] = None
    mailbox_email: Optional[str] = None
    connection_status: str = "DISCONNECTED"
    credit_sync_status: str = "manual_only"


class EmergentAccountUpdate(BaseModel):
    account_name: Optional[str] = None
    email: Optional[str] = None
    organization: Optional[str] = None
    owner_user_id: Optional[int] = None
    owner_name: Optional[str] = None
    ownership_type: Optional[str] = None
    description: Optional[str] = None
    status: Optional[str] = None
    auth_type: Optional[str] = None
    connection_status: Optional[str] = None
    credit_sync_status: Optional[str] = None


class EmergentAccountResponse(EmergentAccountBase):
    id: int
    account_identifier: str
    mailbox_email: Optional[str] = None
    connection_status: str
    credit_sync_status: str = "manual_only"
    last_connected_at: Optional[datetime] = None
    last_synced_at: Optional[datetime] = None
    created_at: datetime
    updated_at: datetime
    latest_credit_balance: Optional[Decimal] = None
    assigned_members_count: int = 0
    has_universal_key: bool = False
    universal_keys_count: int = 0
    has_saved_password: bool = False
    connection: Optional[AccountConnectionResponse] = None

    model_config = ConfigDict(from_attributes=True)


class AccountListResponse(BaseModel):
    items: List[EmergentAccountResponse]
    total: int
    page: int
    page_size: int
    total_pages: int
