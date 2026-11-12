from datetime import datetime, timezone
from sqlalchemy import Boolean, Column, DateTime, ForeignKey, Integer, Numeric, String, Text
from sqlalchemy.orm import relationship
from app.database import Base


def utcnow():
    return datetime.now(timezone.utc)


class BuildJob(Base):
    __tablename__ = "build_jobs"

    id = Column(Integer, primary_key=True, index=True)
    project_id = Column(Integer, ForeignKey("projects.id", ondelete="CASCADE"), nullable=False, index=True)
    account_id = Column(Integer, ForeignKey("emergent_accounts.id", ondelete="CASCADE"), nullable=False, index=True)
    initiated_by_user_id = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True)
    
    # Basic job metadata
    title = Column(String(200), default="Untitled Build Request", nullable=False)
    job_type = Column(String(100), nullable=False)  # prompt_build, code_gen, full_stack, deployment, model_eval
    job_status = Column(String(50), default="DRAFT", nullable=False, index=True)  
    # DRAFT, QUEUED, ASSIGNED, STARTING, RUNNING, PAUSED, COMPLETED, FAILED, CANCELLED
    priority = Column(String(20), default="MEDIUM", nullable=False, index=True)  # LOW, MEDIUM, HIGH, CRITICAL
    
    # Detailed requirements & metadata
    requirements = Column(Text, nullable=True)
    reference_urls = Column(Text, nullable=True)  # JSON list of reference URLs
    notes = Column(Text, nullable=True)
    attachments_metadata = Column(Text, nullable=True)  # JSON list of attachment descriptors
    expected_completion_date = Column(DateTime(timezone=True), nullable=True)
    
    # Queue, execution & reliability tracking
    idempotency_key = Column(String(100), unique=True, index=True, nullable=True)
    worker_id = Column(String(100), nullable=True, index=True)
    last_heartbeat_at = Column(DateTime(timezone=True), nullable=True)
    retry_count = Column(Integer, default=0, nullable=False)
    max_retries = Column(Integer, default=3, nullable=False)
    timeout_seconds = Column(Integer, default=3600, nullable=False)
    
    # Adapter & mock provenance
    execution_adapter = Column(String(50), default="MOCK_EMERGENT", nullable=False)  # MOCK_EMERGENT, REAL_EMERGENT
    is_mock = Column(Boolean, default=True, nullable=False)
    
    # Timing & execution details
    started_at = Column(DateTime(timezone=True), nullable=True)
    paused_at = Column(DateTime(timezone=True), nullable=True)
    cancelled_at = Column(DateTime(timezone=True), nullable=True)
    completed_at = Column(DateTime(timezone=True), nullable=True)
    credits_used = Column(Numeric(14, 4), default=0.0000, nullable=False)
    request_payload = Column(Text, nullable=True)
    result_summary = Column(Text, nullable=True)
    result_metadata = Column(Text, nullable=True)  # JSON metadata (artifacts, URLs, execution stats)
    error_details = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), default=utcnow, nullable=False)
    updated_at = Column(DateTime(timezone=True), default=utcnow, onupdate=utcnow, nullable=False)

    project = relationship("Project", back_populates="build_jobs")
    account = relationship("EmergentAccount", back_populates="build_jobs")
    initiated_by = relationship("User", foreign_keys=[initiated_by_user_id])
    assignments = relationship("JobAssignment", back_populates="job", cascade="all, delete-orphan")
    credit_events = relationship("CreditEvent", back_populates="job")
    history = relationship("BuildJobHistory", back_populates="job", cascade="all, delete-orphan", order_by="BuildJobHistory.created_at.asc()")


class JobAssignment(Base):
    __tablename__ = "job_assignments"

    id = Column(Integer, primary_key=True, index=True)
    job_id = Column(Integer, ForeignKey("build_jobs.id", ondelete="CASCADE"), nullable=False, index=True)
    assigned_user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    role_in_job = Column(String(50), default="operator", nullable=False)  # operator, reviewer, observer
    assigned_at = Column(DateTime(timezone=True), default=utcnow, nullable=False)

    job = relationship("BuildJob", back_populates="assignments")
    user = relationship("User", back_populates="job_assignments")


class BuildJobHistory(Base):
    __tablename__ = "build_job_history"

    id = Column(Integer, primary_key=True, index=True)
    job_id = Column(Integer, ForeignKey("build_jobs.id", ondelete="CASCADE"), nullable=False, index=True)
    from_status = Column(String(50), nullable=True)
    to_status = Column(String(50), nullable=False)
    worker_id = Column(String(100), nullable=True)
    message = Column(Text, nullable=True)
    error_details = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), default=utcnow, nullable=False)

    job = relationship("BuildJob", back_populates="history")


class BuildWorker(Base):
    __tablename__ = "build_workers"

    id = Column(Integer, primary_key=True, index=True)
    worker_name = Column(String(100), unique=True, index=True, nullable=False)
    status = Column(String(50), default="ACTIVE", nullable=False)  # ACTIVE, BUSY, OFFLINE, TERMINATED
    current_job_id = Column(Integer, ForeignKey("build_jobs.id", ondelete="SET NULL"), nullable=True)
    system_info = Column(Text, nullable=True)  # JSON machine stats, hostname, pid
    last_heartbeat_at = Column(DateTime(timezone=True), default=utcnow, nullable=False)
    created_at = Column(DateTime(timezone=True), default=utcnow, nullable=False)
    updated_at = Column(DateTime(timezone=True), default=utcnow, onupdate=utcnow, nullable=False)
