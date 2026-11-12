"""
Autonomous Brain and Task Planner Service
Phase 5A Implementation for Emergent Central Hub

Responsibilities:
1. Read administrator-defined project instructions.
2. Understand Video Creation and Website/App Development objectives.
3. Convert instructions into structured plans.
4. Generate actionable tasks with clear acceptance criteria.
5. Accept manually created tasks and imported task lists.
6. Prioritize tasks and assign initial priorities.
7. Track dependencies and detect blocked tasks.
8. Detect completed, failed, and blocked tasks.
9. Generate subsequent tasks only when project objective still requires work.
10. Prevent duplicate or meaningless task generation (deduplication & max_tasks bounds).
"""
import hashlib
import json
import logging
from datetime import datetime, timezone
from decimal import Decimal
from typing import Any, Dict, List, Optional, Tuple
from sqlalchemy.orm import Session
from sqlalchemy import func

from app.models.project import Project
from app.models.account import EmergentAccount
from app.models.autonomous import (
    AutonomousInstruction,
    AutonomousTask,
    AutonomousTaskLog,
)
from app.schemas.autonomous import (
    AutonomousInstructionCreate,
    AutonomousTaskCreate,
    AutonomousTaskImportRequest,
)

logger = logging.getLogger("emergent.autonomous.brain")


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class AutonomousBrainService:
    """
    Intelligent planning engine for Video and Website/App project pipelines.
    Enforces goal-oriented task bounding and dependency management.
    """

    def create_instruction(
        self,
        payload: AutonomousInstructionCreate,
        user_id: Optional[int],
        db: Session,
    ) -> AutonomousInstruction:
        instruction = AutonomousInstruction(
            project_id=payload.project_id,
            title=payload.title,
            work_type=payload.work_type,
            objective=payload.objective,
            system_prompt=payload.system_prompt,
            parameters_json=json.dumps(payload.parameters or {}),
            max_tasks=payload.max_tasks,
            is_active=True,
            created_by_user_id=user_id,
            created_at=utcnow(),
            updated_at=utcnow(),
        )
        db.add(instruction)
        db.commit()
        db.refresh(instruction)
        return instruction

    def generate_plan_and_tasks(
        self,
        instruction_id: int,
        db: Session,
    ) -> List[AutonomousTask]:
        """
        Decomposes instruction objective into actionable tasks with strict acceptance criteria
        and bounded task count.
        """
        instruction = db.query(AutonomousInstruction).filter(AutonomousInstruction.id == instruction_id).first()
        if not instruction:
            raise ValueError(f"Instruction {instruction_id} not found.")

        # Check existing tasks count to prevent exceeding max_tasks
        existing_tasks = db.query(AutonomousTask).filter(AutonomousTask.instruction_id == instruction_id).all()
        if len(existing_tasks) >= instruction.max_tasks:
            logger.info(f"Instruction {instruction_id} already has {len(existing_tasks)} tasks (max: {instruction.max_tasks}). Skipping.")
            return existing_tasks

        generated_tasks: List[AutonomousTask] = []
        created_identifiers: List[str] = [t.task_identifier for t in existing_tasks]

        if instruction.work_type == "VIDEO_CREATION":
            task_specs = self._plan_video_creation_pipeline(instruction)
        else:
            task_specs = self._plan_webapp_development_pipeline(instruction)

        # Generate each task within bounds
        for spec in task_specs:
            if len(existing_tasks) + len(generated_tasks) >= instruction.max_tasks:
                break

            # Deduplication check
            task_hash = hashlib.sha256(f"{instruction_id}:{spec['title']}:{spec['description']}".encode()).hexdigest()[:8]
            task_id_str = f"TASK-{instruction.work_type[:3]}-{instruction.id}-{task_hash}"

            if task_id_str in created_identifiers:
                continue

            # Determine dependencies (previous task in chain is prerequisite)
            deps = []
            if generated_tasks:
                deps.append(generated_tasks[-1].task_identifier)
            elif existing_tasks:
                deps.append(existing_tasks[-1].task_identifier)

            task = AutonomousTask(
                task_identifier=task_id_str,
                instruction_id=instruction.id,
                project_id=instruction.project_id,
                work_type=instruction.work_type,
                source="AI_GENERATED",
                title=spec["title"],
                description=spec["description"],
                expected_result=spec["expected_result"],
                acceptance_criteria=json.dumps(spec["acceptance_criteria"]),
                priority=spec.get("priority", "MEDIUM"),
                estimated_credit_cost=Decimal(str(spec.get("estimated_cost", "0.2500"))),
                actual_credit_cost=Decimal("0.0000"),
                status="PLANNED",
                dependencies=json.dumps(deps) if deps else None,
                retry_count=0,
                max_retries=3,
                retry_policy=json.dumps({"backoff_factor": 2.0, "max_interval": 300}),
                idempotency_key=f"idemp-{task_id_str}",
                execution_adapter="MOCK_VIDEO_ADAPTER" if instruction.work_type == "VIDEO_CREATION" else "MOCK_WEB_ADAPTER",
                is_mock=True,
                checkpoints=json.dumps([]),
                created_at=utcnow(),
                updated_at=utcnow(),
            )
            db.add(task)
            generated_tasks.append(task)
            created_identifiers.append(task_id_str)

        db.commit()
        for t in generated_tasks:
            db.refresh(t)

        logger.info(f"Generated {len(generated_tasks)} bounded tasks for instruction {instruction_id}.")
        return existing_tasks + generated_tasks

    def _plan_video_creation_pipeline(self, instruction: AutonomousInstruction) -> List[Dict[str, Any]]:
        """Video production pipeline breakdown."""
        return [
            {
                "title": f"Video Script & Storyboard: {instruction.title}",
                "description": f"Write engaging script and visual storyboard for video objective: {instruction.objective}",
                "expected_result": "Structured 3-scene video script with pacing, scene breakdown, and visual prompts.",
                "acceptance_criteria": [
                    "Script includes hook, core message, and call-to-action",
                    "Pacing matches requested duration",
                    "Visual descriptions defined for all scenes",
                ],
                "priority": "HIGH",
                "estimated_cost": "0.1500",
            },
            {
                "title": f"Voiceover & Audio Design: {instruction.title}",
                "description": f"Synthesize voiceover narration and audio cues for: {instruction.title}",
                "expected_result": "Synchronized audio voice track at 48kHz with clean vocal clarity.",
                "acceptance_criteria": [
                    "Voice narration synchronized to scene durations",
                    "Zero audio clipping or artifacts",
                ],
                "priority": "MEDIUM",
                "estimated_cost": "0.1500",
            },
            {
                "title": f"Video Render & Assembly: {instruction.title}",
                "description": f"Render composite video frames and assemble final output for: {instruction.title}",
                "expected_result": "1080p MP4 master video artifact with synchronized video and audio.",
                "acceptance_criteria": [
                    "Resolution 1920x1080 at 30fps",
                    "Valid MP4 container",
                    "Artifact generated at verified storage path",
                ],
                "priority": "HIGH",
                "estimated_cost": "0.2000",
            },
        ]

    def _plan_webapp_development_pipeline(self, instruction: AutonomousInstruction) -> List[Dict[str, Any]]:
        """Website / App development pipeline breakdown."""
        return [
            {
                "title": f"App Scaffolding & Architecture: {instruction.title}",
                "description": f"Design architecture, route schemas, and component structure for: {instruction.objective}",
                "expected_result": "Complete directory scaffolding, dependency manifest, and API schema contract.",
                "acceptance_criteria": [
                    "TypeScript / Python schema definitions",
                    "Clean modular directory layout",
                    "API contracts specified with input validation",
                ],
                "priority": "HIGH",
                "estimated_cost": "0.1500",
            },
            {
                "title": f"Feature Implementation & Codegen: {instruction.title}",
                "description": f"Generate full application code and UI components satisfying: {instruction.objective}",
                "expected_result": "Clean functional source code with complete UI/backend implementation.",
                "acceptance_criteria": [
                    "Zero syntax errors",
                    "Clean typing and strict lint passing",
                    "All core functional endpoints implemented",
                ],
                "priority": "HIGH",
                "estimated_cost": "0.2000",
            },
            {
                "title": f"Automated Testing & Build Verification: {instruction.title}",
                "description": f"Execute test suites and verify build artifacts for: {instruction.title}",
                "expected_result": "100% test pass rate with production build artifact generated.",
                "acceptance_criteria": [
                    "Automated unit and integration tests passing",
                    "Production bundle compiles with zero errors",
                    "Deployment checks verified",
                ],
                "priority": "CRITICAL",
                "estimated_cost": "0.1500",
            },
        ]

    def create_manual_task(
        self,
        payload: AutonomousTaskCreate,
        db: Session,
    ) -> AutonomousTask:
        """Creates a single manually defined task."""
        task_hash = hashlib.sha256(f"manual:{payload.title}:{utcnow().isoformat()}".encode()).hexdigest()[:8]
        task_id_str = f"TASK-MAN-{payload.work_type[:3]}-{task_hash}"

        task = AutonomousTask(
            task_identifier=task_id_str,
            instruction_id=payload.instruction_id,
            project_id=payload.project_id,
            work_type=payload.work_type,
            source="MANUAL",
            title=payload.title,
            description=payload.description,
            expected_result=payload.expected_result,
            acceptance_criteria=json.dumps(payload.acceptance_criteria or []),
            assigned_account_id=payload.assigned_account_id,
            priority=payload.priority,
            estimated_credit_cost=payload.estimated_credit_cost,
            actual_credit_cost=Decimal("0.0000"),
            status="PLANNED",
            dependencies=json.dumps(payload.dependencies or []),
            retry_count=0,
            max_retries=payload.max_retries,
            idempotency_key=f"idemp-{task_id_str}",
            execution_adapter="MOCK_VIDEO_ADAPTER" if payload.work_type == "VIDEO_CREATION" else "MOCK_WEB_ADAPTER",
            is_mock=True,
            checkpoints=json.dumps([]),
            created_at=utcnow(),
            updated_at=utcnow(),
        )
        db.add(task)
        db.commit()
        db.refresh(task)
        return task

    def import_tasks_bulk(
        self,
        payload: AutonomousTaskImportRequest,
        db: Session,
    ) -> List[AutonomousTask]:
        """Bulk imports task lists from external queues/JSON."""
        imported_tasks = []
        for item in payload.tasks:
            task_hash = hashlib.sha256(f"import:{item.title}:{utcnow().isoformat()}".encode()).hexdigest()[:8]
            task_id_str = f"TASK-IMP-{item.work_type[:3]}-{task_hash}"

            task = AutonomousTask(
                task_identifier=task_id_str,
                instruction_id=payload.instruction_id,
                project_id=payload.project_id,
                work_type=item.work_type,
                source="IMPORTED",
                title=item.title,
                description=item.description,
                expected_result=item.expected_result,
                acceptance_criteria=json.dumps(item.acceptance_criteria or []),
                priority=item.priority or "MEDIUM",
                estimated_credit_cost=item.estimated_credit_cost or Decimal("0.0000"),
                actual_credit_cost=Decimal("0.0000"),
                status="PLANNED",
                dependencies=json.dumps(item.dependencies or []),
                retry_count=0,
                max_retries=3,
                idempotency_key=f"idemp-{task_id_str}",
                execution_adapter="MOCK_VIDEO_ADAPTER" if item.work_type == "VIDEO_CREATION" else "MOCK_WEB_ADAPTER",
                is_mock=True,
                checkpoints=json.dumps([]),
                created_at=utcnow(),
                updated_at=utcnow(),
            )
            db.add(task)
            imported_tasks.append(task)

        db.commit()
        for t in imported_tasks:
            db.refresh(t)
        return imported_tasks

    def check_task_dependencies(
        self,
        task: AutonomousTask,
        db: Session,
    ) -> Tuple[bool, Optional[str]]:
        """
        Evaluates task dependencies.
        Returns (is_ready, blocking_task_identifier).
        If any prerequisite task is not COMPLETED, the task is considered BLOCKED.
        """
        if not task.dependencies:
            return True, None

        try:
            dep_ids = json.loads(task.dependencies)
        except Exception:
            dep_ids = []

        if not dep_ids:
            return True, None

        for dep_id in dep_ids:
            parent = db.query(AutonomousTask).filter(AutonomousTask.task_identifier == dep_id).first()
            if not parent or parent.status != "COMPLETED":
                return False, dep_id

        return True, None

