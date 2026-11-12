from datetime import datetime, timezone
from sqlalchemy import Boolean, Column, DateTime, ForeignKey, Integer, Numeric, String, Text
from sqlalchemy.orm import relationship
from app.database import Base


def utcnow():
    return datetime.now(timezone.utc)


class CreditSnapshot(Base):
    __tablename__ = "credit_snapshots"

    id = Column(Integer, primary_key=True, index=True)
    account_id = Column(Integer, ForeignKey("emergent_accounts.id", ondelete="CASCADE"), nullable=False, index=True)
    recorded_at = Column(DateTime(timezone=True), default=utcnow, nullable=False, index=True)
    available_credits = Column(Numeric(14, 4), nullable=False)
    consumed_credits = Column(Numeric(14, 4), default=0.0000, nullable=False)
    total_allocated = Column(Numeric(14, 4), nullable=True)
    balance_source = Column(String(50), default="manual", nullable=False)  # manual, csv_import, sync_adapter
    is_estimate = Column(Boolean, default=False, nullable=False)
    created_at = Column(DateTime(timezone=True), default=utcnow, nullable=False)

    account = relationship("EmergentAccount", back_populates="credit_snapshots")


class CreditEvent(Base):
    __tablename__ = "credit_events"

    id = Column(Integer, primary_key=True, index=True)
    account_id = Column(Integer, ForeignKey("emergent_accounts.id", ondelete="CASCADE"), nullable=False, index=True)
    event_type = Column(String(50), nullable=False)  # consume, deposit, adjustment, refund
    amount = Column(Numeric(14, 4), nullable=False)
    balance_after = Column(Numeric(14, 4), nullable=True)
    job_id = Column(Integer, ForeignKey("build_jobs.id", ondelete="SET NULL"), nullable=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True)
    notes = Column(Text, nullable=True)
    event_timestamp = Column(DateTime(timezone=True), default=utcnow, nullable=False, index=True)
    created_at = Column(DateTime(timezone=True), default=utcnow, nullable=False)

    account = relationship("EmergentAccount", back_populates="credit_events")
    job = relationship("BuildJob", back_populates="credit_events")
    user = relationship("User")
