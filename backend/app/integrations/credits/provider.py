from abc import ABC, abstractmethod
from decimal import Decimal
from typing import Dict, Any, Optional


class CreditProviderInterface(ABC):
    """
    Abstract credit provider for tracking and synchronizing balance states.
    Allows manual entry, CSV bulk imports, and future automated API sync.
    """

    @abstractmethod
    def fetch_balance(self, account_identifier: str) -> Optional[Decimal]:
        """Fetch current balance from external system if supported."""
        pass

    @abstractmethod
    def record_usage(self, account_identifier: str, amount: Decimal, job_id: Optional[int] = None) -> Dict[str, Any]:
        """Record credit consumption event."""
        pass


class ManualCreditProvider(CreditProviderInterface):
    """
    Default provider for manual credit tracking and administrative audits.
    """

    def fetch_balance(self, account_identifier: str) -> Optional[Decimal]:
        # Manual provider does not pull live balances automatically
        return None

    def record_usage(self, account_identifier: str, amount: Decimal, job_id: Optional[int] = None) -> Dict[str, Any]:
        return {
            "account_identifier": account_identifier,
            "amount": amount,
            "job_id": job_id,
            "status": "recorded",
            "source": "manual",
        }
