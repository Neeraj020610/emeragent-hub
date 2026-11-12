from datetime import datetime, timezone
from sqlalchemy import Boolean, Column, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import relationship
from app.database import Base


def utcnow():
    return datetime.now(timezone.utc)


class AccountSession(Base):
    __tablename__ = "account_sessions"

    id = Column(Integer, primary_key=True, index=True)
    account_id = Column(Integer, ForeignKey("emergent_accounts.id", ondelete="CASCADE"), unique=True, nullable=False, index=True)
    session_token = Column(String(100), unique=True, index=True, nullable=False)
    auth_method = Column(String(50), default="oauth2", nullable=False)  # oauth2, mcp_client, universal_key, browser_profile
    session_status = Column(String(50), default="ACTIVE", nullable=False)  # ACTIVE, EXPIRED, REVOKED, REAUTH_REQUIRED, DISCONNECTED
    session_data_enc = Column(Text, nullable=True)  # Fernet encrypted token bundle / session context
    browser_profile_dir = Column(String(255), nullable=True)  # Isolated filesystem storage path for browser state
    token_expires_at = Column(DateTime(timezone=True), nullable=True)
    last_validated_at = Column(DateTime(timezone=True), nullable=True)
    last_active_at = Column(DateTime(timezone=True), nullable=True)
    reauth_required = Column(Boolean, default=False, nullable=False)
    reauth_reason = Column(Text, nullable=True)
    authenticated_by_user_id = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True)
    created_at = Column(DateTime(timezone=True), default=utcnow, nullable=False)
    updated_at = Column(DateTime(timezone=True), default=utcnow, onupdate=utcnow, nullable=False)

    # Relationships
    account = relationship("EmergentAccount", back_populates="account_session")
    authenticated_by = relationship("User", foreign_keys=[authenticated_by_user_id])

