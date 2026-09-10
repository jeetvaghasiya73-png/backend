from datetime import datetime
from typing import Optional, List
from pydantic import BaseModel, ConfigDict

# --- Campaign Schemas ---
class CampaignBase(BaseModel):
    name: str
    description: Optional[str] = None
    daily_limit: int = 100
    delay_min: int = 30
    delay_max: int = 90
    target_city: Optional[str] = None
    target_service: Optional[str] = None
    sender_email: Optional[str] = None
    sender_name: Optional[str] = None
    email_template: str
    followup_enabled: bool = False
    followup_interval_days: int = 3
    max_followups: int = 3
    automation_mode: str = "MANUAL" # MANUAL, ASSISTED, AUTO

class CampaignCreate(CampaignBase):
    pass

class CampaignUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    status: Optional[str] = None # DRAFT, READY, RUNNING, PAUSED, COMPLETED, FAILED
    daily_limit: Optional[int] = None
    delay_min: Optional[int] = None
    delay_max: Optional[int] = None
    target_city: Optional[str] = None
    target_service: Optional[str] = None
    sender_email: Optional[str] = None
    sender_name: Optional[str] = None
    email_template: Optional[str] = None
    followup_enabled: Optional[bool] = None
    followup_interval_days: Optional[int] = None
    max_followups: Optional[int] = None
    automation_mode: Optional[str] = None

class CampaignOut(CampaignBase):
    id: int
    status: str
    created_at: datetime
    started_at: Optional[datetime] = None
    paused_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None

    model_config = ConfigDict(from_attributes=True)

# --- Email Message Schemas ---
class EmailMessageBase(BaseModel):
    campaign_id: Optional[int] = None
    lead_id: int
    message_type: str # INITIAL, FOLLOW_UP, REPLY, MANUAL
    subject: str
    body: str
    recipient_email: str
    sender_email: str

class EmailMessageCreate(EmailMessageBase):
    status: Optional[str] = "DRAFT"

class EmailMessageOut(EmailMessageBase):
    id: int
    status: str # DRAFT, QUEUED, SENDING, SENT, FAILED, BOUNCED, REPLIED, CANCELLED
    provider_message_id: Optional[str] = None
    error_message: Optional[str] = None
    created_at: datetime
    sent_at: Optional[datetime] = None
    reply_received_at: Optional[datetime] = None

    model_config = ConfigDict(from_attributes=True)

# --- Follow Up Schemas ---
class FollowUpBase(BaseModel):
    lead_id: int
    campaign_id: int
    email_message_id: Optional[int] = None
    scheduled_at: datetime
    attempt_number: int = 1

class FollowUpOut(FollowUpBase):
    id: int
    status: str # SCHEDULED, PROCESSING, SENT, CANCELLED, FAILED
    reason: Optional[str] = None
    created_at: datetime
    completed_at: Optional[datetime] = None

    model_config = ConfigDict(from_attributes=True)

# --- Analytics Schemas ---
class EmailAnalyticsOut(BaseModel):
    total_campaigns: int
    total_leads: int
    total_sent: int
    total_queued: int
    total_failed: int
    total_replied: int
    total_interested: int
    total_unsubscribed: int
    total_followups: int
    sent_by_day: List[dict] # [{"day": "2026-08-22", "count": 10}]
    replies_by_day: List[dict]
    category_performance: List[dict] # [{"category": "AI Agents", "sent": 20, "replied": 5}]
