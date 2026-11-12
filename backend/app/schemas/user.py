from datetime import datetime
from typing import Optional
from pydantic import BaseModel, EmailStr


class RoleResponse(BaseModel):
    id: int
    name: str
    description: Optional[str] = None
    permissions: Optional[str] = None

    class Config:
        from_attributes = True


class UserBase(BaseModel):
    email: EmailStr
    full_name: str
    role_id: int
    is_active: bool = True


class UserCreate(UserBase):
    password: str


class UserUpdate(BaseModel):
    email: Optional[EmailStr] = None
    full_name: Optional[str] = None
    role_id: Optional[int] = None
    is_active: Optional[bool] = None
    password: Optional[str] = None


class UserResponse(BaseModel):
    id: int
    email: EmailStr
    full_name: str
    role_id: int
    is_active: bool
    is_verified: bool
    created_at: datetime
    role: Optional[RoleResponse] = None

    class Config:
        from_attributes = True
