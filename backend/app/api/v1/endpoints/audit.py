from typing import List, Optional
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.user import User
from app.models.audit import AuditLog
from app.schemas.audit import AuditLogResponse
from app.dependencies import require_role

router = APIRouter()


@router.get("", response_model=List[AuditLogResponse])
def list_audit_logs(
    limit: int = 100,
    current_user: User = Depends(require_role(["ADMIN"])),
    db: Session = Depends(get_db),
):
    return db.query(AuditLog).order_by(AuditLog.created_at.desc()).limit(limit).all()
