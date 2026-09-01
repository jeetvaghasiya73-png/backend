from datetime import datetime
from typing import Optional
from pydantic import BaseModel, ConfigDict, field_validator

class UserBase(BaseModel):
    username: str

# Used ONLY for login — minimal schema, no extra fields
class LoginRequest(BaseModel):
    username: str
    password: str

# Used for creating new admin users via the admin panel
class UserCreateAdmin(BaseModel):
    username: str
    password: str
    is_superadmin: bool = False

    @field_validator("username")
    @classmethod
    def username_must_be_valid(cls, v: str) -> str:
        v = v.strip()
        if len(v) < 3:
            raise ValueError("Username must be at least 3 characters")
        if len(v) > 50:
            raise ValueError("Username must be at most 50 characters")
        return v

    @field_validator("password")
    @classmethod
    def password_must_be_strong(cls, v: str) -> str:
        if len(v) < 8:
            raise ValueError("Password must be at least 8 characters")
        return v

# Legacy schema kept for backward compat (OAuth2 form login)
class UserCreate(UserBase):
    password: str

class UserUpdate(BaseModel):
    username: Optional[str] = None
    password: Optional[str] = None
    is_active: Optional[bool] = None
    is_admin: Optional[bool] = None
    is_superadmin: Optional[bool] = None

class UserOut(UserBase):
    id: int
    is_active: bool
    is_admin: bool
    is_superadmin: bool
    created_by_id: Optional[int] = None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)

class Token(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"

class TokenPayload(BaseModel):
    sub: Optional[str] = None
    exp: Optional[int] = None
    type: Optional[str] = None
