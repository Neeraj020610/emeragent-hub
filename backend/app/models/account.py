from datetime import datetime, timezone
from sqlalchemy import Boolean, Column, DateTime, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import relationship
from app.database import Base


def utcnow():
    return datetime.now(timezone.utc)


class EmergentAccount(Base):
    __tablename__ = "emergent_accounts"

    id = Column(Integer, primary_key=True, index=True)
    account_identifier = Column(String(100), unique=True, index=True, nullable=False)
    account_name = Column(String(150), nullable=False)
    email = Column(String(255), index=True, nullable=True)
    organization = Column(String(150), nullable=True)
    
    # Ownership & Classification (Phase 2)
    owner_user_id = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True)
    owner_name = Column(String(150), nullable=True)
    ownership_type = Column(String(50), default="COMPANY_OWNED", nullable=False)  # COMPANY_OWNED, PERSONAL
    description = Column(Text, nullable=True)

    status = Column(String(50), default="active", nullable=False)  # active, suspended, pending
    auth_type = Column(String(50), default="oauth", nullable=False)  # oauth, mcp, api_key
    encrypted_password = Column(Text, nullable=True)  # Fernet-encrypted Emergent login password (never stored in plaintext)
    connection_status = Column(String(50), default="DISCONNECTED", nullable=False)  # CONNECTED, DISCONNECTED, EXPIRED, AUTHORIZATION_REQUIRED, ERROR, PENDING
    credit_sync_status = Column(String(50), default="manual_only", nullable=False)
    last_connected_at = Column(DateTime(timezone=True), nullable=True)
    last_synced_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), default=utcnow, nullable=False)
    updated_at = Column(DateTime(timezone=True), default=utcnow, onupdate=utcnow, nullable=False)

    # Relationships
    owner = relationship("User", foreign_keys=[owner_user_id])
    connections = relationship("AccountConnection", back_populates="account", cascade="all, delete-orphan")
    permissions = relationship("AccountPermission", back_populates="account", cascade="all, delete-orphan")
    credit_snapshots = relationship("CreditSnapshot", back_populates="account", cascade="all, delete-orphan")
    credit_events = relationship("CreditEvent", back_populates="account", cascade="all, delete-orphan")
    projects = relationship("Project", back_populates="account", cascade="all, delete-orphan")
    build_jobs = relationship("BuildJob", back_populates="account", cascade="all, delete-orphan")
    otp_requests = relationship("OTPRequest", back_populates="account")
    mailbox_accounts = relationship("MailboxAccount", back_populates="account")
    personal_consents = relationship("PersonalAccountConsent", back_populates="account", cascade="all, delete-orphan")
    universal_keys = relationship("UniversalApiKey", back_populates="account", cascade="all, delete-orphan")
    universal_key_usage_records = relationship("UniversalKeyUsage", back_populates="account", cascade="all, delete-orphan")
    account_session = relationship("AccountSession", back_populates="account", uselist=False, cascade="all, delete-orphan")


class PersonalAccountConsent(Base):
    __tablename__ = "personal_account_consents"

    id = Column(Integer, primary_key=True, index=True)
    account_id = Column(Integer, ForeignKey("emergent_accounts.id", ondelete="CASCADE"), nullable=False, index=True)
    owner_user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    authorized_member_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    granted_by_user_id = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True)
    permission_scope = Column(String(50), default="OTP_RETRIEVAL", nullable=False)
    is_active = Column(Boolean, default=True, nullable=False)
    approved_at = Column(DateTime(timezone=True), default=utcnow, nullable=False)
    revoked_at = Column(DateTime(timezone=True), nullable=True)
    expires_at = Column(DateTime(timezone=True), nullable=True)

    account = relationship("EmergentAccount", back_populates="personal_consents")
    owner_user = relationship("User", foreign_keys=[owner_user_id])
    authorized_member = relationship("User", foreign_keys=[authorized_member_id])
    granted_by_user = relationship("User", foreign_keys=[granted_by_user_id])


class AccountPermission(Base):
    __tablename__ = "account_permissions"
    __table_args__ = (
        UniqueConstraint("user_id", "account_id", name="uq_user_account_permission"),
    )

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    account_id = Column(Integer, ForeignKey("emergent_accounts.id", ondelete="CASCADE"), nullable=False, index=True)
    can_view = Column(Boolean, default=True, nullable=False)
    can_execute = Column(Boolean, default=False, nullable=False)
    can_manage = Column(Boolean, default=False, nullable=False)
    created_at = Column(DateTime(timezone=True), default=utcnow, nullable=False)

    user = relationship("User", back_populates="account_permissions")
    account = relationship("EmergentAccount", back_populates="permissions")


class AccountConnection(Base):
    __tablename__ = "account_connections"

    id = Column(Integer, primary_key=True, index=True)
    account_id = Column(Integer, ForeignKey("emergent_accounts.id", ondelete="CASCADE"), nullable=False, index=True)
    provider = Column(String(50), default="emergent", nullable=False)
    connection_type = Column(String(50), default="oauth2", nullable=False)  # oauth2, mcp_client, direct_token
    access_token_enc = Column(Text, nullable=True)  # Fernet encrypted
    refresh_token_enc = Column(Text, nullable=True) # Fernet encrypted
    token_expires_at = Column(DateTime(timezone=True), nullable=True)
    connection_metadata = Column(Text, nullable=True)  # JSON metadata (e.g. scopes, client_id, rate_limits)
    status = Column(String(50), default="DISCONNECTED", nullable=False)  # CONNECTED, DISCONNECTED, EXPIRED, AUTHORIZATION_REQUIRED, ERROR, PENDING
    last_health_check = Column(DateTime(timezone=True), nullable=True)
    error_message = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), default=utcnow, nullable=False)
    updated_at = Column(DateTime(timezone=True), default=utcnow, onupdate=utcnow, nullable=False)

    account = relationship("EmergentAccount", back_populates="connections")
