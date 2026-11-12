from abc import ABC, abstractmethod
from typing import Dict, Any, Optional


class EmergentOAuthInterface(ABC):
    """
    Abstract interface for Emergent AI OAuth2 flow.
    Follows official OAuth 2.0 Authorization Code Grant specification.
    No undocumented or fabricated endpoints.
    """

    @abstractmethod
    def generate_authorization_url(self, state: str, redirect_uri: str) -> str:
        """Generate the OAuth2 redirect URL for user authentication."""
        pass

    @abstractmethod
    def exchange_code_for_tokens(self, code: str, redirect_uri: str) -> Dict[str, Any]:
        """Exchange the authorization code for access and refresh tokens."""
        pass

    @abstractmethod
    def refresh_access_token(self, refresh_token: str) -> Dict[str, Any]:
        """Obtain a new access token using a refresh token."""
        pass


class EmergentOAuthService(EmergentOAuthInterface):
    def __init__(self, client_id: str = "", client_secret: str = "", base_url: str = ""):
        self.client_id = client_id
        self.client_secret = client_secret
        self.base_url = base_url.rstrip("/")

    def generate_authorization_url(self, state: str, redirect_uri: str) -> str:
        # Standard RFC 6749 OAuth 2.0 authorization endpoint structure
        return (
            f"{self.base_url}/oauth/authorize?"
            f"response_type=code&client_id={self.client_id}&"
            f"redirect_uri={redirect_uri}&state={state}&scope=openid%20profile%20builds"
        )

    def exchange_code_for_tokens(self, code: str, redirect_uri: str) -> Dict[str, Any]:
        # Clean stub pending production OAuth credentials verification
        return {
            "status": "pending_configuration",
            "message": "Emergent OAuth credentials not yet configured for production environment.",
            "access_token": None,
            "refresh_token": None,
            "expires_in": 0,
        }

    def refresh_access_token(self, refresh_token: str) -> Dict[str, Any]:
        return {
            "status": "pending_configuration",
            "message": "Emergent OAuth refresh requires configured production client credentials.",
            "access_token": None,
        }
