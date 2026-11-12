from datetime import datetime, timezone
from sqlalchemy import Boolean, Column, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import relationship
from app.database import Base


def utcnow():
    return datetime.now(timezone.utc)


class MailboxAccount(Base):
    __tablename__ = "mailbox_accounts"

    id = Column(Integer, primary_key=True, index=True)
    email_address = Column(String(255), unique=True, index=True, nullable=False)
    employee_name = Column(String(150), default="", nullable=False)
    provider = Column(String(50), default="internal_mail_api", nullable=False)
    api_base_url = Column(String(255), nullable=False)
    account_id = Column(Integer, ForeignKey("emergent_accounts.id", ondelete="SET NULL"), nullable=True, index=True)
    ownership_type = Column(String(50), default="COMPANY_OWNED", nullable=False)
    is_active = Column(Boolean, default=True, nullable=False)
    verified_access = Column(Boolean, default=False, nullable=False)  # Require verification before active OTP retrieval
    notes = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), default=utcnow, nullable=False)
    updated_at = Column(DateTime(timezone=True), default=utcnow, onupdate=utcnow, nullable=False)

    account = relationship("EmergentAccount", back_populates="mailbox_accounts")
    otp_requests = relationship("OTPRequest", back_populates="mailbox", cascade="all, delete-orphan")


class OTPRequest(Base):
    __tablename__ = "otp_requests"

    id = Column(Integer, primary_key=True, index=True)
    mailbox_id = Column(Integer, ForeignKey("mailbox_accounts.id", ondelete="RESTRICT"), nullable=False, index=True)
    account_id = Column(Integer, ForeignKey("emergent_accounts.id", ondelete="SET NULL"), nullable=True, index=True)
    requested_by_user_id = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True)
    status = Column(String(50), default="pending", nullable=False, index=True)  # pending, polling, completed, failed, expired, cancelled, blocked_unverified
    correlation_id = Column(String(100), unique=True, index=True, nullable=False)
    command_id = Column(String(50), unique=True, index=True, nullable=True)  # Unique command ID from email API
    otp_code_hash = Column(String(255), nullable=True)  # Stored as SHA-256 hash, NEVER plaintext
    sender_filter = Column(String(255), nullable=True)
    subject_filter = Column(String(255), nullable=True)
    attempts_count = Column(Integer, default=0, nullable=False)
    error_reason = Column(Text, nullable=True)
    expires_at = Column(DateTime(timezone=True), nullable=False)
    received_at = Column(DateTime(timezone=True), nullable=True)
    completed_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), default=utcnow, nullable=False)

    mailbox = relationship("MailboxAccount", back_populates="otp_requests")
    account = relationship("EmergentAccount", back_populates="otp_requests")
    requested_by_user = relationship("User", back_populates="otp_requests")
