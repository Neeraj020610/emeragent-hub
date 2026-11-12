from fastapi import APIRouter
from app.api.v1.endpoints import (
    auth,
    users,
    accounts,
    credits,
    jobs,
    projects,
    otp,
    reports,
    audit,
    notifications,
    settings,
    universal_keys,
    sessions,
    autonomous,
    agent_chat,
)

api_router = APIRouter()

api_router.include_router(auth.router, prefix="/auth", tags=["auth"])
api_router.include_router(users.router, prefix="/users", tags=["users"])
api_router.include_router(accounts.router, prefix="/accounts", tags=["accounts"])
api_router.include_router(credits.router, prefix="/credits", tags=["credits"])
api_router.include_router(jobs.router, prefix="/jobs", tags=["jobs"])
api_router.include_router(jobs.router, prefix="/builds", tags=["builds"])
api_router.include_router(projects.router, prefix="/projects", tags=["projects"])
api_router.include_router(otp.router, prefix="/otp", tags=["otp"])
api_router.include_router(reports.router, prefix="/reports", tags=["reports"])
api_router.include_router(audit.router, prefix="/audit", tags=["audit"])
api_router.include_router(notifications.router, prefix="/notifications", tags=["notifications"])
api_router.include_router(settings.router, prefix="/settings", tags=["settings"])
api_router.include_router(universal_keys.router, prefix="/universal-keys", tags=["universal-keys"])
api_router.include_router(universal_keys.router, prefix="/keys", tags=["keys"])
api_router.include_router(sessions.router, prefix="/sessions", tags=["sessions"])
api_router.include_router(autonomous.router, prefix="/autonomous", tags=["autonomous"])
api_router.include_router(agent_chat.router, prefix="/agent-chat", tags=["agent-chat"])
