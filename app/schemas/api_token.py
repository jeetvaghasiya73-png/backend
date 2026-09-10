from datetime import datetime
from typing import Optional, List
from pydantic import BaseModel, ConfigDict

class ApiTokenBase(BaseModel):
    description: Optional[str] = None
    is_active: bool = True
    expires_at: Optional[datetime] = None

class ApiTokenCreate(ApiTokenBase):
    user_id: Optional[int] = None

class ApiTokenOut(ApiTokenBase):
    id: int
    token: str
    user_id: int
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)

class ApiTokenUsageOut(BaseModel):
    id: int
    endpoint: str
    ip_address: Optional[str] = None
    duration_ms: Optional[float] = None
    used_at: datetime

    model_config = ConfigDict(from_attributes=True)
