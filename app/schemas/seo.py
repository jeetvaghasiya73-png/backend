from typing import Optional
from pydantic import BaseModel, ConfigDict, field_validator

class SEOSettingBase(BaseModel):
    page_route: str
    title: str
    description: str
    keywords: Optional[str] = None
    og_image: Optional[str] = None

    @field_validator("page_route")
    @classmethod
    def route_valid(cls, v: str) -> str:
        v = v.strip()
        if not v or not v.startswith("/"):
            raise ValueError("Page route must start with /")
        if len(v) > 200:
            raise ValueError("Page route must be at most 200 characters")
        return v

    @field_validator("title")
    @classmethod
    def title_not_empty(cls, v: str) -> str:
        v = v.strip()
        if not v or len(v) < 3:
            raise ValueError("SEO title must be at least 3 characters")
        if len(v) > 200:
            raise ValueError("SEO title must be at most 200 characters")
        return v

    @field_validator("description")
    @classmethod
    def description_not_empty(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("SEO description cannot be empty")
        if len(v) > 500:
            raise ValueError("SEO description must be at most 500 characters")
        return v

class SEOSettingCreate(SEOSettingBase):
    pass

class SEOSettingUpdate(BaseModel):
    page_route: Optional[str] = None
    title: Optional[str] = None
    description: Optional[str] = None
    keywords: Optional[str] = None
    og_image: Optional[str] = None

class SEOSettingOut(SEOSettingBase):
    id: int

    model_config = ConfigDict(from_attributes=True)
