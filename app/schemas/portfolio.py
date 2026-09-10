from datetime import datetime
from typing import List, Optional
from pydantic import BaseModel, ConfigDict, field_validator

class PortfolioBase(BaseModel):
    title: str
    slug: str
    description: str
    image: str
    client: str
    services_used: List[str] = []
    url: Optional[str] = None
    year: int
    featured: Optional[bool] = False

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
        return v

    @field_validator("year")
    @classmethod
    def year_valid(cls, v: int) -> int:
        if v < 2000 or v > 2100:
            raise ValueError("Year must be between 2000 and 2100")
        return v

    @field_validator("url")
    @classmethod
    def url_valid(cls, v: Optional[str]) -> Optional[str]:
        if v is not None:
            v = v.strip()
            if v and not (v.startswith("http://") or v.startswith("https://")):
                raise ValueError("URL must start with http:// or https://")
        return v

class PortfolioCreate(PortfolioBase):
    pass

class PortfolioUpdate(BaseModel):
    title: Optional[str] = None
    slug: Optional[str] = None
    description: Optional[str] = None
    image: Optional[str] = None
    client: Optional[str] = None
    services_used: Optional[List[str]] = None
    url: Optional[str] = None
    year: Optional[int] = None
    featured: Optional[bool] = None

    @field_validator("year")
    @classmethod
    def year_valid(cls, v: Optional[int]) -> Optional[int]:
        if v is not None and (v < 2000 or v > 2100):
            raise ValueError("Year must be between 2000 and 2100")
        return v

class PortfolioOut(PortfolioBase):
    id: int
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)
