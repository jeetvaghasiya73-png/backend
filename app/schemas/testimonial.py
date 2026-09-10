from typing import Optional
from pydantic import BaseModel, ConfigDict, field_validator

class TestimonialBase(BaseModel):
    name: str
    role: str
    company: str
    content: str
    image: Optional[str] = None
    rating: Optional[int] = 5

    @field_validator("name")
    @classmethod
    def name_not_empty(cls, v: str) -> str:
        v = v.strip()
        if not v or len(v) < 2:
            raise ValueError("Name must be at least 2 characters")
        if len(v) > 100:
            raise ValueError("Name must be at most 100 characters")
        return v

    @field_validator("content")
    @classmethod
    def content_not_empty(cls, v: str) -> str:
        if not v or not v.strip():
            raise ValueError("Testimonial content cannot be empty")
        if len(v) > 2000:
            raise ValueError("Content must be at most 2000 characters")
        return v

    @field_validator("rating")
    @classmethod
    def rating_valid(cls, v: Optional[int]) -> Optional[int]:
        if v is not None and (v < 1 or v > 5):
            raise ValueError("Rating must be between 1 and 5")
        return v

class TestimonialCreate(TestimonialBase):
    pass

class TestimonialUpdate(BaseModel):
    name: Optional[str] = None
    role: Optional[str] = None
    company: Optional[str] = None
    content: Optional[str] = None
    image: Optional[str] = None
    rating: Optional[int] = None

    @field_validator("rating")
    @classmethod
    def rating_valid(cls, v: Optional[int]) -> Optional[int]:
        if v is not None and (v < 1 or v > 5):
            raise ValueError("Rating must be between 1 and 5")
        return v

class TestimonialOut(TestimonialBase):
    id: int

    model_config = ConfigDict(from_attributes=True)
