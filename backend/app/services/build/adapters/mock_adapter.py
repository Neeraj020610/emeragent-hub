"""
Mock Emergent Execution Adapter
Phase 4 Implementation for Emergent Central Hub

CLEARLY LABELED SIMULATION:
- Disclaims all operations as synthetic mock execution.
- Emits structured metadata with is_mock=True.
- Never contacts external Emergent servers.
- Simulates build lifecycle with realistic progress and credits.
"""
import json
import logging
from typing import Dict, Any
from decimal import Decimal
from sqlalchemy.orm import Session

from app.models.account import EmergentAccount, AccountPermission, PersonalAccountConsent
from app.models.project import Project
from app.models.job import BuildJob
from app.models.user import User
from app.services.build.adapters.base import BaseExecutionAdapter

logger = logging.getLogger("emergent.build.adapter.mock")


class MockEmergentAdapter(BaseExecutionAdapter):
    @property
    def adapter_name(self) -> str:
        return "MOCK_EMERGENT"

    @property
    def is_mock(self) -> bool:
        return True

    def validate_account_connection(
        self,
        account: EmergentAccount,
        user: User,
        db: Session,
    ) -> bool:
        """
        Validates account health, ownership, and user execution permissions.
        Rejects suspended accounts or unauthorized users.
        """
        if account.status != "active":
            logger.warning(f"Account {account.account_identifier} is not active (status: {account.status})")
            return False

        # Admin can execute across all company accounts
        is_admin = user.role and user.role.name.upper() in ("ADMIN", "SUPERADMIN")
        if is_admin and account.ownership_type == "COMPANY_OWNED":
            return True

        # Check personal account consent if applicable
        if account.ownership_type == "PERSONAL":
            if account.owner_user_id == user.id:
                return True
            # Check server-side PersonalAccountConsent
            consent = (
                db.query(PersonalAccountConsent)
                .filter(
                    PersonalAccountConsent.account_id == account.id,
                    PersonalAccountConsent.authorized_member_id == user.id,
                    PersonalAccountConsent.is_active == True,
                )
                .first()
            )
            if not consent or (consent.expires_at and consent.expires_at < user.created_at):
                return False
            return True

        # Company-owned account: check explicit permission
        perm = (
            db.query(AccountPermission)
            .filter(
                AccountPermission.account_id == account.id,
                AccountPermission.user_id == user.id,
            )
            .first()
        )
        if perm and perm.can_execute:
            return True

        return is_admin

    def prepare_execution_request(
        self,
        job: BuildJob,
        project: Project,
        account: EmergentAccount,
    ) -> Dict[str, Any]:
        """Prepares a mock payload for simulated execution."""
        ref_urls = []
        if job.reference_urls:
            try:
                ref_urls = json.loads(job.reference_urls) if job.reference_urls.startswith("[") else [job.reference_urls]
            except Exception:
                ref_urls = [job.reference_urls]

        return {
            "job_id": job.id,
            "project_key": project.project_key,
            "account_identifier": account.account_identifier,
            "job_type": job.job_type,
            "title": job.title,
            "priority": job.priority,
            "requirements": job.requirements,
            "reference_urls": ref_urls,
            "simulation_mode": True,
            "adapter": self.adapter_name,
            "disclaimer": "SIMULATED MOCK EXECUTION. Official Emergent execution integration is currently disabled.",
        }

    def submit_build(
        self,
        job: BuildJob,
        account: EmergentAccount,
        prepared_payload: Dict[str, Any],
    ) -> Dict[str, Any]:
        """Simulates successful submission to mock execution pipeline."""
        mock_external_id = f"mock_bld_{job.id:06d}_{job.priority.lower()}"
        logger.info(f"Submitted job #{job.id} to MockEmergentAdapter with mock ID {mock_external_id}")
        return {
            "status": "accepted",
            "external_job_id": mock_external_id,
            "adapter": self.adapter_name,
            "is_mock": True,
            "message": "Build accepted by mock execution engine.",
            "estimated_duration_seconds": 15,
        }

    def poll_execution_status(
        self,
        job: BuildJob,
        account: EmergentAccount,
    ) -> Dict[str, Any]:
        """Simulates execution completion with mock artifacts and synthetic credits."""
        return {
            "status": "COMPLETED",
            "is_mock": True,
            "adapter": self.adapter_name,
            "credits_used": Decimal("0.7500"),
            "result_summary": f"Mock build '{job.title}' completed successfully. Code generated and verified in simulation sandbox.",
            "result_metadata": json.dumps({
                "adapter": self.adapter_name,
                "is_mock": True,
                "disclaimer": "This is synthetic mock data. Real Emergent execution is disabled.",
                "artifacts": [
                    {"name": "generated_bundle.zip", "size_kb": 1420, "sha256": "mock_sha256_e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855"},
                    {"name": "build_logs.txt", "size_kb": 48, "lines": 320},
                    {"name": "test_results.json", "tests_passed": 24, "tests_failed": 0},
                ],
                "execution_metrics": {
                    "total_tokens": 12840,
                    "prompt_tokens": 3410,
                    "completion_tokens": 9430,
                    "duration_seconds": 12.4,
                },
            }),
        }

    def cancel_build(
        self,
        job: BuildJob,
        account: EmergentAccount,
    ) -> bool:
        """Simulates build cancellation."""
        logger.info(f"Cancelled mock build job #{job.id}")
        return True

