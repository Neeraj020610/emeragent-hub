from datetime import datetime
from typing import Optional
from pydantic import BaseModel, EmailStr


class MailboxAccountBase(BaseModel):
    email_address: EmailStr
    employee_name: str = ""
    account_id: Optional[int] = None
    ownership_type: str = "COMPANY_OWNED"
    api_base_url: Optional[str] = None
    is_active: bool = True
    verified_access: bool = False
    notes: Optional[str] = None


class MailboxAccountCreate(BaseModel):
    email_address: EmailStr
    employee_name: str
    account_id: Optional[int] = None
    ownership_type: str = "COMPANY_OWNED"
    api_base_url: Optional[str] = None
    is_active: bool = True
    verified_access: bool = False
    notes: Optional[str] = None


class MailboxAccountUpdate(BaseModel):
    employee_name: Optional[str] = None
    account_id: Optional[int] = None
    ownership_type: Optional[str] = None
    is_active: Optional[bool] = None
    verified_access: Optional[bool] = None
    notes: Optional[str] = None


class MailboxAccountResponse(BaseModel):
    id: int
    email_address: EmailStr
    employee_name: str = ""
    provider: str
    api_base_url: str
    account_id: Optional[int] = None
    ownership_type: str = "COMPANY_OWNED"
    is_active: bool
    verified_access: bool
    notes: Optional[str] = None
    created_at: datetime
    updated_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class OTPRequestCreate(BaseModel):
    mailbox_id: Optional[int] = None
    account_id: Optional[int] = None
    sender_filter: Optional[str] = None
    subject_filter: Optional[str] = None
    validity_minutes: int = 10
    owner_consent_confirmed: bool = False


class OTPRequestResponse(BaseModel):
    id: int
    mailbox_id: int
    account_id: Optional[int] = None
    account_name: Optional[str] = None
    mailbox_email: Optional[str] = None
    employee_name: Optional[str] = None
    requested_by_user_id: Optional[int] = None
    status: str
    correlation_id: str
    command_id: Optional[str] = None
    attempts_count: int = 0
    error_reason: Optional[str] = None
    sender_filter: Optional[str] = None
    subject_filter: Optional[str] = None
    expires_at: datetime
    received_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    created_at: datetime
    is_verified: bool = False

    class Config:
        from_attributes = True


class OTPStatusResponse(BaseModel):
    request_id: int
    status: str
    correlation_id: str
    command_id: Optional[str] = None
    attempts_count: int
    is_ready: bool
    error_reason: Optional[str] = None
    expires_at: datetime


class OTPResultResponse(BaseModel):
    request_id: int
    correlation_id: str
    otp_code: str
    retrieved_at: datetime
    expires_at: datetime


class PersonalConsentCreate(BaseModel):
    authorized_member_id: int
    permission_scope: str = "OTP_RETRIEVAL"
    expires_in_days: Optional[int] = 30


class PersonalConsentResponse(BaseModel):
    id: int
    account_id: int
    owner_user_id: int
    authorized_member_id: int
    granted_by_user_id: Optional[int] = None
    authorized_member_email: Optional[str] = None
    permission_scope: str
    is_active: bool
    approved_at: datetime
    revoked_at: Optional[datetime] = None
    expires_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class OTPVerifyRequest(BaseModel):
    correlation_id: str
    candidate_otp: str
