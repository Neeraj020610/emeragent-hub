"""
Autonomous Worker Engine
Phase 5B Implementation for Emergent Central Hub

Coordinates:
- Continuous task polling from persistent DB queue
- Priority scheduling (CRITICAL > HIGH > MEDIUM > LOW)
- Account selection with 50% Credit Ceiling Guard
- Heartbeat tracking and crash recovery for orphaned tasks
- Step-by-step checkpointing and execution history logging
- Exponential backoff retry on transient failures
- Error classification and graceful shutdown / pause controls
"""
import json
import logging
import uuid
from datetime import datetime, timezone, timedelta
from decimal import Decimal
from typing import Any, Dict, List, Optional, Tuple
from sqlalchemy.orm import Session
from sqlalchemy import func, case

from app.models.account import EmergentAccount
from app.models.session import AccountSession
from app.models.autonomous import (
    AutonomousTask,
    AutonomousTaskLog,
    AutonomousSystemState,
    AccountCreditBudget,
)
from app.services.autonomous.brain import AutonomousBrainService
from app.services.autonomous.scheduler import AccountCreditScheduler
from app.services.autonomous.adapters.video_adapter import MockVideoExecutionAdapter
from app.services.autonomous.adapters.webapp_adapter import MockWebAppExecutionAdapter
from app.services.autonomous.adapters.base import BaseAutonomousAdapter, StepResult

logger = logging.getLogger("emergent.autonomous.worker_engine")


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class AutonomousWorkerEngine:
    def __init__(
        self,
        worker_id: Optional[str] = None,
        scheduler: Optional[AccountCreditScheduler] = None,
        brain: Optional[AutonomousBrainService] = None,
    ):
        self.worker_id = worker_id or f"worker-{uuid.uuid4().hex[:8]}"
        self.scheduler = scheduler or AccountCreditScheduler()
        self.brain = brain or AutonomousBrainService()
        self.video_adapter = MockVideoExecutionAdapter()
        self.webapp_adapter = MockWebAppExecutionAdapter()

    def get_adapter(self, work_type: str) -> BaseAutonomousAdapter:
        if work_type == "VIDEO_CREATION":
            return self.video_adapter
        return self.webapp_adapter

    def get_system_state(self, db: Session) -> AutonomousSystemState:
        state = db.query(AutonomousSystemState).first()
        if not state:
            state = AutonomousSystemState(
                status="STOPPED",
                last_command="STOP",
                last_command_at=utcnow(),
                command_message="System initialized in STOPPED state.",
                active_workers_count=0,
                updated_at=utcnow(),
            )
            db.add(state)
            db.commit()
            db.refresh(state)
        return state

    def recover_orphaned_tasks(self, db: Session, timeout_minutes: int = 15) -> int:
        """
        Crash recovery: detects tasks left in IN_PROGRESS with heartbeat older than timeout.
        Resets them to QUEUED (if retry_count < max_retries) or FAILED.
        """
        threshold = utcnow() - timedelta(minutes=timeout_minutes)
        orphaned = (
            db.query(AutonomousTask)
            .filter(
                AutonomousTask.status == "IN_PROGRESS",
                AutonomousTask.last_heartbeat_at < threshold,
            )
            .all()
        )
        recovered_count = 0
        for task in orphaned:
            logger.warning(f"Recovering orphaned task {task.task_identifier} (last heartbeat: {task.last_heartbeat_at})")
            if task.assigned_account_id:
                # Release active lock
                budget = db.query(AccountCreditBudget).filter(AccountCreditBudget.account_id == task.assigned_account_id).first()
                if budget and budget.active_task_id == task.id:
                    budget.active_task_id = None

            if task.retry_count < task.max_retries:
                task.retry_count += 1
                task.status = "QUEUED"
                task.error_classification = "CRASH_RECOVERY"
                task.error_details = "Worker heartbeat timed out. Task reset to queue with retry."
            else:
                task.status = "FAILED"
                task.error_classification = "MAX_RETRIES_EXCEEDED"
                task.error_details = "Worker heartbeat timed out and max retries reached."

            self._log_event(
                task_id=task.id,
                level="WARN",
                message=f"Crash recovery applied. New status: {task.status}",
                step="CRASH_RECOVERY",
                db=db,
            )
            recovered_count += 1

        db.commit()
        return recovered_count

    def poll_and_dispatch_next_task(
        self,
        db: Session,
        force_run: bool = False,
        target_task_id: Optional[int] = None,
    ) -> Optional[Dict[str, Any]]:
        """
        Polls for the highest priority task ready to execute, verifies dependencies,
        selects an eligible Emergent account under the 50% credit ceiling, and executes
        the next checkpoint step.
        """
        system_state = self.get_system_state(db)
        if not force_run and system_state.status != "RUNNING":
            logger.debug(f"Worker engine idle: system is {system_state.status}")
            return None

        # Recover any timed-out tasks first
        self.recover_orphaned_tasks(db)

        queued_task = None
        if target_task_id:
            target = db.query(AutonomousTask).filter(AutonomousTask.id == target_task_id).first()
            if target and target.status in ("QUEUED", "CHECKPOINT", "PLANNED"):
                if target.status == "PLANNED":
                    target.status = "QUEUED"
                    db.commit()
                queued_task = target

        if not queued_task:
            # 1. Promote PLANNED / BLOCKED tasks to QUEUED if dependencies are satisfied
            candidate_tasks = db.query(AutonomousTask).filter(AutonomousTask.status.in_(["PLANNED", "BLOCKED"])).all()
            for pt in candidate_tasks:
                is_ready, blocker = self.brain.check_task_dependencies(pt, db)
                if is_ready:
                    pt.status = "QUEUED"
                    pt.error_details = None
                else:
                    pt.status = "BLOCKED"
                    pt.error_details = f"Blocked on prerequisite task: {blocker}"
            db.commit()

            # 2. Priority Scheduling: CRITICAL (4) > HIGH (3) > MEDIUM (2) > LOW (1)
            priority_order = case(
                (AutonomousTask.priority == "CRITICAL", 4),
                (AutonomousTask.priority == "HIGH", 3),
                (AutonomousTask.priority == "MEDIUM", 2),
                (AutonomousTask.priority == "LOW", 1),
                else_=0,
            )

            queued_task = (
                db.query(AutonomousTask)
                .filter(
                    AutonomousTask.status.in_(["QUEUED", "CHECKPOINT"]),
                    AutonomousTask.is_mock == True,
                    AutonomousTask.execution_adapter != "EMERGENT_BROWSER_ADAPTER",
                )
                .order_by(priority_order.desc(), AutonomousTask.created_at.asc())
                .first()
            )

        if not queued_task:
            return None

        # 3. Account Selection & 50% Credit Guard
        account = None
        if queued_task.assigned_account_id:
            acc = db.query(EmergentAccount).filter(EmergentAccount.id == queued_task.assigned_account_id).first()
            if acc:
                budget = self.scheduler.get_or_create_budget(acc.id, db)
                is_eligible, reason = self.scheduler.evaluate_account_eligibility(budget, db, current_task_id=queued_task.id)
                if is_eligible:
                    account = acc
                else:
                    logger.info(f"Assigned account {acc.account_name} not eligible ({reason}). Attempting rotation.")

        if not account:
            selection = self.scheduler.select_eligible_account(
                work_type=queued_task.work_type,
                estimated_cost=queued_task.estimated_credit_cost,
                db=db,
            )
            if not selection:
                logger.warning(f"No eligible account available for task {queued_task.task_identifier}. Waiting for account availability.")
                queued_task.status = "BLOCKED"
                queued_task.error_classification = "CREDIT_CEILING_REACHED"
                queued_task.error_details = "All Emergent accounts have reached their 50% Planned Usage Ceiling or have invalid sessions."
                db.commit()
                return None
            account, _ = selection
            queued_task.assigned_account_id = account.id

        # 4. Reserve budget before execution
        reserved = self.scheduler.reserve_budget(
            account_id=account.id,
            task_id=queued_task.id,
            estimated_cost=queued_task.estimated_credit_cost,
            db=db,
        )
        if not reserved:
            queued_task.status = "BLOCKED"
            queued_task.error_details = "Failed to reserve budget within 50% ceiling."
            db.commit()
            return None

        # 5. Execute next step
        return self._execute_task_step(queued_task, account, db)

    def _execute_task_step(
        self,
        task: AutonomousTask,
        account: EmergentAccount,
        db: Session,
    ) -> Dict[str, Any]:
        """Executes a single atomic checkpoint step on the assigned account."""
        adapter = self.get_adapter(task.work_type)

        # Mark in progress with heartbeat
        task.status = "IN_PROGRESS"
        task.worker_id = self.worker_id
        task.last_heartbeat_at = utcnow()
        if not task.started_at:
            task.started_at = utcnow()
        db.commit()

        # Load existing checkpoints
        current_checkpoints: List[Dict[str, Any]] = []
        if task.checkpoints:
            try:
                current_checkpoints = json.loads(task.checkpoints)
            except Exception:
                current_checkpoints = []

        try:
            step_result: StepResult = adapter.execute_next_step(
                task=task,
                account=account,
                current_checkpoints=current_checkpoints,
                db=db,
            )
        except Exception as e:
            logger.exception(f"Execution error on task {task.task_identifier}: {e}")
            step_result = StepResult(
                success=False,
                step_name="EXECUTION_FAILURE",
                checkpoint_data={},
                error_message=str(e),
                error_classification="UNHANDLED_EXCEPTION",
            )

        if not step_result.success:
            # Handle failure with retry
            task.retry_count += 1
            task.error_classification = step_result.error_classification or "TASK_FAILURE"
            task.error_details = step_result.error_message
            if task.retry_count < task.max_retries:
                task.status = "QUEUED"
            else:
                task.status = "FAILED"

            self.scheduler.record_usage_and_release(
                account_id=account.id,
                task_id=task.id,
                estimated_cost=task.estimated_credit_cost,
                actual_cost=Decimal("0.0000"),
                usage_type="PLATFORM_BUILD",
                db=db,
            )
            self._log_event(
                task_id=task.id,
                level="ERROR",
                message=f"Step {step_result.step_name} failed: {step_result.error_message}. Retry {task.retry_count}/{task.max_retries}",
                step=step_result.step_name,
                db=db,
            )
            db.commit()
            return {
                "task_id": task.task_identifier,
                "status": task.status,
                "success": False,
                "error": step_result.error_message,
            }

        # Step succeeded: append checkpoint
        current_checkpoints.append(step_result.checkpoint_data)
        task.checkpoints = json.dumps(current_checkpoints)
        task.actual_credit_cost += step_result.credits_consumed
        task.last_heartbeat_at = utcnow()

        self._log_event(
            task_id=task.id,
            level="INFO",
            message=f"Completed checkpoint: {step_result.step_name} (Cost: {step_result.credits_consumed:.4f})",
            step=step_result.step_name,
            db=db,
        )

        if step_result.is_completed:
            task.status = "COMPLETED"
            task.completed_at = utcnow()
            task.result_metadata = json.dumps(step_result.result_metadata)
            # Reconcile full usage against 50% credit ceiling
            self.scheduler.record_usage_and_release(
                account_id=account.id,
                task_id=task.id,
                estimated_cost=task.estimated_credit_cost,
                actual_cost=task.actual_credit_cost,
                usage_type="PLATFORM_BUILD",
                db=db,
            )
            self._log_event(
                task_id=task.id,
                level="INFO",
                message=f"Task fully completed! Total actual credits: {task.actual_credit_cost:.4f}",
                step="COMPLETED",
                db=db,
            )
        else:
            # Task has more checkpoints: leave in CHECKPOINT status for next polling turn
            task.status = "CHECKPOINT"

        db.commit()
        db.refresh(task)

        return {
            "task_id": task.task_identifier,
            "status": task.status,
            "step_completed": step_result.step_name,
            "credits_consumed": float(step_result.credits_consumed),
            "is_completed": step_result.is_completed,
            "account_name": account.account_name,
        }

    def _log_event(
        self,
        task_id: int,
        level: str,
        message: str,
        step: str,
        db: Session,
    ) -> None:
        log_entry = AutonomousTaskLog(
            task_id=task_id,
            worker_id=self.worker_id,
            log_level=level,
            message=message,
            step_name=step,
            created_at=utcnow(),
        )
        db.add(log_entry)
