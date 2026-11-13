from typing import Dict, Any
from fastapi import APIRouter, Depends
from app.models.user import User
from app.config import settings
from app.dependencies import require_role

router = APIRouter()


@router.get("")
def get_system_settings(
    current_user: User = Depends(require_role(["ADMIN"])),
) -> Dict[str, Any]:
    return {
        "project_name": settings.PROJECT_NAME,
        "api_version": "v1",
        "email_api_base_url": settings.EMAIL_API_BASE_URL,
        "email_api_security_status": "Strict / Unverified (Pending Admin API Authorization)",
        "emergent_api_base_url": settings.EMERGENT_API_BASE_URL,
        "emergent_auth_mode": "OAuth 2.0 / MCP Protocol (Credentials Staged)",
        "database_backend": "PostgreSQL Ready (Configured SQLite Active for Dev)",
        "credit_tracking_mode": "Manual Entry & CSV Import (Safe Sync Architecture)",
        "token_expiration_minutes": settings.ACCESS_TOKEN_EXPIRE_MINUTES,
        "artifact_retention_policy": "Strict 6-Hour Auto-Purge (Videos & Screenshots)",
    }


@router.post("/purge-expired-artifacts")
def purge_expired_artifacts_endpoint(
    current_user: User = Depends(require_role(["ADMIN"])),
) -> Dict[str, Any]:
    """Manually triggers the 6-hour artifact retention purge."""
    from app.services.storage_lifecycle import cleanup_expired_artifacts
    stats = cleanup_expired_artifacts()
    return {
        "status": "SUCCESS",
        "message": f"Artifact retention purge completed. Freed {stats['freed_bytes']} bytes.",
        "stats": stats,
    }
