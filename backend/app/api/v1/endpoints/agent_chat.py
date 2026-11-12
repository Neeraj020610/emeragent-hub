import os
from typing import List, Optional
from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, status
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.user import User
from app.models.chat import Conversation, MessageAttachment
from app.schemas.chat import (
    ConversationListItemResponse,
    ConversationDetailResponse,
    ConversationCreateRequest,
    SendMessageRequest,
    ConversationMessageResponse,
    MessageAttachmentResponse,
    TaskControlRequest,
)
from app.services.agent_chat.service import AgentChatService
from app.dependencies import get_current_user, record_audit

router = APIRouter()
chat_service = AgentChatService()


# -------------------------------------------------------------
# 1. Conversation Endpoints
# -------------------------------------------------------------
@router.get("/conversations", response_model=List[ConversationListItemResponse])
def list_conversations(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Lists conversations for the authenticated user."""
    return chat_service.list_conversations(user_id=current_user.id, db=db)


@router.post("/conversations", response_model=ConversationDetailResponse)
def create_conversation(
    payload: Optional[ConversationCreateRequest] = None,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Initializes a new ChatGPT-style conversation with an initial agent greeting."""
    title = payload.title if payload else "New Chat"
    conv = chat_service.create_conversation(user_id=current_user.id, title=title, db=db)
    record_audit(
        db=db,
        user_id=current_user.id,
        action="CREATE_CONVERSATION",
        resource_type="conversation",
        resource_id=conv.conversation_uuid,
        details=f"Conversation created: {conv.title}",
    )
    return conv


@router.get("/conversations/{conversation_uuid}", response_model=ConversationDetailResponse)
def get_conversation(
    conversation_uuid: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Retrieves full conversation history, messages, attachments, and current task state."""
    conv = chat_service.get_conversation_by_uuid(conv_uuid=conversation_uuid, user_id=current_user.id, db=db)
    if not conv:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Conversation not found.")
    return conv


@router.delete("/conversations/{conversation_uuid}")
def delete_conversation(
    conversation_uuid: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Deletes a conversation and its message history."""
    deleted = chat_service.delete_conversation(conv_uuid=conversation_uuid, user_id=current_user.id, db=db)
    if not deleted:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Conversation not found.")
    record_audit(
        db=db,
        user_id=current_user.id,
        action="DELETE_CONVERSATION",
        resource_type="conversation",
        resource_id=conversation_uuid,
        details="Conversation deleted.",
    )
    return {"status": "success", "message": "Conversation deleted successfully."}


# -------------------------------------------------------------
# 2. File & Image Upload
# -------------------------------------------------------------
@router.post("/conversations/{conversation_uuid}/upload", response_model=MessageAttachmentResponse)
async def upload_attachment(
    conversation_uuid: str,
    file: UploadFile = File(...),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Uploads a real reference image, document, code, or project file.
    Stores on disk and performs backend content inspection (size, dimensions, hash, line count).
    """
    conv = chat_service.get_conversation_by_uuid(conv_uuid=conversation_uuid, user_id=current_user.id, db=db)
    if not conv:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Conversation not found.")

    attachment = await chat_service.save_attachment(conversation=conv, file=file, db=db)
    record_audit(
        db=db,
        user_id=current_user.id,
        action="UPLOAD_ATTACHMENT",
        resource_type="message_attachment",
        resource_id=str(attachment.id),
        details=f"Uploaded '{attachment.file_name}' ({attachment.file_size_bytes} bytes).",
    )
    return attachment


@router.get("/attachments/{attachment_id}/download")
def download_attachment(
    attachment_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Safely retrieves an uploaded file from disk with user RBAC isolation."""
    attachment = db.query(MessageAttachment).filter(MessageAttachment.id == attachment_id).first()
    if not attachment:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Attachment not found.")

    # Verify user owns the conversation
    conv = db.query(Conversation).filter(Conversation.id == attachment.conversation_id).first()
    if not conv or (conv.user_id != current_user.id and current_user.role.name.upper() not in ("ADMIN", "SUPERADMIN")):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access denied to this attachment.")

    if not os.path.exists(attachment.file_path):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="File missing on server storage.")

    return FileResponse(
        path=attachment.file_path,
        media_type=attachment.mime_type,
        filename=attachment.file_name,
    )


# -------------------------------------------------------------
# 3. Message Processing & Autonomous Execution
# -------------------------------------------------------------
@router.post("/conversations/{conversation_uuid}/messages", response_model=ConversationMessageResponse)
def send_message(
    conversation_uuid: str,
    payload: SendMessageRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Sends a user prompt to the Agent Chat:
    - Parses requirement (Video vs Web/App vs Query)
    - Inspects any attached images/files
    - Builds structured plan with acceptance criteria
    - Selects eligible Emergent account under 50% credit ceiling
    - Dispatches execution steps through worker engine
    - Returns structured response with plan card and live progress
    """
    conv = chat_service.get_conversation_by_uuid(conv_uuid=conversation_uuid, user_id=current_user.id, db=db)
    if not conv:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Conversation not found.")

    reply = chat_service.process_user_message(
        conversation=conv,
        prompt=payload.prompt,
        attachment_ids=payload.attachment_ids,
        auto_execute=payload.auto_execute,
        db=db,
    )

    record_audit(
        db=db,
        user_id=current_user.id,
        action="AGENT_CHAT_MESSAGE",
        resource_type="conversation",
        resource_id=conversation_uuid,
        details=f"Prompt processed. Task ID: {reply.task_id or 'None'}",
    )
    return reply


# -------------------------------------------------------------
# 4. Task Controls (STOP, PAUSE, RESUME)
# -------------------------------------------------------------
@router.post("/conversations/{conversation_uuid}/control")
def control_conversation_task(
    conversation_uuid: str,
    payload: TaskControlRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Executes STOP, PAUSE, or RESUME on the current active task for this conversation."""
    conv = chat_service.get_conversation_by_uuid(conv_uuid=conversation_uuid, user_id=current_user.id, db=db)
    if not conv:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Conversation not found.")

    try:
        res = chat_service.control_task(
            conversation=conv,
            action=payload.action,
            user=current_user,
            db=db,
            note=payload.note,
        )
        record_audit(
            db=db,
            user_id=current_user.id,
            action=f"AGENT_TASK_{payload.action.upper()}",
            resource_type="conversation",
            resource_id=conversation_uuid,
            details=f"Task action {payload.action.upper()} applied.",
        )
        return res
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))

