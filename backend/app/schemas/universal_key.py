from datetime import datetime
from decimal import Decimal
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, ConfigDict, Field


class UniversalKeyAccountRegisterRequest(BaseModel):
    account_name: str = Field(..., min_length=2, max_length=150, description="Display name for the Emergent account")
    api_key: str = Field(..., min_length=8, description="Universal API Key (LiteLLM-compatible)")
    email: Optional[str] = Field(None, description="Optional account owner or alert email metadata")
    description: Optional[str] = Field(None, max_length=500, description="Optional description/notes")
    ownership_type: str = Field("COMPANY_OWNED", description="COMPANY_OWNED or PERSONAL")
    proxy_base_url: Optional[str] = Field("https://proxy.emergent.ai", description="Configured LiteLLM proxy base URL")
    validate_first: bool = Field(True, description="Perform safe test authentication against official proxy before saving")


class UniversalKeyAddRequest(BaseModel):
    account_id: int
    key_name: str = Field(..., min_length=2, max_length=150)
    api_key: str = Field(..., min_length=8)
    proxy_base_url: Optional[str] = Field("https://proxy.emergent.ai")
    validate_first: bool = Field(True)


class UniversalKeyUpdateRequest(BaseModel):
    key_name: Optional[str] = Field(None, min_length=2, max_length=150)
    proxy_base_url: Optional[str] = None
    is_active: Optional[bool] = None


class UniversalKeyResponse(BaseModel):
    id: int
    account_id: int
    account_name: str
    account_email: Optional[str] = None
    key_name: str
    masked_key: str
    key_prefix: str
    key_last4: str
    proxy_base_url: str
    is_active: bool
    validation_status: str
    validation_message: Optional[str] = None
    last_validated_at: Optional[datetime] = None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class UniversalKeyValidateResponse(BaseModel):
    is_valid: bool
    status_code: int
    message: str
    latency_ms: int
    models_available: Optional[List[str]] = None


class ChatMessage(BaseModel):
    role: str
    content: str


class UniversalKeyChatRequest(BaseModel):
    account_id: Optional[int] = None
    key_id: Optional[int] = None
    model: str = "gpt-4o-mini"
    messages: List[ChatMessage]
    temperature: Optional[float] = 0.7
    max_tokens: Optional[int] = 500


class UniversalKeyChatResponse(BaseModel):
    request_id: str
    account_id: int
    key_id: int
    model: str
    content: str
    prompt_tokens: int
    completion_tokens: int
    total_tokens: int
    cost: Optional[float] = None
    duration_ms: int
    status: str


class UniversalKeyUsageResponse(BaseModel):
    id: int
    key_id: int
    account_id: int
    account_name: str
    user_id: Optional[int] = None
    user_name: Optional[str] = None
    request_id: str
    model: str
    prompt_tokens: int
    completion_tokens: int
    total_tokens: int
    cost: Optional[float] = None
    duration_ms: int
    status: str
    error_reason: Optional[str] = None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class UniversalKeyStatsResponse(BaseModel):
    total_keys: int
    active_keys: int
    total_requests: int
    successful_requests: int
    failed_requests: int
    total_tokens: int
    total_cost: float

