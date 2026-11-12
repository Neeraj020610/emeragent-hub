from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.user import User
from app.models.audit import AuditLog
from app.schemas.project import (
    ProjectCreate,
    ProjectUpdate,
    ProjectResponse,
    ProjectDetailResponse,
    ProjectMemberCreate,
    ProjectMemberResponse,
)
from app.schemas.audit import AuditLogResponse
from app.services.build.service import BuildService
from app.dependencies import get_current_user, require_role

router = APIRouter()
build_service = BuildService()


@router.get("", response_model=List[ProjectResponse])
def list_projects(
    account_id: Optional[int] = None,
    status: Optional[str] = None,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Lists projects accessible to the current user (filtered by RBAC and project membership)."""
    return build_service.list_projects(
        current_user=current_user,
        db=db,
        account_id=account_id,
        status_filter=status,
    )


@router.post("", response_model=ProjectDetailResponse, status_code=status.HTTP_201_CREATED)
def create_project(
    request: Request,
    payload: ProjectCreate,
    current_user: User = Depends(require_role(["ADMIN", "MANAGER"])),
    db: Session = Depends(get_db),
):
    """Creates a new project. Restricted to ADMIN and MANAGER."""
    ip_address = request.client.host if request.client else None
    return build_service.create_project(
        payload=payload,
        current_user=current_user,
        db=db,
        ip_address=ip_address,
    )


@router.get("/{project_id}", response_model=ProjectDetailResponse)
def get_project(
    project_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Retrieves full project details including members and build statistics."""
    return build_service.get_project_details(
        project_id=project_id,
        current_user=current_user,
        db=db,
    )


@router.put("/{project_id}", response_model=ProjectDetailResponse)
def update_project(
    project_id: int,
    payload: ProjectUpdate,
    request: Request,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Updates project properties. Requires MANAGER or ADMIN permissions on the project."""
    ip_address = request.client.host if request.client else None
    return build_service.update_project(
        project_id=project_id,
        payload=payload,
        current_user=current_user,
        db=db,
        ip_address=ip_address,
    )


@router.post("/{project_id}/members", response_model=ProjectMemberResponse)
def add_project_member(
    project_id: int,
    payload: ProjectMemberCreate,
    request: Request,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Assigns or updates a member's role in a project. Requires project management permissions."""
    ip_address = request.client.host if request.client else None
    return build_service.add_project_member(
        project_id=project_id,
        user_id=payload.user_id,
        role_in_project=payload.role_in_project,
        current_user=current_user,
        db=db,
        ip_address=ip_address,
    )


@router.delete("/{project_id}/members/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
def remove_project_member(
    project_id: int,
    user_id: int,
    request: Request,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Removes a member from a project."""
    ip_address = request.client.host if request.client else None
    build_service.remove_project_member(
        project_id=project_id,
        user_id=user_id,
        current_user=current_user,
        db=db,
        ip_address=ip_address,
    )
    return None


@router.get("/{project_id}/activity", response_model=List[AuditLogResponse])
def get_project_activity(
    project_id: int,
    limit: int = 50,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Retrieves project audit activity history."""
    # Verify access to project first
    build_service.get_project_details(project_id, current_user, db)
    
    logs = (
        db.query(AuditLog)
        .filter(AuditLog.resource_type == "project", AuditLog.resource_id == str(project_id))
        .order_by(AuditLog.created_at.desc())
        .limit(limit)
        .all()
    )
    return logs
