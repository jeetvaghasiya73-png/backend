from datetime import datetime
from typing import Optional
from pydantic import BaseModel, ConfigDict, field_validator

class BlogBase(BaseModel):
    title: str
    slug: str
    content: str
    summary: str
    cover_image: Optional[str] = None
    published: Optional[bool] = False
    author: Optional[str] = "Nexora Team"
    seo_title: Optional[str] = None
    seo_description: Optional[str] = None

    @field_validator("title")
    @classmethod
    def title_not_empty(cls, v: str) -> str:
        v = v.strip()
        if not v or len(v) < 3:
            raise ValueError("Title must be at least 3 characters")
        if len(v) > 200:
            raise ValueError("Title must be at most 200 characters")
        return v

    @field_validator("slug")
    @classmethod
    def slug_valid(cls, v: str) -> str:
        import re
        v = v.strip().lower()
        if not re.match(r"^[a-z0-9]+(?:-[a-z0-9]+)*$", v):
            raise ValueError("Slug must be lowercase alphanumeric with hyphens only")
        if len(v) > 200:
            raise ValueError("Slug must be at most 200 characters")
        return v

    @field_validator("content")
    @classmethod
    def content_not_empty(cls, v: str) -> str:
        if not v or not v.strip():
            raise ValueError("Content cannot be empty")
        return v

    @field_validator("summary")
    @classmethod
    def summary_not_empty(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("Summary cannot be empty")
        if len(v) > 500:
            raise ValueError("Summary must be at most 500 characters")
        return v

class BlogCreate(BlogBase):
    pass

class BlogUpdate(BaseModel):
    title: Optional[str] = None
    slug: Optional[str] = None
    content: Optional[str] = None
    summary: Optional[str] = None
    cover_image: Optional[str] = None
    published: Optional[bool] = None
    author: Optional[str] = None
    seo_title: Optional[str] = None
    seo_description: Optional[str] = None

    @field_validator("title")
    @classmethod
    def title_not_empty(cls, v: Optional[str]) -> Optional[str]:
        if v is not None:
            v = v.strip()
            if len(v) < 3:
                raise ValueError("Title must be at least 3 characters")
            if len(v) > 200:
                raise ValueError("Title must be at most 200 characters")
        return v

    @field_validator("slug")
    @classmethod
    def slug_valid(cls, v: Optional[str]) -> Optional[str]:
        if v is not None:
            import re
            v = v.strip().lower()
            if not re.match(r"^[a-z0-9]+(?:-[a-z0-9]+)*$", v):
                raise ValueError("Slug must be lowercase alphanumeric with hyphens only")
        return v

class BlogOut(BlogBase):
    id: int
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)
