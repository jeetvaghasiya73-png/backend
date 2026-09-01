from typing import List, Optional
from pydantic import BaseModel, ConfigDict, field_validator

class ServiceBase(BaseModel):
    title: str
    slug: str
    description: str
    icon: str
    features: List[str] = []
    active: Optional[bool] = True

    @field_validator("title")
    @classmethod
    def title_not_empty(cls, v: str) -> str:
        v = v.strip()
        if not v or len(v) < 2:
            raise ValueError("Title must be at least 2 characters")
        if len(v) > 100:
            raise ValueError("Title must be at most 100 characters")
        return v

    @field_validator("slug")
    @classmethod
    def slug_valid(cls, v: str) -> str:
        import re
        v = v.strip().lower()
        if not re.match(r"^[a-z0-9]+(?:-[a-z0-9]+)*$", v):
            raise ValueError("Slug must be lowercase alphanumeric with hyphens only")
        return v

    @field_validator("description")
    @classmethod
    def description_not_empty(cls, v: str) -> str:
        if not v or not v.strip():
            raise ValueError("Description cannot be empty")
        if len(v) > 2000:
            raise ValueError("Description must be at most 2000 characters")
        return v

    @field_validator("icon")
    @classmethod
    def icon_not_empty(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("Icon name cannot be empty")
        return v

class ServiceCreate(ServiceBase):
    pass

class ServiceUpdate(BaseModel):
    title: Optional[str] = None
    slug: Optional[str] = None
    description: Optional[str] = None
    icon: Optional[str] = None
    features: Optional[List[str]] = None
    active: Optional[bool] = None

class ServiceOut(ServiceBase):
    id: int

    model_config = ConfigDict(from_attributes=True)
