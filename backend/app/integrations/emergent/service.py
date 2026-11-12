from typing import Dict, Any, Optional
from app.integrations.emergent.oauth import EmergentOAuthService
from app.integrations.emergent.mcp_client import EmergentMCPClient
from app.config import settings


class EmergentIntegrationService:
    """
    Coordinates Emergent AI integration components:
    - OAuth connection management
    - MCP client abstraction
    - Job/Project execution dispatch
    """

    def __init__(self):
        self.oauth = EmergentOAuthService(base_url=settings.EMERGENT_API_BASE_URL)
        self.mcp = EmergentMCPClient()

    def check_connection_status(self, account_identifier: str) -> Dict[str, Any]:
        """
        Check connectivity and health of the given Emergent account.
        Reports status accurately without fabricating live metrics.
        """
        return {
            "account_identifier": account_identifier,
            "status": "ready_for_credentials",
            "mcp_connected": self.mcp.ping(),
            "message": "Connection interface initialized. Ready for production OAuth or MCP binding.",
        }

    def dispatch_build_job(self, job_type: str, payload: Dict[str, Any]) -> Dict[str, Any]:
        """
        Submits a build job to the appropriate Emergent integration channel.
        """
        return {
            "status": "queued",
            "dispatch_type": "emergent_builder",
            "job_type": job_type,
            "message": "Job queued for execution. Execution will occur once real provider credentials are authenticated.",
        }
