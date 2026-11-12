from datetime import datetime, timezone
from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    ForeignKey,
    Integer,
    Numeric,
    String,
    Text,
)
from sqlalchemy.orm import relationship
from app.database import Base


def utcnow():
    return datetime.now(timezone.utc)


class Conversation(Base):
    """
    ChatGPT-style conversation session for Personal Agent Chat.
    Persists user conversations across server restarts.
    """
    __tablename__ = "conversations"

    id = Column(Integer, primary_key=True, index=True)
    conversation_uuid = Column(String(100), unique=True, index=True, nullable=False)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    title = Column(String(255), default="New Chat", nullable=False)
    is_pinned = Column(Boolean, default=False, nullable=False)
    current_task_id = Column(Integer, ForeignKey("autonomous_tasks.id", ondelete="SET NULL"), nullable=True, index=True)
    created_at = Column(DateTime(timezone=True), default=utcnow, nullable=False)
    updated_at = Column(DateTime(timezone=True), default=utcnow, onupdate=utcnow, nullable=False)

    user = relationship("User")
    current_task = relationship("AutonomousTask", foreign_keys=[current_task_id])
    messages = relationship("ConversationMessage", back_populates="conversation", cascade="all, delete-orphan", order_by="ConversationMessage.created_at.asc()")
    attachments = relationship("MessageAttachment", back_populates="conversation", cascade="all, delete-orphan")


class ConversationMessage(Base):
    """
    Individual chat bubble in a conversation.
    Tracks user prompts, agent responses, attached task plans, and execution progress.
    """
    __tablename__ = "conversation_messages"

    id = Column(Integer, primary_key=True, index=True)
    conversation_id = Column(Integer, ForeignKey("conversations.id", ondelete="CASCADE"), nullable=False, index=True)
    sender_type = Column(String(50), default="USER", nullable=False)  # USER, AGENT, SYSTEM
    content = Column(Text, nullable=False)
    
    # Task planning & execution linkages
    task_id = Column(Integer, ForeignKey("autonomous_tasks.id", ondelete="SET NULL"), nullable=True, index=True)
    action_plan_json = Column(Text, nullable=True)  # Structured plan with acceptance criteria
    execution_status = Column(String(50), nullable=True)  # PLANNING, WAITING_INPUT, EXECUTING, PAUSED, COMPLETED, STOPPED, FAILED
    account_id = Column(Integer, ForeignKey("emergent_accounts.id", ondelete="SET NULL"), nullable=True, index=True)
    is_mock = Column(Boolean, default=True, nullable=False)
    
    created_at = Column(DateTime(timezone=True), default=utcnow, nullable=False)

    conversation = relationship("Conversation", back_populates="messages")
    task = relationship("AutonomousTask", foreign_keys=[task_id])
    account = relationship("EmergentAccount", foreign_keys=[account_id])
    attachments = relationship("MessageAttachment", back_populates="message")


class MessageAttachment(Base):
    """
    Real file and image attachments uploaded by the user or output by the agent.
    Stored on disk in storage/attachments/ and inspected by the agent brain.
    """
    __tablename__ = "message_attachments"

    id = Column(Integer, primary_key=True, index=True)
    conversation_id = Column(Integer, ForeignKey("conversations.id", ondelete="CASCADE"), nullable=False, index=True)
    message_id = Column(Integer, ForeignKey("conversation_messages.id", ondelete="SET NULL"), nullable=True, index=True)
    file_name = Column(String(255), nullable=False)
    file_path = Column(String(500), nullable=False)
    file_size_bytes = Column(Integer, default=0, nullable=False)
    mime_type = Column(String(100), default="application/octet-stream", nullable=False)
    file_hash = Column(String(64), nullable=True)  # SHA-256 integrity hash
    file_summary = Column(Text, nullable=True)  # Extracted summary, dimensions, code preview
    created_at = Column(DateTime(timezone=True), default=utcnow, nullable=False)

    conversation = relationship("Conversation", back_populates="attachments")
    message = relationship("ConversationMessage", back_populates="attachments")

