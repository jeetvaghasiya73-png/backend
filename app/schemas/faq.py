from typing import Optional
from pydantic import BaseModel, ConfigDict, field_validator

class FAQBase(BaseModel):
    question: str
    answer: str
    category: Optional[str] = "General"
    order_index: Optional[int] = 0

    @field_validator("question")
    @classmethod
    def question_not_empty(cls, v: str) -> str:
        v = v.strip()
        if not v or len(v) < 5:
            raise ValueError("Question must be at least 5 characters")
        if len(v) > 500:
            raise ValueError("Question must be at most 500 characters")
        return v

    @field_validator("answer")
    @classmethod
    def answer_not_empty(cls, v: str) -> str:
        if not v or not v.strip():
            raise ValueError("Answer cannot be empty")
        if len(v) > 5000:
            raise ValueError("Answer must be at most 5000 characters")
        return v

    @field_validator("order_index")
    @classmethod
    def order_valid(cls, v: Optional[int]) -> Optional[int]:
        if v is not None and v < 0:
            raise ValueError("Order index must be 0 or greater")
        return v

class FAQCreate(FAQBase):
    pass

class FAQUpdate(BaseModel):
    question: Optional[str] = None
    answer: Optional[str] = None
    category: Optional[str] = None
    order_index: Optional[int] = None

class FAQOut(FAQBase):
    id: int

    model_config = ConfigDict(from_attributes=True)
