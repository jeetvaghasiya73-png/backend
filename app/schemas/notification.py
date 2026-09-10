from pydantic import BaseModel
from typing import Optional
from datetime import datetime

class NotificationBase(BaseModel):
    title: str
    message: str
    type: Optional[str] = "system"
    read: Optional[bool] = False
    link: Optional[str] = None

class NotificationCreate(NotificationBase):
    pass

class NotificationUpdate(BaseModel):
    read: Optional[bool] = None

class NotificationOut(NotificationBase):
    id: int
    created_at: datetime

    class Config:
        from_attributes = True
