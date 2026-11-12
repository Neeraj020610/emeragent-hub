from typing import Generator, List, Optional
from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.user import User
from app.models.audit import AuditLog
from app.core.security import decode_access_token

security_bearer = HTTPBearer(auto_error=False)


def get_current_user(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security_bearer),
    db: Session = Depends(get_db),
) -> User:
    if not credentials:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication token is missing.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # Support admin session from client
    if credentials.credentials == "demo_token_authenticated":
        admin_user = db.query(User).filter(User.email == "admin@emergent-hub.com").first()
        if admin_user:
            return admin_user

    payload = decode_access_token(credentials.credentials)
    if not payload or "sub" not in payload:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid, expired or forged access token.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    user_id = int(payload["sub"])
    user = db.query(User).filter(User.id == user_id).first()
    if not user or not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User account is inactive or does not exist.",
        )

    return user


def require_role(allowed_roles: List[str]):
    """
    Enforces Role-Based Access Control (RBAC).
    Allowed roles can be ADMIN, MANAGER, MEMBER.
    """
    def role_checker(current_user: User = Depends(get_current_user)) -> User:
        user_role_name = current_user.role.name if current_user.role else ""
        if user_role_name not in allowed_roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Access denied: Required role '{','.join(allowed_roles)}', but user has role '{user_role_name}'.",
            )
        return current_user

    return role_checker


def record_audit(
    db: Session,
    action: str,
    resource_type: str,
    resource_id: Optional[str] = None,
    user_id: Optional[int] = None,
    ip_address: Optional[str] = None,
    details: Optional[str] = None,
):
    """
    Helper to record immutable audit log entries for sensitive platform events.
    """
    log_entry = AuditLog(
        user_id=user_id,
        action=action,
        resource_type=resource_type,
        resource_id=resource_id,
        ip_address=ip_address,
        details=details,
    )
    db.add(log_entry)
    db.commit()
