from datetime import datetime
from typing import List, Optional
from pydantic import BaseModel, EmailStr, ConfigDict, field_validator

class LeadBase(BaseModel):
    name: str
    email: EmailStr
    phone: Optional[str] = None
    company: Optional[str] = None
    services: List[str] = []
    message: Optional[str] = None

    @field_validator("name")
    @classmethod
    def name_not_empty(cls, v: str) -> str:
        v = v.strip()
        if not v or len(v) < 2:
            raise ValueError("Name must be at least 2 characters")
        if len(v) > 100:
            raise ValueError("Name must be at most 100 characters")
        return v

    @field_validator("phone")
    @classmethod
    def phone_valid(cls, v: Optional[str]) -> Optional[str]:
        if v is not None:
            import re
            v = v.strip()
            if v and not re.match(r"^[\+]?[\d\s\-\(\)]{7,20}$", v):
                raise ValueError("Invalid phone number format")
        return v

    @field_validator("message")
    @classmethod
    def message_max_length(cls, v: Optional[str]) -> Optional[str]:
        if v is not None and len(v) > 5000:
            raise ValueError("Message must be at most 5000 characters")
        return v

class LeadCreate(LeadBase):
    pass

class LeadUpdate(BaseModel):
    name: Optional[str] = None
    email: Optional[EmailStr] = None
    phone: Optional[str] = None
    company: Optional[str] = None
    services: Optional[List[str]] = None
    message: Optional[str] = None
    status: Optional[str] = None

    @field_validator("status")
    @classmethod
    def status_valid(cls, v: Optional[str]) -> Optional[str]:
        if v is not None:
            allowed = {"pending", "contacting", "qualified", "closed"}
            if v not in allowed:
                raise ValueError(f"Status must be one of: {', '.join(sorted(allowed))}")
        return v

class LeadOut(LeadBase):
    id: int
    status: str
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)
