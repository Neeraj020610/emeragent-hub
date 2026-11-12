from datetime import datetime, timezone
from sqlalchemy import Boolean, Column, DateTime, ForeignKey, Integer, Numeric, String, Text
from sqlalchemy.orm import relationship
from app.database import Base


def utcnow():
    return datetime.now(timezone.utc)


class UniversalApiKey(Base):
    __tablename__ = "universal_api_keys"

    id = Column(Integer, primary_key=True, index=True)
    account_id = Column(Integer, ForeignKey("emergent_accounts.id", ondelete="CASCADE"), nullable=False, index=True)
    key_name = Column(String(150), nullable=False)
    api_key_enc = Column(Text, nullable=False)  # Fernet encrypted at rest
    key_prefix = Column(String(30), nullable=False)  # e.g. "emg_live_" or first 8 chars
    key_last4 = Column(String(10), nullable=False)   # e.g. "4567"
    proxy_base_url = Column(String(255), default="https://proxy.emergent.ai", nullable=False)
    is_active = Column(Boolean, default=True, nullable=False)
    created_by_user_id = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True)
    last_validated_at = Column(DateTime(timezone=True), nullable=True)
    validation_status = Column(String(50), default="VALID", nullable=False)  # VALID, INVALID, EXPIRED, ERROR
    validation_message = Column(Text, nullable=True)
    revoked_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), default=utcnow, nullable=False)
    updated_at = Column(DateTime(timezone=True), default=utcnow, onupdate=utcnow, nullable=False)

    # Relationships
    account = relationship("EmergentAccount", back_populates="universal_keys")
    creator = relationship("User", foreign_keys=[created_by_user_id])
    usage_records = relationship("UniversalKeyUsage", back_populates="api_key", cascade="all, delete-orphan")


class UniversalKeyUsage(Base):
    __tablename__ = "universal_key_usage_events"

    id = Column(Integer, primary_key=True, index=True)
    key_id = Column(Integer, ForeignKey("universal_api_keys.id", ondelete="CASCADE"), nullable=False, index=True)
    account_id = Column(Integer, ForeignKey("emergent_accounts.id", ondelete="CASCADE"), nullable=False, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True)
    request_id = Column(String(100), index=True, nullable=False)
    model = Column(String(100), nullable=False)
    prompt_tokens = Column(Integer, default=0, nullable=False)
    completion_tokens = Column(Integer, default=0, nullable=False)
    total_tokens = Column(Integer, default=0, nullable=False)
    cost = Column(Numeric(12, 6), default=0.0, nullable=True)
    duration_ms = Column(Integer, default=0, nullable=False)
    status = Column(String(50), default="SUCCESS", nullable=False)  # SUCCESS, ERROR, RATE_LIMITED, TIMEOUT, UNAUTHORIZED
    error_reason = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), default=utcnow, nullable=False)

    # Relationships
    api_key = relationship("UniversalApiKey", back_populates="usage_records")
    account = relationship("EmergentAccount", back_populates="universal_key_usage_records")
    user = relationship("User", foreign_keys=[user_id])

