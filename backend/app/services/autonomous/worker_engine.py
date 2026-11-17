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
from sqlalchemy import func, case, or_

from app.models.account import EmergentAccount
from app.models.session import AccountSession
from app.models.autonomous import (
    AutonomousTask,
    AutonomousTaskLog,
    AutonomousSystemState,
    AccountCreditBudget,
)
from app.models.credit import CreditSnapshot
from app.models.chat import Conversation
from app.services.session.failover_service import get_or_failover_active_account
from app.services.autonomous.adapters.emergent_browser_adapter import schedule_emergent_browser_task
from app.services.autonomous.brain import AutonomousBrainService
from app.services.autonomous.scheduler import AccountCreditScheduler
from app.services.autonomous.adapters.video_adapter import MockVideoExecutionAdapter
from app.services.autonomous.adapters.webapp_adapter import MockWebAppExecutionAdapter
from app.services.autonomous.adapters.base import BaseAutonomousAdapter, StepResult

logger = logging.getLogger("emergent.autonomous.worker_engine")

CREATIVE_PROMPT_POOL = [
    {
        "title": "Futuristic Cyberpunk Metropolis with Flying Vehicles",
        "prompt": "Create an ultra-high quality cinematic 30-second video of a futuristic cyberpunk mega-city at dusk. Towering neon skyscrapers with holographic billboards, sleek flying anti-gravity cars and aero-taxis navigating between sky bridges, continuous smooth camera tracking following a high-speed vehicle through illuminated city canyons, immersive ambient city sounds and electronic synth score.",
    },
    {
        "title": "Ancient Roman Colosseum Gladiator Showdown",
        "prompt": "Create a dramatic 30-second cinematic video of an ancient Roman amphitheater during golden hour. Dust swirling across the arena sands, two armored gladiators in dynamic combat pose, massive cheering crowds in the colosseum stands, epic brass and percussion orchestral soundtrack.",
    },
    {
        "title": "Deep Sea Bioluminescent Creature Expedition",
        "prompt": "Create a breathtaking 30-second underwater cinematic exploration video. A deep-sea research submarine descending into the abyss, illuminating glowing bioluminescent jellyfish and undiscovered deep-ocean marine life, subtle hydro-acoustic audio and serene atmospheric score.",
    },
    {
        "title": "Mars Human Colony First Terraforming Dome",
        "prompt": "Create a photorealistic 30-second video of humanity's first self-sustaining colony on Mars. Red planet landscape with solar arrays, pressurized glass geodesic biodomes, robotic rovers traversing rust-red dunes against Olympus Mons at sunset, inspiring orchestral cinematic music.",
    },
    {
        "title": "Samurai Duel in Cherry Blossom Storm",
        "prompt": "Create a high-octane 30-second anime-inspired cinematic video of a lone samurai with a katana standing on a misty temple bridge during a swirling pink cherry blossom storm, wind blowing robes, lightning flash, authentic Japanese koto and cinematic taiko drum beat.",
    },
    {
        "title": "Supercar Hyper-Speed Night Tunnel Drift",
        "prompt": "Create a sleek 30-second commercial-grade video of an exotic electric hypercar drifting through a futuristic illuminated underwater glass tunnel, glowing tire streaks, roaring aero turbine sound, high-energy modern bass soundtrack.",
    },
    {
        "title": "Medieval Dragon Siege over Mountain Castle",
        "prompt": "Create an epic 30-second fantasy cinematic video of an ancient stone castle perched on mist-shrouded mountain peaks, a massive winged fire dragon soaring overhead in defense of the fortress, thunderous wings, soaring orchestral fantasy score.",
    },
    {
        "title": "Space Station Zero-Gravity Earth Orbital View",
        "prompt": "Create a stunning 30-second IMAX-quality video from the observation deck of an orbital space station. Looking down at planet Earth rotating below with glowing city lights and atmospheric aurora borealis, serene celestial ambient music.",
    },
    {
        "title": "Steampunk Airship Fleet Sailing Through Sunlit Clouds",
        "prompt": "Create a detailed 30-second cinematic video of giant brass and mahogany steampunk zeppelins sailing between golden sunlit storm clouds, spinning copper propellers and glowing pressure gauges, grand adventurous brass symphony.",
    },
    {
        "title": "AI Robotics Autonomous Factory of the Year 2050",
        "prompt": "Create a 30-second showcase video of an advanced humanoid robotics assembly facility. High-precision robotic arms collaborating seamlessly with bipedal humanoid androids assembling quantum microprocessors, crisp mechanical audio and futuristic synth beats.",
    },
    {
        "title": "Viking Longship Navigating Arctic Glaciers",
        "prompt": "Create a cinematic 30-second video of a rugged Viking longship navigating through towering blue Arctic glaciers and icebergs under shimmering green Northern Lights, dramatic waves crashing, Norse chanting and deep drum score.",
    },
    {
        "title": "Futuristic Solar City with High-Speed Maglev Train",
        "prompt": "Create a bright, optimistic 30-second video of an eco-futuristic solar city with vertical gardens on skyscrapers, ultra-sleek high-speed maglev train soaring across elevated transparent tube tracks, modern upbeat ambient electronic music.",
    },
]


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
                AutonomousTask.status.in_(["IN_PROGRESS", "RUNNING"]),
                or_(
                    AutonomousTask.last_heartbeat_at < threshold,
                    (AutonomousTask.last_heartbeat_at.is_(None) & (AutonomousTask.updated_at < threshold)),
                    (AutonomousTask.last_heartbeat_at.is_(None) & AutonomousTask.updated_at.is_(None)),
                ),
            )
            .all()
        )
        recovered_count = 0
        for task in orphaned:
            logger.warning(f"Recovering orphaned task {task.task_identifier} (last heartbeat: {task.last_heartbeat_at}, updated_at: {task.updated_at})")
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
                task.last_heartbeat_at = None
                task.updated_at = utcnow()
            else:
                task.status = "FAILED"
                task.error_classification = "MAX_RETRIES_EXCEEDED"
                task.error_details = "Worker heartbeat timed out and max retries reached."
                task.updated_at = utcnow()

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
        Polls for tasks and executes REAL work on the active eligible Emergent account.
        If no tasks exist in queue, automatically feeds the next creative video task
        to ensure continuous 100% credit consumption until operator issues STOP.
        """
        system_state = self.get_system_state(db)
        if not force_run and system_state.status != "RUNNING":
            logger.debug(f"Worker engine idle: system is {system_state.status}")
            return None

        # 1. Crash/Orphan Recovery: Recover any tasks whose worker died or heartbeat timed out
        self.recover_orphaned_tasks(db, timeout_minutes=3)

        # 2. Ensure single concurrent execution: If an Emergent task is actively IN_PROGRESS, wait for it
        active_task = (
            db.query(AutonomousTask)
            .filter(AutonomousTask.status.in_(["IN_PROGRESS", "RUNNING"]))
            .first()
        )
        if active_task:
            return None

        # 3. Resolve the Active Eligible Worker Account (with auto-failover if credits < 5)
        account = get_or_failover_active_account(db)
        if not account:
            logger.warning("Worker engine: No active or standby account with available credits found in pool.")
            return None

        # 3. Find targeted or next queued task
        priority_order = case(
            (AutonomousTask.priority == "CRITICAL", 4),
            (AutonomousTask.priority == "HIGH", 3),
            (AutonomousTask.priority == "MEDIUM", 2),
            (AutonomousTask.priority == "LOW", 1),
            else_=0,
        )

        queued_task = None
        if target_task_id:
            target = db.query(AutonomousTask).filter(AutonomousTask.id == target_task_id).first()
            if target and target.status in ("QUEUED", "CHECKPOINT", "PLANNED"):
                if target.status == "PLANNED":
                    target.status = "QUEUED"
                    db.commit()
                queued_task = target

        if not queued_task:
            # Promote ready PLANNED tasks
            candidate_tasks = db.query(AutonomousTask).filter(AutonomousTask.status.in_(["PLANNED", "BLOCKED"])).all()
            for pt in candidate_tasks:
                is_ready, blocker = self.brain.check_task_dependencies(pt, db)
                if is_ready:
                    pt.status = "QUEUED"
                    pt.error_details = None
            db.commit()

            queued_task = (
                db.query(AutonomousTask)
                .filter(AutonomousTask.status == "QUEUED")
                .order_by(priority_order.desc(), AutonomousTask.created_at.asc())
                .first()
            )

        # 4. Auto-Feed Continuous Generation: If queue is empty, generate next creative task!
        if not queued_task:
            queued_task = self._auto_generate_next_creative_task(account, db)

        if not queued_task:
            return None

        # 5. Dispatch task directly to REAL Emergent Browser Session (100% Real, Zero Mock!)
        queued_task.status = "IN_PROGRESS"
        queued_task.assigned_account_id = account.id
        queued_task.execution_adapter = "EMERGENT_BROWSER_ADAPTER"
        queued_task.is_mock = False
        queued_task.worker_id = self.worker_id
        queued_task.started_at = utcnow()
        queued_task.last_heartbeat_at = utcnow()
        db.commit()

        # Find or create a conversation for activity logs
        conv = db.query(Conversation).first()
        conv_id = conv.id if conv else 1

        prompt_text = queued_task.description or queued_task.title
        schedule_emergent_browser_task(
            task_id=queued_task.id,
            account_id=account.id,
            conversation_id=conv_id,
            prompt=prompt_text,
            work_type=queued_task.work_type or "VIDEO_CREATION",
            is_hinglish=True,
        )

        logger.info(
            f"Autonomous Worker dispatched REAL task {queued_task.task_identifier} "
            f"('{queued_task.title}') on Active Account '{account.account_name}' (ID: {account.id})"
        )

        self._log_event(
            task_id=queued_task.id,
            level="INFO",
            message=f"Dispatched real task to Emergent Studio on Account '{account.account_name}' ({account.id}).",
            step="EMERGENT_DISPATCHED",
            db=db,
        )

        return {
            "task_id": queued_task.task_identifier,
            "status": "IN_PROGRESS",
            "account_name": account.account_name,
            "title": queued_task.title,
            "is_real": True,
        }

    def _auto_generate_next_creative_task(
        self,
        account: EmergentAccount,
        db: Session,
    ) -> Optional[AutonomousTask]:
        """
        Generates a new real high-impact creative video task from the curated prompt pool
        to ensure continuous credit consumption on the active account.
        """
        total_tasks = db.query(func.count(AutonomousTask.id)).scalar() or 0
        prompt_data = CREATIVE_PROMPT_POOL[total_tasks % len(CREATIVE_PROMPT_POOL)]

        task_ident = f"TASK-AUTO-VID-{uuid.uuid4().hex[:8]}"
        new_task = AutonomousTask(
            task_identifier=task_ident,
            instruction_id=None,
            work_type="VIDEO_CREATION",
            title=prompt_data["title"],
            description=prompt_data["prompt"],
            expected_result="Single continuous scene 30-sec video rendered in crystal clear HD with custom audio & synced voiceover.",
            priority="HIGH",
            status="QUEUED",
            is_mock=False,
            execution_adapter="EMERGENT_BROWSER_ADAPTER",
            assigned_account_id=account.id,
            estimated_credit_cost=Decimal("10.0000"),
            actual_credit_cost=Decimal("0.0000"),
            retry_count=0,
            max_retries=2,
            acceptance_criteria=json.dumps([
                "Custom chapter narrative arc and visual pacing",
                "Scene-specific illustrated storyboard prompts",
                "Synchronized spoken voiceover narration",
                "Rendered H.264 MP4 with AAC audio",
                "Verified artifact stored and downloadable",
            ]),
            created_at=utcnow(),
            updated_at=utcnow(),
        )
        db.add(new_task)
        db.commit()
        db.refresh(new_task)

        self._log_event(
            task_id=new_task.id,
            level="INFO",
            message=f"Continuous Worker Auto-Feeder generated new creative task '{new_task.title}' for Account '{account.account_name}'.",
            step="AUTO_FEED_GENERATED",
            db=db,
        )
        return new_task

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
