from datetime import datetime
from typing import Optional, List
from pydantic import BaseModel, ConfigDict, Field


class ProjectMemberBase(BaseModel):
    user_id: int
    role_in_project: str = Field(default="developer", description="lead, developer, reviewer, observer")


class ProjectMemberCreate(ProjectMemberBase):
    pass


class ProjectMemberResponse(ProjectMemberBase):
    id: int
    project_id: int
    assigned_at: datetime
    user_email: Optional[str] = None
    user_full_name: Optional[str] = None

    model_config = ConfigDict(from_attributes=True)


class ProjectBase(BaseModel):
    account_id: int
    project_name: str
    project_key: str
    description: Optional[str] = None
    status: str = "PLANNING"  # PLANNING, ACTIVE, ON_HOLD, COMPLETED, ARCHIVED
    start_date: Optional[datetime] = None
    expected_completion_date: Optional[datetime] = None
    tags: Optional[str] = None


class ProjectCreate(ProjectBase):
    owner_user_id: Optional[int] = None
    member_user_ids: Optional[List[int]] = None


class ProjectUpdate(BaseModel):
    project_name: Optional[str] = None
    description: Optional[str] = None
    status: Optional[str] = None
    account_id: Optional[int] = None
    owner_user_id: Optional[int] = None
    start_date: Optional[datetime] = None
    expected_completion_date: Optional[datetime] = None
    tags: Optional[str] = None


class ProjectResponse(ProjectBase):
    id: int
    owner_user_id: Optional[int] = None
    owner_name: Optional[str] = None
    account_name: Optional[str] = None
    created_at: datetime
    updated_at: datetime
    total_builds_count: int = 0
    active_builds_count: int = 0

    model_config = ConfigDict(from_attributes=True)


class ProjectDetailResponse(ProjectResponse):
    members: List[ProjectMemberResponse] = []
