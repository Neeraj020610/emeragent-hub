"""
Real Emergent Execution Adapter
Phase 4 Implementation for Emergent Central Hub

STRICT INTEGRATION GUARD:
- Disabled by default via settings.EMERGENT_EXECUTION_ENABLED = False.
- Does not invent endpoints or scrape browser sessions.
- Throws clear NotImplementedError when invoked until official certified
  Emergent APIs are configured.
"""
import logging
from typing import Dict, Any
from sqlalchemy.orm import Session

from app.config import settings
from app.models.account import EmergentAccount
from app.models.project import Project
from app.models.job import BuildJob
from app.models.user import User
from app.services.build.adapters.base import BaseExecutionAdapter

logger = logging.getLogger("emergent.build.adapter.real")


class RealEmergentAdapter(BaseExecutionAdapter):
    @property
    def adapter_name(self) -> str:
        return "REAL_EMERGENT"

    @property
    def is_mock(self) -> bool:
        return False

    def _assert_integration_enabled(self) -> None:
        if not getattr(settings, "EMERGENT_EXECUTION_ENABLED", False):
            raise NotImplementedError(
                "Official Emergent API execution is currently disabled by system policy "
                "(EMERGENT_EXECUTION_ENABLED=False). To run builds, use the MOCK_EMERGENT adapter "
                "or enable official provider integration after certifying credentials."
            )

    def validate_account_connection(
        self,
        account: EmergentAccount,
        user: User,
        db: Session,
    ) -> bool:
        self._assert_integration_enabled()
        # Once official OAuth/MCP API is live, check token expiry and active scopes here
        return account.connection_status == "CONNECTED"

    def prepare_execution_request(
        self,
        job: BuildJob,
        project: Project,
        account: EmergentAccount,
    ) -> Dict[str, Any]:
        self._assert_integration_enabled()
        return {}

    def submit_build(
        self,
        job: BuildJob,
        account: EmergentAccount,
        prepared_payload: Dict[str, Any],
    ) -> Dict[str, Any]:
        self._assert_integration_enabled()
        return {}

    def poll_execution_status(
        self,
        job: BuildJob,
        account: EmergentAccount,
    ) -> Dict[str, Any]:
        self._assert_integration_enabled()
        return {}

    def cancel_build(
        self,
        job: BuildJob,
        account: EmergentAccount,
    ) -> bool:
        self._assert_integration_enabled()
        return False

