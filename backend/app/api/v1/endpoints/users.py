from typing import List
from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.user import User, Role
from app.schemas.user import UserCreate, UserUpdate, UserResponse, RoleResponse
from app.core.security import hash_password
from app.dependencies import get_current_user, require_role, record_audit

router = APIRouter()


@router.get("/roles", response_model=List[RoleResponse])
def list_roles(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    return db.query(Role).all()


@router.get("", response_model=List[UserResponse])
def list_users(
    current_user: User = Depends(require_role(["ADMIN", "MANAGER"])),
    db: Session = Depends(get_db),
):
    return db.query(User).all()


@router.post("", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
def create_user(
    request: Request,
    payload: UserCreate,
    current_user: User = Depends(require_role(["ADMIN"])),
    db: Session = Depends(get_db),
):
    existing = db.query(User).filter(User.email == payload.email.lower()).first()
    if existing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"User with email '{payload.email}' already exists.",
        )

    role = db.query(Role).filter(Role.id == payload.role_id).first()
    if not role:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Role with ID '{payload.role_id}' does not exist.",
        )

    new_user = User(
        email=payload.email.lower(),
        hashed_password=hash_password(payload.password),
        full_name=payload.full_name,
        role_id=payload.role_id,
        is_active=payload.is_active,
        is_verified=True,
    )
    db.add(new_user)
    db.commit()
    db.refresh(new_user)

    record_audit(
        db=db,
        action="user_created",
        resource_type="user",
        resource_id=str(new_user.id),
        user_id=current_user.id,
        ip_address=request.client.host if request.client else None,
        details=f"Created user {new_user.email} with role {role.name}",
    )

    return new_user


@router.put("/{user_id}", response_model=UserResponse)
def update_user(
    user_id: int,
    request: Request,
    payload: UserUpdate,
    current_user: User = Depends(require_role(["ADMIN"])),
    db: Session = Depends(get_db),
):
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found.")

    if payload.email is not None:
        user.email = payload.email.lower()
    if payload.full_name is not None:
        user.full_name = payload.full_name
    if payload.role_id is not None:
        role = db.query(Role).filter(Role.id == payload.role_id).first()
        if not role:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Role not found.")
        user.role_id = payload.role_id
    if payload.is_active is not None:
        user.is_active = payload.is_active
    if payload.password is not None and payload.password.strip():
        user.hashed_password = hash_password(payload.password)

    db.commit()
    db.refresh(user)

    record_audit(
        db=db,
        action="user_updated",
        resource_type="user",
        resource_id=str(user.id),
        user_id=current_user.id,
        ip_address=request.client.host if request.client else None,
        details=f"Updated user ID {user.id}",
    )

    return user
