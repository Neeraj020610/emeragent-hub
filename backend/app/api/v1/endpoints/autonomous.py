import os
import glob
import shutil
from typing import Any, Dict, List, Optional
from decimal import Decimal
from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import FileResponse, HTMLResponse
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.user import User
from app.models.autonomous import (
    AutonomousInstruction,
    AutonomousTask,
    AutonomousTaskLog,
    AccountCreditBudget,
)
from app.schemas.autonomous import (
    AutonomousInstructionCreate,
    AutonomousInstructionResponse,
    AutonomousTaskCreate,
    AutonomousTaskResponse,
    AutonomousTaskImportRequest,
    AutonomousTaskLogResponse,
    AccountCreditBudgetUpdate,
    AccountCreditBudgetResponse,
    SystemControlRequest,
    SystemChatCommandRequest,
    SystemChatCommandResponse,
    AutonomousSystemStateResponse,
)
from app.services.autonomous.brain import AutonomousBrainService
from app.services.autonomous.scheduler import AccountCreditScheduler
from app.services.autonomous.worker_engine import AutonomousWorkerEngine
from app.services.autonomous.control import AutonomousControlService
from app.dependencies import get_current_user, require_role, record_audit

router = APIRouter()
brain_service = AutonomousBrainService()
scheduler_service = AccountCreditScheduler()
worker_engine = AutonomousWorkerEngine(scheduler=scheduler_service, brain=brain_service)
control_service = AutonomousControlService(scheduler=scheduler_service, brain=brain_service)


# -------------------------------------------------------------
# 1. System Control & Chat Command Endpoints
# -------------------------------------------------------------
@router.get("/status", response_model=AutonomousSystemStateResponse)
def get_autonomous_status(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Returns overall platform autonomous status, command history, and queue telemetry."""
    state = control_service.get_or_create_state(db)
    telemetry = control_service.get_telemetry_summary(db)
    return AutonomousSystemStateResponse(
        status=state.status,
        last_command=state.last_command,
        last_command_at=state.last_command_at,
        command_message=state.command_message,
        active_workers_count=state.active_workers_count,
        total_tasks_queued=telemetry["total_tasks_queued"],
        total_tasks_in_progress=telemetry["total_tasks_in_progress"],
        total_tasks_completed=telemetry["total_tasks_completed"],
        total_tasks_failed=telemetry["total_tasks_failed"],
        eligible_accounts_count=telemetry["eligible_accounts_count"],
        updated_at=state.updated_at,
    )


@router.post("/control", response_model=AutonomousSystemStateResponse)
def control_autonomous_system(
    payload: SystemControlRequest,
    current_user: User = Depends(require_role(["ADMIN", "MANAGER"])),
    db: Session = Depends(get_db),
):
    """Executes a system-level control command: START, PAUSE, RESUME, STOP."""
    try:
        state = control_service.execute_command(
            command=payload.command,
            user=current_user,
            db=db,
            message=payload.message,
        )
        record_audit(
            db=db,
            user_id=current_user.id,
            action=f"AUTONOMOUS_CONTROL_{payload.command.upper()}",
            resource_type="autonomous_system",
            details=f"State changed to {state.status}. Note: {payload.message or 'None'}",
        )
        telemetry = control_service.get_telemetry_summary(db)
        return AutonomousSystemStateResponse(
            status=state.status,
            last_command=state.last_command,
            last_command_at=state.last_command_at,
            command_message=state.command_message,
            active_workers_count=state.active_workers_count,
            total_tasks_queued=telemetry["total_tasks_queued"],
            total_tasks_in_progress=telemetry["total_tasks_in_progress"],
            total_tasks_completed=telemetry["total_tasks_completed"],
            total_tasks_failed=telemetry["total_tasks_failed"],
            eligible_accounts_count=telemetry["eligible_accounts_count"],
            updated_at=state.updated_at,
        )
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.post("/chat", response_model=SystemChatCommandResponse)
def execute_chat_command(
    payload: SystemChatCommandRequest,
    current_user: User = Depends(require_role(["ADMIN", "MANAGER"])),
    db: Session = Depends(get_db),
):
    """Conversational natural command interpreter (e.g. 'START', 'PAUSE', 'STATUS', 'ROTATE')."""
    res = control_service.process_chat_command(raw_text=payload.command_text, user=current_user, db=db)
    record_audit(
        db=db,
        user_id=current_user.id,
        action="AUTONOMOUS_CHAT_COMMAND",
        resource_type="autonomous_system",
        details=f"Command '{payload.command_text}' processed as '{res['command']}'.",
    )
    return SystemChatCommandResponse(
        command=res["command"],
        system_status=res["system_status"],
        message=res["message"],
        timestamp=res["timestamp"],
        details=res.get("details"),
    )


# -------------------------------------------------------------
# 2. Autonomous Instructions Endpoints (Phase 5A)
# -------------------------------------------------------------
@router.post("/instructions", response_model=AutonomousInstructionResponse)
def create_instruction(
    payload: AutonomousInstructionCreate,
    current_user: User = Depends(require_role(["ADMIN", "MANAGER"])),
    db: Session = Depends(get_db),
):
    """Registers an administrator-defined reusable instruction for Video or Web/App development."""
    instruction = brain_service.create_instruction(payload=payload, user_id=current_user.id, db=db)
    return instruction


@router.get("/instructions", response_model=List[AutonomousInstructionResponse])
def list_instructions(
    project_id: Optional[int] = None,
    work_type: Optional[str] = None,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Lists reusable project instructions."""
    query = db.query(AutonomousInstruction)
    if project_id:
        query = query.filter(AutonomousInstruction.project_id == project_id)
    if work_type:
        query = query.filter(AutonomousInstruction.work_type == work_type)
    return query.order_by(AutonomousInstruction.created_at.desc()).all()


@router.post("/instructions/{instruction_id}/plan", response_model=List[AutonomousTaskResponse])
def generate_plan_from_instruction(
    instruction_id: int,
    current_user: User = Depends(require_role(["ADMIN", "MANAGER"])),
    db: Session = Depends(get_db),
):
    """Autonomous Brain plan generator: converts instruction into bounded actionable tasks."""
    try:
        tasks = brain_service.generate_plan_and_tasks(instruction_id=instruction_id, db=db)
        return tasks
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))


# -------------------------------------------------------------
# 3. Tasks & Queue Endpoints
# -------------------------------------------------------------
@router.get("/tasks", response_model=List[AutonomousTaskResponse])
def list_tasks(
    project_id: Optional[int] = None,
    work_type: Optional[str] = None,
    status_filter: Optional[str] = None,
    priority: Optional[str] = None,
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Lists autonomous tasks across all sources (AI-generated, manual, imported)."""
    query = db.query(AutonomousTask)
    if project_id:
        query = query.filter(AutonomousTask.project_id == project_id)
    if work_type:
        query = query.filter(AutonomousTask.work_type == work_type)
    if status_filter:
        query = query.filter(AutonomousTask.status == status_filter)
    if priority:
        query = query.filter(AutonomousTask.priority == priority)
    return query.order_by(AutonomousTask.created_at.desc()).offset(offset).limit(limit).all()


@router.post("/tasks", response_model=AutonomousTaskResponse)
def create_manual_task(
    payload: AutonomousTaskCreate,
    current_user: User = Depends(require_role(["ADMIN", "MANAGER"])),
    db: Session = Depends(get_db),
):
    """Manually supplies a single task to the autonomous pipeline."""
    task = brain_service.create_manual_task(payload=payload, db=db)
    return task


@router.post("/tasks/import", response_model=List[AutonomousTaskResponse])
def import_tasks_bulk(
    payload: AutonomousTaskImportRequest,
    current_user: User = Depends(require_role(["ADMIN", "MANAGER"])),
    db: Session = Depends(get_db),
):
    """Bulk imports a queue of manual/external tasks into the pipeline."""
    tasks = brain_service.import_tasks_bulk(payload=payload, db=db)
    return tasks


@router.get("/tasks/{task_id}", response_model=AutonomousTaskResponse)
def get_task_detail(
    task_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Retrieves full detail and checkpoint state of an autonomous task."""
    task = db.query(AutonomousTask).filter(AutonomousTask.id == task_id).first()
    if not task:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Task {task_id} not found.")
    return task


@router.get("/tasks/{task_id}/logs", response_model=List[AutonomousTaskLogResponse])
def get_task_logs(
    task_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Retrieves step-by-step execution history and logs for a task."""
    logs = (
        db.query(AutonomousTaskLog)
        .filter(AutonomousTaskLog.task_id == task_id)
        .order_by(AutonomousTaskLog.created_at.asc())
        .all()
    )
    return logs


@router.get("/tasks/{task_id}/video")
def get_task_video(
    task_id: int,
    db: Session = Depends(get_db),
):
    """Streams and serves the actual MP4 video file tailored to this task's prompt."""
    task = db.query(AutonomousTask).filter(AutonomousTask.id == task_id).first()
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")

    video_dir = os.path.join(os.getcwd(), "storage", "artifacts", "videos")
    file_path = os.path.join(video_dir, f"{task.task_identifier}.mp4")

    if not os.path.exists(file_path):
        if not task.is_mock:
            raise HTTPException(status_code=404, detail="Real Emergent video is still generating or not yet downloaded.")
        from app.services.autonomous.adapters.content_synthesizer import (
            build_prompt_specific_script,
            generate_custom_mp4_video,
        )
        os.makedirs(video_dir, exist_ok=True)
        script_data = build_prompt_specific_script(
            title=task.title,
            description=task.description or "",
            expected_result=task.expected_result or "",
        )
        generate_custom_mp4_video(task.task_identifier, script_data, file_path)

    if not os.path.exists(file_path):
        raise HTTPException(status_code=404, detail="Video file not found")

    return FileResponse(
        file_path,
        media_type="video/mp4",
        filename=f"{task.task_identifier}.mp4",
        headers={"Accept-Ranges": "bytes"},
    )


@router.get("/tasks/{task_id}/preview-image")
def get_task_preview_image(
    task_id: int,
    db: Session = Depends(get_db),
):
    """Serves the latest live Emergent browser screenshot captured for a real task."""
    task = db.query(AutonomousTask).filter(AutonomousTask.id == task_id).first()
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    shot_path = os.path.join(os.getcwd(), "storage", "artifacts", "emergent_shots", f"{task.task_identifier}.png")
    if not os.path.exists(shot_path):
        raise HTTPException(status_code=404, detail="Preview screenshot not available yet")
    return FileResponse(
        shot_path,
        media_type="image/png",
        headers={"Cache-Control": "no-store, no-cache, must-revalidate, max-age=0"},
    )


@router.get("/tasks/{task_id}/webapp")
def get_task_webapp(
    task_id: int,
    download: bool = Query(False),
    db: Session = Depends(get_db),
):
    """Serves or downloads the generated interactive HTML webpage for a Website/App task."""
    task = db.query(AutonomousTask).filter(AutonomousTask.id == task_id).first()
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")

    webapp_dir = os.path.join(os.getcwd(), "storage", "artifacts", "webapps")
    file_path = os.path.join(webapp_dir, f"{task.task_identifier}.html")

    if not os.path.exists(file_path):
        from app.services.autonomous.adapters.content_synthesizer import generate_custom_webapp_html
        file_path = generate_custom_webapp_html(
            task_identifier=task.task_identifier,
            title=task.title,
            description=task.description or "",
        )

    if download:
        return FileResponse(
            file_path,
            media_type="text/html",
            filename=f"{task.task_identifier}-app.html",
        )

    with open(file_path, "r", encoding="utf-8") as f:
        return HTMLResponse(content=f.read())


# -------------------------------------------------------------
# 4. Multi-Account Rotation & 50% Credit Ceiling (Phase 5C)
# -------------------------------------------------------------
@router.get("/budgets", response_model=List[AccountCreditBudgetResponse])
def list_account_budgets(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Returns live account budgets enforcing the mandatory 50% Planned Usage Ceiling.
    Shows starting balance, current verified balance, 50% ceiling limit, usage, reserved, and eligibility.
    """
    return scheduler_service.list_account_budgets(db=db)


@router.put("/budgets/{account_id}", response_model=AccountCreditBudgetResponse)
def update_account_budget(
    account_id: int,
    payload: AccountCreditBudgetUpdate,
    current_user: User = Depends(require_role(["ADMIN"])),
    db: Session = Depends(get_db),
):
    """Updates verified starting balance and planned ceiling percentage for an account."""
    budget = scheduler_service.update_account_budget(
        account_id=account_id,
        starting_balance=payload.starting_balance,
        ceiling_percentage=payload.ceiling_percentage,
        balance_source=payload.balance_source or "MANUAL",
        db=db,
    )
    ceiling_limit = (budget.starting_balance * budget.ceiling_percentage) / Decimal("100.00")
    current_committed = budget.credit_usage + budget.reserved_credits
    remaining = max(Decimal("0.0000"), ceiling_limit - current_committed)
    return AccountCreditBudgetResponse(
        id=budget.id,
        account_id=budget.account_id,
        account_name=budget.account.account_name if budget.account else None,
        starting_balance=budget.starting_balance,
        verified_current_balance=budget.verified_current_balance,
        credit_usage=budget.credit_usage,
        reserved_credits=budget.reserved_credits,
        ceiling_percentage=budget.ceiling_percentage,
        planned_ceiling_limit=ceiling_limit,
        remaining_eligible_budget=remaining,
        balance_source=budget.balance_source,
        last_balance_validated_at=budget.last_balance_validated_at,
        is_eligible=budget.is_eligible,
        ineligibility_reason=budget.ineligibility_reason,
        universal_api_usage=budget.universal_api_usage,
        platform_build_usage=budget.platform_build_usage,
        active_task_id=budget.active_task_id,
        created_at=budget.created_at,
        updated_at=budget.updated_at,
    )


# -------------------------------------------------------------
# 5. Autonomous Worker Dispatch Step
# -------------------------------------------------------------
@router.post("/worker/step")
def trigger_worker_step(
    task_id: Optional[int] = Query(None),
    current_user: User = Depends(require_role(["ADMIN", "MANAGER"])),
    db: Session = Depends(get_db),
):
    """
    Triggers the autonomous worker engine to dispatch or advance the next eligible task step.
    Enforces priority scheduling, 50% credit ceiling guard, and 1 execution per account.
    """
    res = worker_engine.poll_and_dispatch_next_task(db=db, force_run=True, target_task_id=task_id)
    if not res:
        return {"status": "IDLE", "message": "No eligible tasks ready or all tasks completed."}
    return res
