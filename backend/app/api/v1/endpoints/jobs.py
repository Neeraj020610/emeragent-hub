from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Request, status, Query
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.user import User
from app.models.job import BuildJob
from app.schemas.job import (
    BuildJobCreate,
    BuildJobResponse,
    BuildJobDetailResponse,
    BuildDashboardStatsResponse,
)
from app.services.build.service import BuildService
from app.services.build.state_machine import InvalidTransitionError
from app.dependencies import get_current_user, require_role

router = APIRouter()
build_service = BuildService()


@router.get("/dashboard/stats", response_model=BuildDashboardStatsResponse)
def get_build_dashboard_stats(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Returns aggregated metrics and health status for the Build Manager dashboard.
    Clearly reports mock versus real execution counts.
    """
    return build_service.get_dashboard_stats(db=db)


@router.get("", response_model=List[BuildJobResponse])
def list_build_jobs(
    project_id: Optional[int] = None,
    account_id: Optional[int] = None,
    status: Optional[str] = None,
    priority: Optional[str] = None,
    assigned_user_id: Optional[int] = None,
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Lists build requests with filtering, search support, and RBAC isolation.
    """
    return build_service.list_build_jobs(
        current_user=current_user,
        db=db,
        project_id=project_id,
        account_id=account_id,
        status_filter=status,
        priority_filter=priority,
        assigned_user_id=assigned_user_id,
        limit=limit,
        offset=offset,
    )


@router.post("", response_model=BuildJobDetailResponse, status_code=status.HTTP_201_CREATED)
def create_build_job(
    request: Request,
    payload: BuildJobCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Creates a new build request.
    Validates project access, account permissions, and personal consent.
    Enforces idempotency and optionally enqueues into the execution engine.
    """
    ip_address = request.client.host if request.client else None
    return build_service.create_build_job(
        payload=payload,
        current_user=current_user,
        db=db,
        ip_address=ip_address,
    )


@router.get("/{job_id}", response_model=BuildJobDetailResponse)
def get_build_job(
    job_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Retrieves full build job details including execution timeline and history.
    """
    return build_service.get_build_job_details(
        job_id=job_id,
        current_user=current_user,
        db=db,
    )


@router.post("/{job_id}/start", response_model=BuildJobDetailResponse)
def start_build_job(
    job_id: int,
    request: Request,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Transitions a DRAFT build into the QUEUED execution state."""
    ip_address = request.client.host if request.client else None
    try:
        return build_service.start_job(
            job_id=job_id,
            current_user=current_user,
            db=db,
            ip_address=ip_address,
        )
    except InvalidTransitionError as ite:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(ite))


@router.post("/{job_id}/execute", response_model=BuildJobDetailResponse)
def execute_build_job_direct(
    job_id: int,
    request: Request,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Starts and immediately runs the build job through the execution queue engine."""
    ip_address = request.client.host if request.client else None
    job = db.query(BuildJob).filter(BuildJob.id == job_id).first()
    if not job:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Build job not found.")

    if job.job_status == "DRAFT":
        build_service.start_job(job_id=job_id, current_user=current_user, db=db, ip_address=ip_address)

    if job.job_status == "QUEUED":
        job.job_status = "STARTING"
        job.worker_id = build_service.queue.worker_id
        db.commit()

    executed = build_service.queue.execute_claimed_job(db=db, job_id=job_id)
    return build_service.get_build_job_details(executed.id, current_user, db)
  

@router.post("/{job_id}/pause", response_model=BuildJobDetailResponse)
def pause_build_job(
    job_id: int,
    request: Request,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Pauses a currently RUNNING build job."""
    ip_address = request.client.host if request.client else None
    try:
        return build_service.pause_job(
            job_id=job_id,
            current_user=current_user,
            db=db,
            ip_address=ip_address,
        )
    except InvalidTransitionError as ite:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(ite))


@router.post("/{job_id}/resume", response_model=BuildJobDetailResponse)
def resume_build_job(
    job_id: int,
    request: Request,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Resumes a PAUSED build job."""
    ip_address = request.client.host if request.client else None
    try:
        return build_service.resume_job(
            job_id=job_id,
            current_user=current_user,
            db=db,
            ip_address=ip_address,
        )
    except InvalidTransitionError as ite:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(ite))


@router.post("/{job_id}/cancel", response_model=BuildJobDetailResponse)
def cancel_build_job(
    job_id: int,
    request: Request,
    reason: Optional[str] = None,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Cancels a non-terminal build job."""
    ip_address = request.client.host if request.client else None
    try:
        return build_service.cancel_job(
            job_id=job_id,
            current_user=current_user,
            db=db,
            reason=reason,
            ip_address=ip_address,
        )
    except InvalidTransitionError as ite:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(ite))


@router.post("/{job_id}/retry", response_model=BuildJobDetailResponse)
def retry_build_job(
    job_id: int,
    request: Request,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Re-enqueues a FAILED build job."""
    ip_address = request.client.host if request.client else None
    try:
        return build_service.retry_job(
            job_id=job_id,
            current_user=current_user,
            db=db,
            ip_address=ip_address,
        )
    except InvalidTransitionError as ite:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(ite))


@router.post("/queue/process-next", response_model=Optional[BuildJobResponse])
def process_next_queued_job(
    current_user: User = Depends(require_role(["ADMIN", "MANAGER"])),
    db: Session = Depends(get_db),
):
    """
    Claims and processes the highest priority QUEUED job in the execution engine.
    Priority scheduling: CRITICAL > HIGH > MEDIUM > LOW (FIFO tie-breaker).
    """
    claimed = build_service.queue.claim_next_job(db=db)
    if not claimed:
        return None

    executed = build_service.queue.execute_claimed_job(db=db, job_id=claimed.id)
    return build_service._build_job_response(executed, db)


@router.post("/queue/reap-crashes")
def reap_crashed_workers(
    threshold_seconds: Optional[int] = None,
    current_user: User = Depends(require_role(["ADMIN"])),
    db: Session = Depends(get_db),
):
    """
    Admin sweep to detect worker crashes and stale executions,
    automatically recovering jobs via retry policy.
    """
    return build_service.queue.check_timeouts_and_reap_crashes(
        db=db,
        stale_threshold_seconds=threshold_seconds,
    )
