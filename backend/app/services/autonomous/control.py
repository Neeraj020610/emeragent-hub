"""
Autonomous Control and Chat Command Service
Phase 5 Implementation for Emergent Central Hub

Handles:
- Centralized START, PAUSE, RESUME, and STOP state controls
- Natural chat command interpretation ("START", "PAUSE", "RESUME", "STOP", "STATUS", "ROTATE", "TASKS")
- Session and automatic OTP re-authentication integration
- System state aggregation and worker telemetry
"""
import logging
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from sqlalchemy.orm import Session
from sqlalchemy import func

from app.models.user import User
from app.models.account import EmergentAccount
from app.models.session import AccountSession
from app.models.autonomous import (
    AutonomousTask,
    AutonomousSystemState,
    AccountCreditBudget,
    AutonomousInstruction,
)
from app.services.autonomous.scheduler import AccountCreditScheduler
from app.services.autonomous.brain import AutonomousBrainService
from app.services.otp.orchestrator import OTPOrchestrator

logger = logging.getLogger("emergent.autonomous.control")


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class AutonomousControlService:
    def __init__(
        self,
        scheduler: Optional[AccountCreditScheduler] = None,
        brain: Optional[AutonomousBrainService] = None,
        otp_orchestrator: Optional[OTPOrchestrator] = None,
    ):
        self.scheduler = scheduler or AccountCreditScheduler()
        self.brain = brain or AutonomousBrainService()
        self.otp_orchestrator = otp_orchestrator or OTPOrchestrator()

    def get_or_create_state(self, db: Session) -> AutonomousSystemState:
        state = db.query(AutonomousSystemState).first()
        if not state:
            state = AutonomousSystemState(
                status="STOPPED",
                last_command="STOP",
                last_command_at=utcnow(),
                command_message="Platform initialized in STOPPED state.",
                active_workers_count=0,
                updated_at=utcnow(),
            )
            db.add(state)
            db.commit()
            db.refresh(state)
        return state

    def execute_command(
        self,
        command: str,
        user: Optional[User],
        db: Session,
        message: Optional[str] = None,
    ) -> AutonomousSystemState:
        """
        Executes a high-level system control command:
        - START: Transitions system to RUNNING, promotes PLANNED tasks to QUEUED.
        - PAUSE: Transitions system to PAUSED, workers gracefully hold at checkpoints.
        - RESUME: Resumes execution from PAUSED to RUNNING.
        - STOP: Stops all autonomous operations immediately.
        """
        cmd = command.strip().upper()
        if cmd not in ("START", "PAUSE", "RESUME", "STOP"):
            raise ValueError(f"Invalid command '{command}'. Valid: START, PAUSE, RESUME, STOP.")

        state = self.get_or_create_state(db)
        state.last_command = cmd
        state.last_command_at = utcnow()
        state.last_command_by_user_id = user.id if user else None
        state.command_message = message or f"Operator issued {cmd} command."

        if cmd == "START":
            state.status = "RUNNING"
            state.active_workers_count = 1
            # Promote any PLANNED tasks to QUEUED if dependencies ready
            planned = db.query(AutonomousTask).filter(AutonomousTask.status == "PLANNED").all()
            for t in planned:
                is_ready, _ = self.brain.check_task_dependencies(t, db)
                if is_ready:
                    t.status = "QUEUED"
        elif cmd == "PAUSE":
            state.status = "PAUSED"
            state.active_workers_count = 0
        elif cmd == "RESUME":
            state.status = "RUNNING"
            state.active_workers_count = 1
        elif cmd == "STOP":
            state.status = "STOPPED"
            state.active_workers_count = 0

        state.updated_at = utcnow()
        db.commit()
        db.refresh(state)
        return state

    def process_chat_command(
        self,
        raw_text: str,
        user: Optional[User],
        db: Session,
    ) -> Dict[str, Any]:
        """
        Parses and handles conversational commands in natural language:
        - 'START' / 'START ALL'
        - 'PAUSE' / 'HOLD'
        - 'RESUME' / 'CONTINUE'
        - 'STOP' / 'TERMINATE'
        - 'STATUS' / 'REPORT'
        - 'ROTATE' / 'ROTATE ACCOUNT'
        - 'TASKS' / 'QUEUE'
        """
        normalized = raw_text.strip().upper()

        if any(keyword in normalized for keyword in ("START", "RUN", "BEGIN")):
            state = self.execute_command("START", user=user, db=db, message=f"Chat command: {raw_text}")
            return {
                "command": "START",
                "system_status": state.status,
                "message": "Autonomous AI Worker platform is now RUNNING. Tasks will be continuously scheduled under the 50% credit ceiling.",
                "timestamp": utcnow(),
                "details": self.get_telemetry_summary(db),
            }

        if any(keyword in normalized for keyword in ("PAUSE", "HOLD", "WAIT")):
            state = self.execute_command("PAUSE", user=user, db=db, message=f"Chat command: {raw_text}")
            return {
                "command": "PAUSE",
                "system_status": state.status,
                "message": "System PAUSED. Current tasks will hold gracefully at safe checkpoints.",
                "timestamp": utcnow(),
                "details": self.get_telemetry_summary(db),
            }

        if any(keyword in normalized for keyword in ("RESUME", "CONTINUE", "UNPAUSE")):
            state = self.execute_command("RESUME", user=user, db=db, message=f"Chat command: {raw_text}")
            return {
                "command": "RESUME",
                "system_status": state.status,
                "message": "System RESUMED. Background workers will proceed with priority scheduling.",
                "timestamp": utcnow(),
                "details": self.get_telemetry_summary(db),
            }

        if any(keyword in normalized for keyword in ("STOP", "HALT", "TERMINATE")):
            state = self.execute_command("STOP", user=user, db=db, message=f"Chat command: {raw_text}")
            return {
                "command": "STOP",
                "system_status": state.status,
                "message": "System STOPPED. All autonomous dispatching has halted.",
                "timestamp": utcnow(),
                "details": self.get_telemetry_summary(db),
            }

        if any(keyword in normalized for keyword in ("STATUS", "HEALTH", "INFO", "TELEMETRY")):
            state = self.get_or_create_state(db)
            telemetry = self.get_telemetry_summary(db)
            return {
                "command": "STATUS",
                "system_status": state.status,
                "message": f"System status: {state.status}. {telemetry['total_tasks_queued']} queued, {telemetry['total_tasks_in_progress']} active, {telemetry['eligible_accounts_count']} eligible accounts.",
                "timestamp": utcnow(),
                "details": telemetry,
            }

        if any(keyword in normalized for keyword in ("ROTATE", "SWITCH ACCOUNT")):
            # Evaluate all account ceilings and rotate
            budgets = self.scheduler.list_account_budgets(db)
            eligible_names = [b["account_name"] for b in budgets if b["is_eligible"]]
            return {
                "command": "ROTATE",
                "system_status": self.get_or_create_state(db).status,
                "message": f"Multi-account scheduler refreshed. Eligible accounts for dispatch: {', '.join(eligible_names) if eligible_names else 'None (50% ceiling reached or sessions invalid)'}.",
                "timestamp": utcnow(),
                "details": {"eligible_accounts": eligible_names},
            }

        if any(keyword in normalized for keyword in ("TASKS", "QUEUE", "WORK")):
            recent_tasks = (
                db.query(AutonomousTask)
                .order_by(AutonomousTask.created_at.desc())
                .limit(10)
                .all()
            )
            return {
                "command": "TASKS",
                "system_status": self.get_or_create_state(db).status,
                "message": f"Found {len(recent_tasks)} recent tasks in pipeline.",
                "timestamp": utcnow(),
                "details": {
                    "tasks": [
                        {
                            "id": t.task_identifier,
                            "title": t.title,
                            "work_type": t.work_type,
                            "status": t.status,
                            "priority": t.priority,
                            "assigned_account": t.assigned_account.account_name if t.assigned_account else "Unassigned",
                        }
                        for t in recent_tasks
                    ]
                },
            }

        # Fallback / help message
        return {
            "command": "UNKNOWN",
            "system_status": self.get_or_create_state(db).status,
            "message": f"Unrecognized command '{raw_text}'. Available commands: START, PAUSE, RESUME, STOP, STATUS, ROTATE, TASKS.",
            "timestamp": utcnow(),
            "details": None,
        }

    def get_telemetry_summary(self, db: Session) -> Dict[str, Any]:
        queued_count = db.query(func.count(AutonomousTask.id)).filter(AutonomousTask.status == "QUEUED").scalar() or 0
        in_progress_count = db.query(func.count(AutonomousTask.id)).filter(AutonomousTask.status.in_(["IN_PROGRESS", "CHECKPOINT"])).scalar() or 0
        completed_count = db.query(func.count(AutonomousTask.id)).filter(AutonomousTask.status == "COMPLETED").scalar() or 0
        failed_count = db.query(func.count(AutonomousTask.id)).filter(AutonomousTask.status == "FAILED").scalar() or 0

        # Eligible accounts
        all_budgets = self.scheduler.list_account_budgets(db)
        eligible_count = sum(1 for b in all_budgets if b["is_eligible"])

        return {
            "total_tasks_queued": queued_count,
            "total_tasks_in_progress": in_progress_count,
            "total_tasks_completed": completed_count,
            "total_tasks_failed": failed_count,
            "eligible_accounts_count": eligible_count,
        }

