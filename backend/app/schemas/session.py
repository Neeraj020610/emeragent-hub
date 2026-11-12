from datetime import datetime
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, ConfigDict, Field


class AccountSessionAuthenticateRequest(BaseModel):
    auth_method: str = Field("oauth2", description="oauth2, mcp_client, universal_key, browser_profile")
    auth_code: Optional[str] = Field(None, description="OAuth code or simulation secret")
    universal_key_id: Optional[int] = Field(None, description="Optional ID of registered universal key")
    session_metadata: Optional[str] = Field(None, description="Optional client/scope metadata")


class AccountSessionResponse(BaseModel):
    id: int
    account_id: int
    account_identifier: str
    account_name: str
    account_email: Optional[str] = None
    ownership_type: str
    session_token: str
    auth_method: str
    session_status: str  # ACTIVE, EXPIRED, REVOKED, REAUTH_REQUIRED, DISCONNECTED
    token_expires_at: Optional[datetime] = None
    last_validated_at: Optional[datetime] = None
    last_active_at: Optional[datetime] = None
    reauth_required: bool
    reauth_reason: Optional[str] = None
    is_currently_active: bool = False
    browser_profile_isolated: bool = False
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class AccountSessionSwitchResponse(BaseModel):
    status: str
    account_id: int
    account_name: str
    session_token: str
    message: str
    session: AccountSessionResponse


class AccountSessionStats(BaseModel):
    total_sessions: int
    active_sessions: int
    reauth_required_count: int
    disconnected_count: int


class AccountSessionSecureLoginRequest(BaseModel):
    email: str = Field(..., description="Emergent account email")
    password: str = Field("", description="Emergent account password (reuses Fernet-encrypted saved password if blank)")
    mailbox_email: Optional[str] = Field(None, description="Optional associated Phx mailbox email")
    auto_otp: bool = Field(True, description="Attempt automated OTP retrieval via Phx Email API")


class AccountSessionSecureLoginResponse(BaseModel):
    status: str  # SUCCESS, OTP_REQUIRED, PENDING_VERIFICATION, FAILED
    account_id: int
    account_name: str
    message: str
    requires_otp: bool = False
    otp_retrieval_status: Optional[str] = None
    manual_otp_fallback: bool = False
    dashboard_verified: bool = False
    session: Optional[AccountSessionResponse] = None


class AccountSessionSubmitOTPRequest(BaseModel):
    otp_code: str = Field(..., description="6-digit verification code")


class AccountSessionSubmitOTPResponse(BaseModel):
    status: str  # SUCCESS, FAILED
    account_id: int
    message: str
    dashboard_verified: bool
    session: Optional[AccountSessionResponse] = None


