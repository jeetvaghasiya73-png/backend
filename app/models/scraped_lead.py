from datetime import datetime, timezone
from typing import Optional, List
from sqlalchemy import Integer, String, Text, DateTime, Boolean, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.database.session import Base

class ScrapedLead(Base):
    __tablename__ = "scraped_leads"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    bussiness_name: Mapped[str] = mapped_column(String(255), nullable=True)
    bussiness_email: Mapped[Optional[str]] = mapped_column(String(255), nullable=True, index=True, unique=True)
    bussiness_number: Mapped[str] = mapped_column(String(100), nullable=True)
    bussiness_area: Mapped[str] = mapped_column(String(255), nullable=True)
    rating: Mapped[str] = mapped_column(String(50), nullable=True)
    landmark: Mapped[str] = mapped_column(String(255), nullable=True)
    total_review: Mapped[str] = mapped_column(String(50), nullable=True)
    building: Mapped[str] = mapped_column(String(255), nullable=True)
    pincode: Mapped[str] = mapped_column(String(50), nullable=True)
    bussiness_website: Mapped[str] = mapped_column(String(255), nullable=True)
    category: Mapped[str] = mapped_column(Text, nullable=True)
    bussiness_address: Mapped[str] = mapped_column(Text, nullable=True)
    service: Mapped[str] = mapped_column(Text, nullable=True)
    scraped_city: Mapped[str] = mapped_column(String(100), nullable=True, index=True)
    scraped_service: Mapped[str] = mapped_column(String(100), nullable=True, index=True)
    
    # Outreach status tracking columns
    email_status: Mapped[str] = mapped_column(String(50), default="pending", server_default="pending", index=True)
    email_sent_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    email_error: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    
    # Additional Campaign & Agent tracking fields
    email_subject: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    email_body: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    personalization_status: Mapped[str] = mapped_column(String(50), default="pending", server_default="pending") # pending, success, failed
    last_email_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    next_followup_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    followup_count: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    reply_status: Mapped[str] = mapped_column(String(50), default="unprocessed", server_default="unprocessed") # unprocessed, classified, replied, etc.
    unsubscribe: Mapped[bool] = mapped_column(Boolean, default=False, server_default="0")
    bounced: Mapped[bool] = mapped_column(Boolean, default=False, server_default="0")
    campaign_id: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey("campaigns.id", ondelete="SET NULL"), nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=lambda: datetime.now(timezone.utc)
    )

    # Relationships
    campaign: Mapped[Optional["Campaign"]] = relationship("Campaign", back_populates="leads")
    messages: Mapped[List["EmailMessage"]] = relationship("EmailMessage", back_populates="lead", cascade="all, delete-orphan")
    followups: Mapped[List["FollowUp"]] = relationship("FollowUp", back_populates="lead", cascade="all, delete-orphan")
