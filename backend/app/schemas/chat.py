from datetime import datetime
from decimal import Decimal
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field, ConfigDict


class MessageAttachmentResponse(BaseModel):
    id: int
    conversation_id: int
    message_id: Optional[int]
    file_name: str
    file_size_bytes: int
    mime_type: str
    file_hash: Optional[str]
    file_summary: Optional[str]
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class ConversationMessageResponse(BaseModel):
    id: int
    conversation_id: int
    sender_type: str  # USER, AGENT, SYSTEM
    content: str
    task_id: Optional[int] = None
    action_plan_json: Optional[str] = None
    execution_status: Optional[str] = None
    account_id: Optional[int] = None
    account_name: Optional[str] = None
    is_mock: bool = True
    attachments: List[MessageAttachmentResponse] = []
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class ConversationListItemResponse(BaseModel):
    id: int
    conversation_uuid: str
    title: str
    is_pinned: bool
    current_task_id: Optional[int]
    message_count: int
    last_message_preview: Optional[str]
    updated_at: datetime
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class ConversationDetailResponse(BaseModel):
    id: int
    conversation_uuid: str
    title: str
    is_pinned: bool
    current_task_id: Optional[int]
    messages: List[ConversationMessageResponse]
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class ConversationCreateRequest(BaseModel):
    title: Optional[str] = "New Chat"


class SendMessageRequest(BaseModel):
    prompt: str = Field(..., min_length=1)
    attachment_ids: Optional[List[int]] = None
    auto_execute: bool = Field(True, description="Whether to automatically begin executing generated task plan")


class TaskControlRequest(BaseModel):
    action: str = Field(..., description="STOP, PAUSE, RESUME")
    note: Optional[str] = None

