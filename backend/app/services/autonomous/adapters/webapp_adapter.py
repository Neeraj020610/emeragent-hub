import json
import logging
import os
from datetime import datetime, timezone
from decimal import Decimal
from typing import Any, Dict, List, Optional
from sqlalchemy.orm import Session

from app.models.account import EmergentAccount
from app.models.autonomous import AutonomousTask
from app.services.autonomous.adapters.base import BaseAutonomousAdapter, StepResult
from app.services.autonomous.adapters.content_synthesizer import generate_custom_webapp_html

logger = logging.getLogger("emergent.autonomous.webapp_adapter")


class MockWebAppExecutionAdapter(BaseAutonomousAdapter):
    """
    Website & App Development Adapter.
    Executes multi-step software engineering workflows:
    1. SPECIFICATION_REVIEW
    2. SCAFFOLDING_ARCHITECTURE
    3. CODE_GENERATION
    4. AUTOMATED_TEST_RUN
    5. ACCEPTANCE_VALIDATION (with explicit deployment authorization guard)

    Clearly identifies simulated/mock execution and creates structured codebase artifact metadata.
    """

    @property
    def adapter_name(self) -> str:
        return "MOCK_WEB_ADAPTER"

    @property
    def work_type(self) -> str:
        return "WEBSITE_APP_DEV"

    @property
    def is_mock(self) -> bool:
        return True

    def validate_account_capability(self, account: EmergentAccount, db: Session) -> bool:
        if account.status != "active":
            return False
        return True

    def execute_next_step(
        self,
        task: AutonomousTask,
        account: EmergentAccount,
        current_checkpoints: List[Dict[str, Any]],
        db: Session,
    ) -> StepResult:
        completed_step_names = [cp.get("step") for cp in current_checkpoints]
        now_iso = datetime.now(timezone.utc).isoformat()

        # Step 1: Specification Review
        if "SPECIFICATION_REVIEW" not in completed_step_names:
            spec = {
                "target_type": "Full-Stack Web Application",
                "framework": "Next.js 14 + FastAPI",
                "database": "SQLite / PostgreSQL",
                "identified_routes": ["/api/v1/resource", "/dashboard"],
                "security_requirements": ["JWT Authentication", "RBAC", "Input Validation"],
            }
            return StepResult(
                success=True,
                step_name="SPECIFICATION_REVIEW",
                checkpoint_data={"step": "SPECIFICATION_REVIEW", "completed_at": now_iso, "specification": spec},
                credits_consumed=Decimal("0.0400"),
                is_completed=False,
            )

        # Step 2: Scaffolding & Architecture
        if "SCAFFOLDING_ARCHITECTURE" not in completed_step_names:
            architecture = {
                "directories_created": ["src/components", "src/hooks", "app/api", "tests/unit"],
                "schema_definitions": ["BaseModel", "UserEntity", "TransactionRecord"],
                "routing_manifest": "Verified modular hierarchy",
            }
            return StepResult(
                success=True,
                step_name="SCAFFOLDING_ARCHITECTURE",
                checkpoint_data={"step": "SCAFFOLDING_ARCHITECTURE", "completed_at": now_iso, "architecture": architecture},
                credits_consumed=Decimal("0.0600"),
                is_completed=False,
            )

        # Step 3: Code Generation
        if "CODE_GENERATION" not in completed_step_names:
            webapp_file = generate_custom_webapp_html(
                task_identifier=task.task_identifier,
                title=task.title,
                description=task.description or "",
            )
            codegen_report = {
                "files_written": 7,
                "lines_of_code": 840,
                "syntax_validation": "Clean compile, 0 syntax errors",
                "type_check": "TypeScript strict mode passed",
                "preview_file": f"storage/artifacts/webapps/{task.task_identifier}.html",
                "artifact_size_bytes": os.path.getsize(webapp_file) if os.path.exists(webapp_file) else 0,
            }
            return StepResult(
                success=True,
                step_name="CODE_GENERATION",
                checkpoint_data={"step": "CODE_GENERATION", "completed_at": now_iso, "codegen": codegen_report},
                credits_consumed=Decimal("0.1000"),
                is_completed=False,
            )

        # Step 4: Automated Test Run
        if "AUTOMATED_TEST_RUN" not in completed_step_names:
            test_results = {
                "tests_executed": 18,
                "tests_passed": 18,
                "tests_failed": 0,
                "code_coverage_pct": 94.2,
                "regressions_detected": 0,
            }
            return StepResult(
                success=True,
                step_name="AUTOMATED_TEST_RUN",
                checkpoint_data={"step": "AUTOMATED_TEST_RUN", "completed_at": now_iso, "test_results": test_results},
                credits_consumed=Decimal("0.0800"),
                is_completed=False,
            )

        # Step 5: Acceptance Validation & Deployment Check
        criteria_list = []
        if task.acceptance_criteria:
            try:
                criteria_list = json.loads(task.acceptance_criteria)
            except Exception:
                criteria_list = [task.acceptance_criteria]

        validation_report = {
            "all_criteria_satisfied": True,
            "criteria_evaluated": criteria_list,
            "build_artifact_path": f"dist/builds/{task.task_identifier}.tar.gz",
            "deployment_status": "STAGED_READY (Production deployment requires explicit administrator sign-off)",
            "adapter": self.adapter_name,
            "is_mock": self.is_mock,
        }

        return StepResult(
            success=True,
            step_name="ACCEPTANCE_VALIDATION",
            checkpoint_data={"step": "ACCEPTANCE_VALIDATION", "completed_at": now_iso, "validation": validation_report},
            credits_consumed=Decimal("0.0200"),
            result_metadata={
                "build_artifact": f"dist/builds/{task.task_identifier}.tar.gz",
                "tests_passed": 18,
                "code_coverage": "94.2%",
                "git_commit": f"git-{task.task_identifier[:8]}",
                "validation_summary": "Scaffolding, full code implementation, automated tests, and acceptance criteria validated.",
                "adapter": self.adapter_name,
                "is_mock": True,
            },
            is_completed=True,
        )

