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
    UniqueConstraint,
)
from sqlalchemy.orm import relationship
from app.database import Base


def utcnow():
    return datetime.now(timezone.utc)


class AutonomousInstruction(Base):
    """
    Administrator-defined reusable instructions for Video Creation and Website/App Development.
    The Autonomous Brain consumes these instructions to generate bounded, actionable tasks.
    """
    __tablename__ = "autonomous_instructions"

    id = Column(Integer, primary_key=True, index=True)
    project_id = Column(Integer, ForeignKey("projects.id", ondelete="CASCADE"), nullable=True, index=True)
    title = Column(String(200), nullable=False)
    work_type = Column(String(50), nullable=False, index=True)  # VIDEO_CREATION, WEBSITE_APP_DEV
    objective = Column(Text, nullable=False)
    system_prompt = Column(Text, nullable=True)
    parameters_json = Column(Text, nullable=True)  # JSON dict (duration, style, resolution, language, tech stack, etc.)
    max_tasks = Column(Integer, default=10, nullable=False)
    is_active = Column(Boolean, default=True, nullable=False)
    created_by_user_id = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True)
    created_at = Column(DateTime(timezone=True), default=utcnow, nullable=False)
    updated_at = Column(DateTime(timezone=True), default=utcnow, onupdate=utcnow, nullable=False)

    project = relationship("Project")
    created_by = relationship("User", foreign_keys=[created_by_user_id])
    tasks = relationship("AutonomousTask", back_populates="instruction", cascade="all, delete-orphan")


class AutonomousTask(Base):
    """
    Actionable task managed by the Autonomous Brain and executed by the Autonomous Worker Engine.
    Supports AI-generated plans, manual tasks, and imported task queues.
    """
    __tablename__ = "autonomous_tasks"

    id = Column(Integer, primary_key=True, index=True)
    task_identifier = Column(String(100), unique=True, index=True, nullable=False)  # e.g. TASK-VID-2026-001
    instruction_id = Column(Integer, ForeignKey("autonomous_instructions.id", ondelete="SET NULL"), nullable=True, index=True)
    project_id = Column(Integer, ForeignKey("projects.id", ondelete="CASCADE"), nullable=True, index=True)
    work_type = Column(String(50), nullable=False, index=True)  # VIDEO_CREATION, WEBSITE_APP_DEV
    source = Column(String(50), default="AI_GENERATED", nullable=False)  # AI_GENERATED, MANUAL, IMPORTED
    title = Column(String(255), nullable=False)
    description = Column(Text, nullable=False)
    expected_result = Column(Text, nullable=False)
    acceptance_criteria = Column(Text, nullable=True)  # JSON array of acceptance strings
    assigned_account_id = Column(Integer, ForeignKey("emergent_accounts.id", ondelete="SET NULL"), nullable=True, index=True)
    priority = Column(String(20), default="MEDIUM", nullable=False, index=True)  # LOW, MEDIUM, HIGH, CRITICAL
    
    # Cost & Estimation
    estimated_credit_cost = Column(Numeric(14, 4), default=0.0000, nullable=False)
    actual_credit_cost = Column(Numeric(14, 4), default=0.0000, nullable=False)
    
    # State & Scheduling
    status = Column(String(50), default="PLANNED", nullable=False, index=True)
    # PLANNED, QUEUED, IN_PROGRESS, CHECKPOINT, COMPLETED, FAILED, BLOCKED, CANCELLED
    dependencies = Column(Text, nullable=True)  # JSON array of prerequisite task_identifiers
    retry_count = Column(Integer, default=0, nullable=False)
    max_retries = Column(Integer, default=3, nullable=False)
    retry_policy = Column(Text, nullable=True)  # JSON dict: {backoff_factor: 2.0, max_interval: 300}
    
    # Worker & Execution Tracking
    idempotency_key = Column(String(100), unique=True, index=True, nullable=True)
    worker_id = Column(String(100), nullable=True, index=True)
    last_heartbeat_at = Column(DateTime(timezone=True), nullable=True)
    timeout_seconds = Column(Integer, default=3600, nullable=False)
    execution_adapter = Column(String(50), default="MOCK_ADAPTER", nullable=False)
    is_mock = Column(Boolean, default=True, nullable=False)
    
    # Checkpoints & Results
    checkpoints = Column(Text, nullable=True)  # JSON array of checkpoints: [{step, timestamp, state}]
    result_metadata = Column(Text, nullable=True)  # JSON dict of output files, URLs, artifacts
    error_classification = Column(String(100), nullable=True)
    error_details = Column(Text, nullable=True)
    
    started_at = Column(DateTime(timezone=True), nullable=True)
    completed_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), default=utcnow, nullable=False)
    updated_at = Column(DateTime(timezone=True), default=utcnow, onupdate=utcnow, nullable=False)

    instruction = relationship("AutonomousInstruction", back_populates="tasks")
    project = relationship("Project")
    assigned_account = relationship("EmergentAccount")
    execution_logs = relationship("AutonomousTaskLog", back_populates="task", cascade="all, delete-orphan", order_by="AutonomousTaskLog.created_at.asc()")


class AutonomousTaskLog(Base):
    """Execution step log and checkpoint event for an autonomous task."""
    __tablename__ = "autonomous_task_logs"

    id = Column(Integer, primary_key=True, index=True)
    task_id = Column(Integer, ForeignKey("autonomous_tasks.id", ondelete="CASCADE"), nullable=False, index=True)
    worker_id = Column(String(100), nullable=True)
    log_level = Column(String(20), default="INFO", nullable=False)
    message = Column(Text, nullable=False)
    step_name = Column(String(100), nullable=True)
    metadata_json = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), default=utcnow, nullable=False)

    task = relationship("AutonomousTask", back_populates="execution_logs")


class AccountCreditBudget(Base):
    """
    Centralized account budget and credit scheduler record.
    Enforces the mandatory 50% Planned Usage Ceiling on starting balance.
    Tracks live balances, reserved credits, and distinguishes Universal API vs Platform Build usage.
    """
    __tablename__ = "account_credit_budgets"

    id = Column(Integer, primary_key=True, index=True)
    account_id = Column(Integer, ForeignKey("emergent_accounts.id", ondelete="CASCADE"), unique=True, nullable=False, index=True)
    starting_balance = Column(Numeric(14, 4), default=0.0000, nullable=False)
    verified_current_balance = Column(Numeric(14, 4), default=0.0000, nullable=False)
    credit_usage = Column(Numeric(14, 4), default=0.0000, nullable=False)
    reserved_credits = Column(Numeric(14, 4), default=0.0000, nullable=False)
    ceiling_percentage = Column(Numeric(5, 2), default=50.00, nullable=False)  # 50.00%
    
    # Classification & Provenance
    balance_source = Column(String(50), default="MANUAL", nullable=False)  # MANUAL, IMPORTED, UNKNOWN, API_VERIFIED
    last_balance_validated_at = Column(DateTime(timezone=True), nullable=True)
    is_eligible = Column(Boolean, default=True, nullable=False)
    ineligibility_reason = Column(String(255), nullable=True)
    
    # Ledger separation against shared balance
    universal_api_usage = Column(Numeric(14, 4), default=0.0000, nullable=False)
    platform_build_usage = Column(Numeric(14, 4), default=0.0000, nullable=False)
    active_task_id = Column(Integer, ForeignKey("autonomous_tasks.id", ondelete="SET NULL"), nullable=True)
    
    created_at = Column(DateTime(timezone=True), default=utcnow, nullable=False)
    updated_at = Column(DateTime(timezone=True), default=utcnow, onupdate=utcnow, nullable=False)

    account = relationship("EmergentAccount")
    active_task = relationship("AutonomousTask", foreign_keys=[active_task_id])


class AutonomousSystemState(Base):
    """
    Tracks overall system autonomous execution state, active command, and operator controls.
    Commands: START, PAUSE, RESUME, STOP.
    """
    __tablename__ = "autonomous_system_states"

    id = Column(Integer, primary_key=True, index=True)
    status = Column(String(50), default="STOPPED", nullable=False)  # STOPPED, RUNNING, PAUSED
    last_command = Column(String(50), default="STOP", nullable=False)
    last_command_at = Column(DateTime(timezone=True), default=utcnow, nullable=False)
    last_command_by_user_id = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    command_message = Column(Text, nullable=True)
    active_workers_count = Column(Integer, default=0, nullable=False)
    metadata_json = Column(Text, nullable=True)
    updated_at = Column(DateTime(timezone=True), default=utcnow, onupdate=utcnow, nullable=False)

    last_command_by = relationship("User", foreign_keys=[last_command_by_user_id])

