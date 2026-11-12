"""
Emergent Execution Adapter Interface
Phase 4 Implementation for Emergent Central Hub

Defines standard provider execution contracts.
Supports pluggable mock simulation and certified real integrations.
"""
from abc import ABC, abstractmethod
from typing import Dict, Any, Optional
from sqlalchemy.orm import Session

from app.models.account import EmergentAccount
from app.models.project import Project
from app.models.job import BuildJob
from app.models.user import User


class BaseExecutionAdapter(ABC):
    @property
    @abstractmethod
    def adapter_name(self) -> str:
        """Name of the adapter (e.g. MOCK_EMERGENT, REAL_EMERGENT)."""
        pass

    @property
    @abstractmethod
    def is_mock(self) -> bool:
        """Whether this adapter provides simulated/mock execution."""
        pass

    @abstractmethod
    def validate_account_connection(
        self,
        account: EmergentAccount,
        user: User,
        db: Session,
    ) -> bool:
        """
        Validates account health, connectivity, and user execution permissions
        before dispatching a build.
        """
        pass

    @abstractmethod
    def prepare_execution_request(
        self,
        job: BuildJob,
        project: Project,
        account: EmergentAccount,
    ) -> Dict[str, Any]:
        """Prepares the payload and parameters for the build execution request."""
        pass

    @abstractmethod
    def submit_build(
        self,
        job: BuildJob,
        account: EmergentAccount,
        prepared_payload: Dict[str, Any],
    ) -> Dict[str, Any]:
        """
        Submits the build request to the provider interface.
        Returns execution response metadata.
        """
        pass

    @abstractmethod
    def poll_execution_status(
        self,
        job: BuildJob,
        account: EmergentAccount,
    ) -> Dict[str, Any]:
        """
        Queries provider for status, progress, token/credit consumption,
        and generated artifacts.
        """
        pass

    @abstractmethod
    def cancel_build(
        self,
        job: BuildJob,
        account: EmergentAccount,
    ) -> bool:
        """Requests cancellation of an ongoing build job from the provider."""
        pass

