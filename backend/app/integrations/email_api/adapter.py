import uuid
from abc import ABC, abstractmethod
from typing import Dict, Any, Optional
from app.config import settings


class EmailApiAdapterInterface(ABC):
    """
    Abstract adapter for interacting with email management APIs.
    Enforces secure request correlation and verification checks.
    """

    @abstractmethod
    def create_command(self, mailbox: str, command_type: str, parameters: Dict[str, Any]) -> str:
        """Create a command in the email API and return a correlation ID."""
        pass

    @abstractmethod
    def retrieve_otp(self, correlation_id: str) -> Dict[str, Any]:
        """Query email messages for OTP code matching correlation criteria."""
        pass


class InternalMailApiAdapter(EmailApiAdapterInterface):
    """
    Adapter for the internal email management API.

    SECURITY NOTICE:
    As stated in the platform architectural specification, the current email API has
    no verified API-key authentication or established tenant authorization.
    Production live polling is disabled until authorization is verified by system administrators.
    """

    def __init__(self, base_url: Optional[str] = None):
        self.base_url = (base_url or settings.EMAIL_API_BASE_URL).rstrip("/")
        self.is_access_verified = False  # Set to True only when provider authorization is proven

    def create_command(self, mailbox: str, command_type: str, parameters: Dict[str, Any]) -> str:
        """
        Creates a correlation ID for tracking the OTP command.
        """
        correlation_id = f"cmd_{uuid.uuid4().hex[:16]}"
        return correlation_id

    def retrieve_otp(self, correlation_id: str) -> Dict[str, Any]:
        """
        Retrieves OTP for the correlated command.
        Refuses execution if verified_access is not active.
        """
        if not self.is_access_verified:
            return {
                "status": "blocked_unverified",
                "correlation_id": correlation_id,
                "error": "Live OTP retrieval is suspended: Email API authorization and access controls must be verified by admin before production activation.",
                "otp_found": False,
            }

        # Staged retrieval interface for verified environments
        return {
            "status": "pending",
            "correlation_id": correlation_id,
            "message": "Waiting for inbound verification message.",
            "otp_found": False,
        }
