from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.user import User
from app.schemas.auth import LoginRequest, Token
from app.schemas.user import UserResponse
from app.core.security import verify_password, create_access_token
from app.config import settings
from app.dependencies import get_current_user, record_audit

router = APIRouter()


@router.post("/login", response_model=Token)
def login(request: Request, payload: LoginRequest, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.email == payload.email.lower()).first()
    if not user or not verify_password(payload.password, user.hashed_password):
        record_audit(
            db=db,
            action="login_failed",
            resource_type="auth",
            resource_id=payload.email,
            ip_address=request.client.host if request.client else None,
            details="Invalid login credentials supplied",
        )
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="User account is deactivated.",
        )

    token_data = {
        "sub": str(user.id),
        "email": user.email,
        "role": user.role.name if user.role else "MEMBER",
    }
    access_token = create_access_token(token_data)

    record_audit(
        db=db,
        action="login_success",
        resource_type="auth",
        resource_id=str(user.id),
        user_id=user.id,
        ip_address=request.client.host if request.client else None,
        details=f"User {user.email} logged in successfully.",
    )

    return Token(
        access_token=access_token,
        token_type="bearer",
        expires_in=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
        role=user.role.name if user.role else "MEMBER",
        user_id=user.id,
        full_name=user.full_name,
        email=user.email,
    )


@router.get("/me", response_model=UserResponse)
def get_current_user_profile(current_user: User = Depends(get_current_user)):
    return current_user
