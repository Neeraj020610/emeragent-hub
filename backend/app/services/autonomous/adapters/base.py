from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional
from decimal import Decimal
from sqlalchemy.orm import Session

from app.models.account import EmergentAccount
from app.models.autonomous import AutonomousTask


class StepResult:
    def __init__(
        self,
        success: bool,
        step_name: str,
        checkpoint_data: Dict[str, Any],
        credits_consumed: Decimal = Decimal("0.0000"),
        result_metadata: Optional[Dict[str, Any]] = None,
        error_message: Optional[str] = None,
        error_classification: Optional[str] = None,
        is_completed: bool = False,
    ):
        self.success = success
        self.step_name = step_name
        self.checkpoint_data = checkpoint_data
        self.credits_consumed = credits_consumed
        self.result_metadata = result_metadata or {}
        self.error_message = error_message
        self.error_classification = error_classification
        self.is_completed = is_completed


class BaseAutonomousAdapter(ABC):
    @property
    @abstractmethod
    def adapter_name(self) -> str:
        """Name of adapter, e.g. MOCK_VIDEO_ADAPTER, REAL_VIDEO_ADAPTER."""
        pass

    @property
    @abstractmethod
    def work_type(self) -> str:
        """VIDEO_CREATION or WEBSITE_APP_DEV."""
        pass

    @property
    @abstractmethod
    def is_mock(self) -> bool:
        """Whether this adapter runs in mock simulation mode."""
        pass

    @abstractmethod
    def validate_account_capability(self, account: EmergentAccount, db: Session) -> bool:
        """Verifies if the assigned account supports the required capability."""
        pass

    @abstractmethod
    def execute_next_step(
        self,
        task: AutonomousTask,
        account: EmergentAccount,
        current_checkpoints: List[Dict[str, Any]],
        db: Session,
    ) -> StepResult:
        """
        Executes the next atomic checkpoint step of the task.
        Returns StepResult with progress, checkpoints, credit consumption, and completion status.
        """
        pass

