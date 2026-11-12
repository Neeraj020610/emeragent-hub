from datetime import datetime
from decimal import Decimal
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field, ConfigDict


# -------------------------------------------------------------
# Instructions Schemas
# -------------------------------------------------------------
class AutonomousInstructionCreate(BaseModel):
    project_id: Optional[int] = None
    title: str = Field(..., max_length=200)
    work_type: str = Field(..., description="VIDEO_CREATION or WEBSITE_APP_DEV")
    objective: str
    system_prompt: Optional[str] = None
    parameters: Optional[Dict[str, Any]] = None
    max_tasks: int = Field(10, ge=1, le=50)


class AutonomousInstructionResponse(BaseModel):
    id: int
    project_id: Optional[int]
    title: str
    work_type: str
    objective: str
    system_prompt: Optional[str]
    parameters_json: Optional[str]
    max_tasks: int
    is_active: bool
    created_by_user_id: Optional[int]
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


# -------------------------------------------------------------
# Tasks Schemas
# -------------------------------------------------------------
class AutonomousTaskCreate(BaseModel):
    project_id: Optional[int] = None
    instruction_id: Optional[int] = None
    work_type: str = Field(..., description="VIDEO_CREATION or WEBSITE_APP_DEV")
    source: str = Field("MANUAL", description="AI_GENERATED, MANUAL, or IMPORTED")
    title: str = Field(..., max_length=255)
    description: str
    expected_result: str
    acceptance_criteria: Optional[List[str]] = None
    assigned_account_id: Optional[int] = None
    priority: str = Field("MEDIUM", description="LOW, MEDIUM, HIGH, CRITICAL")
    estimated_credit_cost: Decimal = Field(Decimal("0.0000"), ge=0)
    dependencies: Optional[List[str]] = None
    max_retries: int = Field(3, ge=0, le=10)


class AutonomousTaskImportItem(BaseModel):
    title: str
    work_type: str
    description: str
    expected_result: str
    acceptance_criteria: Optional[List[str]] = None
    priority: Optional[str] = "MEDIUM"
    estimated_credit_cost: Optional[Decimal] = Decimal("0.0000")
    dependencies: Optional[List[str]] = None


class AutonomousTaskImportRequest(BaseModel):
    project_id: Optional[int] = None
    instruction_id: Optional[int] = None
    tasks: List[AutonomousTaskImportItem]


class AutonomousTaskLogResponse(BaseModel):
    id: int
    task_id: int
    worker_id: Optional[str]
    log_level: str
    message: str
    step_name: Optional[str]
    metadata_json: Optional[str]
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class AutonomousTaskResponse(BaseModel):
    id: int
    task_identifier: str
    instruction_id: Optional[int]
    project_id: Optional[int]
    work_type: str
    source: str
    title: str
    description: str
    expected_result: str
    acceptance_criteria: Optional[str]
    assigned_account_id: Optional[int]
    priority: str
    estimated_credit_cost: Decimal
    actual_credit_cost: Decimal
    status: str
    dependencies: Optional[str]
    retry_count: int
    max_retries: int
    worker_id: Optional[str]
    last_heartbeat_at: Optional[datetime]
    timeout_seconds: int
    execution_adapter: str
    is_mock: bool
    checkpoints: Optional[str]
    result_metadata: Optional[str]
    error_classification: Optional[str]
    error_details: Optional[str]
    started_at: Optional[datetime]
    completed_at: Optional[datetime]
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


# -------------------------------------------------------------
# Account Credit Budget Schemas (50% Ceiling)
# -------------------------------------------------------------
class AccountCreditBudgetUpdate(BaseModel):
    starting_balance: Decimal = Field(..., ge=0)
    ceiling_percentage: Decimal = Field(Decimal("50.00"), ge=1, le=100)
    balance_source: Optional[str] = "MANUAL"


class AccountCreditBudgetResponse(BaseModel):
    id: int
    account_id: int
    account_name: Optional[str] = None
    starting_balance: Decimal
    verified_current_balance: Decimal
    credit_usage: Decimal
    reserved_credits: Decimal
    ceiling_percentage: Decimal
    planned_ceiling_limit: Decimal
    remaining_eligible_budget: Decimal
    balance_source: str
    last_balance_validated_at: Optional[datetime]
    is_eligible: bool
    ineligibility_reason: Optional[str]
    universal_api_usage: Decimal
    platform_build_usage: Decimal
    active_task_id: Optional[int]
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


# -------------------------------------------------------------
# System Control & Chat Schemas
# -------------------------------------------------------------
class SystemControlRequest(BaseModel):
    command: str = Field(..., description="START, PAUSE, RESUME, STOP")
    message: Optional[str] = None
    project_id: Optional[int] = None


class SystemChatCommandRequest(BaseModel):
    command_text: str = Field(..., description="e.g. 'START', 'PAUSE', 'STATUS', 'ROTATE'")


class AutonomousSystemStateResponse(BaseModel):
    status: str
    last_command: str
    last_command_at: datetime
    command_message: Optional[str]
    active_workers_count: int
    total_tasks_queued: int
    total_tasks_in_progress: int
    total_tasks_completed: int
    total_tasks_failed: int
    eligible_accounts_count: int
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class SystemChatCommandResponse(BaseModel):
    command: str
    system_status: str
    message: str
    timestamp: datetime
    details: Optional[Dict[str, Any]] = None

