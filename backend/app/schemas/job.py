from datetime import datetime
from decimal import Decimal
from typing import Optional, List, Any, Dict
from pydantic import BaseModel, ConfigDict, Field


class JobAssignmentBase(BaseModel):
    assigned_user_id: int
    role_in_job: str = Field(default="operator", description="operator, reviewer, observer")


class JobAssignmentCreate(JobAssignmentBase):
    pass


class JobAssignmentResponse(JobAssignmentBase):
    id: int
    job_id: int
    assigned_at: datetime
    assigned_user_email: Optional[str] = None
    assigned_user_name: Optional[str] = None

    model_config = ConfigDict(from_attributes=True)


class BuildJobHistoryResponse(BaseModel):
    id: int
    job_id: int
    from_status: Optional[str] = None
    to_status: str
    worker_id: Optional[str] = None
    message: Optional[str] = None
    error_details: Optional[str] = None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class BuildJobBase(BaseModel):
    project_id: int
    account_id: int
    title: str = "Untitled Build Request"
    job_type: str = "prompt_build"
    priority: str = "MEDIUM"  # LOW, MEDIUM, HIGH, CRITICAL
    requirements: Optional[str] = None
    reference_urls: Optional[List[str]] = None
    notes: Optional[str] = None
    attachments_metadata: Optional[List[Dict[str, Any]]] = None
    expected_completion_date: Optional[datetime] = None
    request_payload: Optional[str] = None


class BuildJobCreate(BuildJobBase):
    assigned_user_id: Optional[int] = None
    auto_start: bool = True  # If true, transitions from DRAFT to QUEUED immediately
    idempotency_key: Optional[str] = None


class BuildJobUpdate(BaseModel):
    title: Optional[str] = None
    priority: Optional[str] = None
    requirements: Optional[str] = None
    reference_urls: Optional[List[str]] = None
    notes: Optional[str] = None
    expected_completion_date: Optional[datetime] = None
    assigned_user_id: Optional[int] = None


class BuildJobResponse(BaseModel):
    id: int
    project_id: int
    project_name: Optional[str] = None
    project_key: Optional[str] = None
    account_id: int
    account_name: Optional[str] = None
    account_email: Optional[str] = None
    initiated_by_user_id: Optional[int] = None
    initiator_name: Optional[str] = None
    title: str
    job_type: str
    job_status: str
    priority: str
    requirements: Optional[str] = None
    reference_urls: Optional[List[str]] = None
    notes: Optional[str] = None
    attachments_metadata: Optional[List[Dict[str, Any]]] = None
    expected_completion_date: Optional[datetime] = None
    idempotency_key: Optional[str] = None
    worker_id: Optional[str] = None
    last_heartbeat_at: Optional[datetime] = None
    retry_count: int = 0
    max_retries: int = 3
    timeout_seconds: int = 3600
    execution_adapter: str = "MOCK_EMERGENT"
    is_mock: bool = True
    started_at: Optional[datetime] = None
    paused_at: Optional[datetime] = None
    cancelled_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    credits_used: Decimal = Decimal("0.0000")
    request_payload: Optional[str] = None
    result_summary: Optional[str] = None
    result_metadata: Optional[str] = None
    error_details: Optional[str] = None
    created_at: datetime
    updated_at: datetime
    assignments: List[JobAssignmentResponse] = []
    assigned_user_name: Optional[str] = None
    duration_seconds: Optional[float] = None

    model_config = ConfigDict(from_attributes=True)


class BuildJobDetailResponse(BuildJobResponse):
    history: List[BuildJobHistoryResponse] = []


class BuildDashboardStatsResponse(BaseModel):
    total_builds: int = 0
    draft_builds: int = 0
    queued_builds: int = 0
    running_builds: int = 0
    paused_builds: int = 0
    completed_builds: int = 0
    failed_builds: int = 0
    cancelled_builds: int = 0
    avg_execution_time_seconds: float = 0.0
    queue_health: str = "HEALTHY"
    available_workers: int = 0
    failed_job_alerts: int = 0
    mock_execution_count: int = 0
    real_execution_count: int = 0
    execution_enabled: bool = False
