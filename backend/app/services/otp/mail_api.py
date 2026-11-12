"""
Email Management API Client
Phase 3 Implementation for Emergent Central Hub

Adheres strictly to the supplied email API contract:
1. GET /create-email-command.asp?emailAddress={emailAddress}&employeeName={employeeName}&commandType=Inbox
2. GET /unstop-otp.asp?fileid={fileid}&limit=1&action=unstop_otp
"""
import logging
from typing import Any, Dict, Optional
import httpx
from app.config import settings

logger = logging.getLogger("emergent.otp.mail_api")


class EmailApiClient:
    def __init__(
        self,
        base_url: Optional[str] = None,
        timeout_seconds: Optional[int] = None,
    ):
        self.base_url = (base_url or settings.EMAIL_API_BASE_URL).rstrip("/")
        self.timeout = timeout_seconds or settings.EMAIL_API_HTTP_TIMEOUT_SECONDS

    async def create_email_command(
        self,
        email_address: str,
        employee_name: str,
        command_type: str = "Inbox",
    ) -> Dict[str, Any]:
        """
        Calls GET /create-email-command.asp with:
        - emailAddress
        - employeeName
        - commandType=Inbox
        """
        url = f"{self.base_url}/create-email-command.asp"
        params = {
            "emailAddress": email_address,
            "employeeName": employee_name,
            "commandType": command_type,
        }

        # Safe redacted log message
        redacted_email = email_address[:3] + "***@" + email_address.split("@")[-1] if "@" in email_address else "***"
        logger.info(
            f"Dispatching create-email-command: url={self.base_url}/create-email-command.asp, email={redacted_email}, employee={employee_name[:2]}***"
        )

        async with httpx.AsyncClient(timeout=self.timeout) as client:
            try:
                response = await client.get(url, params=params)
                response.raise_for_status()
                return response.json()
            except httpx.HTTPStatusError as e:
                logger.error(f"HTTP status error from create-email-command: {e.response.status_code}")
                raise RuntimeError(f"Email API returned HTTP {e.response.status_code}") from e
            except httpx.RequestError as e:
                logger.error(f"Network error contacting Email API: {str(e)}")
                raise RuntimeError("Failed to connect to Email API service") from e
            except ValueError as e:
                logger.error("Failed to parse JSON response from Email API")
                raise RuntimeError("Invalid JSON received from Email API") from e

    async def retrieve_otp(
        self,
        command_id: str,
        limit: int = 1,
        action: str = "unstop_otp",
    ) -> Dict[str, Any]:
        """
        Calls GET /unstop-otp.asp with:
        - fileid
        - limit=1
        - action=unstop_otp
        """
        url = f"{self.base_url}/unstop-otp.asp"
        params = {
            "fileid": command_id,
            "limit": str(limit),
            "action": action,
        }

        logger.info(f"Querying unstop-otp: url={self.base_url}/unstop-otp.asp, fileid={command_id}")

        async with httpx.AsyncClient(timeout=self.timeout) as client:
            try:
                response = await client.get(url, params=params)
                response.raise_for_status()
                # NEVER log response text directly as it could contain raw OTP
                data = response.json()
                return data
            except httpx.HTTPStatusError as e:
                logger.error(f"HTTP status error from unstop-otp: {e.response.status_code}")
                raise RuntimeError(f"Email API returned HTTP {e.response.status_code}") from e
            except httpx.RequestError as e:
                logger.error(f"Network error querying OTP: {str(e)}")
                raise RuntimeError("Failed to connect to Email API service") from e
            except ValueError as e:
                logger.error("Failed to parse JSON response from unstop-otp")
                raise RuntimeError("Invalid JSON received from Email API") from e

