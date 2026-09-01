from datetime import datetime
from typing import Optional
from pydantic import BaseModel, ConfigDict

class ScrapedLeadBase(BaseModel):
    bussiness_name: Optional[str] = None
    bussiness_email: Optional[str] = None
    bussiness_number: Optional[str] = None
    bussiness_area: Optional[str] = None
    rating: Optional[str] = None
    landmark: Optional[str] = None
    total_review: Optional[str] = None
    building: Optional[str] = None
    pincode: Optional[str] = None
    bussiness_website: Optional[str] = None
    category: Optional[str] = None
    bussiness_address: Optional[str] = None
    service: Optional[str] = None
    scraped_city: Optional[str] = None
    scraped_service: Optional[str] = None

class ScrapedLeadOut(ScrapedLeadBase):
    id: int
    created_at: datetime
    email_status: Optional[str] = "pending"
    email_sent_at: Optional[datetime] = None
    email_error: Optional[str] = None
    
    # Outreach status and personalization details
    email_subject: Optional[str] = None
    email_body: Optional[str] = None
    personalization_status: Optional[str] = "pending"
    last_email_at: Optional[datetime] = None
    next_followup_at: Optional[datetime] = None
    followup_count: Optional[int] = 0
    reply_status: Optional[str] = "unprocessed"
    unsubscribe: Optional[bool] = False
    bounced: Optional[bool] = False
    campaign_id: Optional[int] = None

    model_config = ConfigDict(from_attributes=True)

class ScrapedLeadUpdate(BaseModel):
    email_status: Optional[str] = None
    email_sent_at: Optional[datetime] = None
    email_error: Optional[str] = None
    email_subject: Optional[str] = None
    email_body: Optional[str] = None
    personalization_status: Optional[str] = None
    last_email_at: Optional[datetime] = None
    next_followup_at: Optional[datetime] = None
    followup_count: Optional[int] = None
    reply_status: Optional[str] = None
    unsubscribe: Optional[bool] = None
    bounced: Optional[bool] = None
    campaign_id: Optional[int] = None
