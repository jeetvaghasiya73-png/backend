from datetime import datetime
from typing import Optional
from pydantic import BaseModel, EmailStr, ConfigDict, field_validator

class ContactBase(BaseModel):
    name: str
    email: EmailStr
    subject: Optional[str] = None
    message: str

    @field_validator("name")
    @classmethod
    def name_not_empty(cls, v: str) -> str:
        v = v.strip()
        if not v or len(v) < 2:
            raise ValueError("Name must be at least 2 characters")
        if len(v) > 100:
            raise ValueError("Name must be at most 100 characters")
        return v

    @field_validator("message")
    @classmethod
    def message_not_empty(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("Message cannot be empty")
        if len(v) > 5000:
            raise ValueError("Message must be at most 5000 characters")
        return v

    @field_validator("subject")
    @classmethod
    def subject_max_length(cls, v: Optional[str]) -> Optional[str]:
        if v is not None and len(v) > 200:
            raise ValueError("Subject must be at most 200 characters")
        return v

class ContactCreate(ContactBase):
    pass

class ContactUpdate(BaseModel):
    status: Optional[str] = None

    @field_validator("status")
    @classmethod
    def status_valid(cls, v: Optional[str]) -> Optional[str]:
        if v is not None:
            allowed = {"unread", "read", "replied"}
            if v not in allowed:
                raise ValueError(f"Status must be one of: {', '.join(sorted(allowed))}")
        return v

class ContactOut(ContactBase):
    id: int
    status: str
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)
