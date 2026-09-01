from datetime import datetime, timezone
from typing import Optional, List
from sqlalchemy import Integer, String, Text, DateTime, Boolean
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.database.session import Base

class Campaign(Base):
    __tablename__ = "campaigns"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(String(50), default="DRAFT", server_default="DRAFT")  # DRAFT, READY, RUNNING, PAUSED, COMPLETED, FAILED
    
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=lambda: datetime.now(timezone.utc)
    )
    started_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    paused_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    completed_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)

    daily_limit: Mapped[int] = mapped_column(Integer, default=100)
    delay_min: Mapped[int] = mapped_column(Integer, default=30)  # delay in seconds
    delay_max: Mapped[int] = mapped_column(Integer, default=90)  # delay in seconds
    target_city: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    target_service: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    sender_email: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    sender_name: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    email_template: Mapped[str] = mapped_column(Text, nullable=False)  # template / AI instructions
    
    followup_enabled: Mapped[bool] = mapped_column(Boolean, default=False)
    followup_interval_days: Mapped[int] = mapped_column(Integer, default=3)
    max_followups: Mapped[int] = mapped_column(Integer, default=3)
    automation_mode: Mapped[str] = mapped_column(String(50), default="MANUAL", server_default="MANUAL")  # MANUAL, ASSISTED, AUTO

    # Relationships
    messages: Mapped[List["EmailMessage"]] = relationship("EmailMessage", back_populates="campaign", cascade="all, delete-orphan")
    followups: Mapped[List["FollowUp"]] = relationship("FollowUp", back_populates="campaign", cascade="all, delete-orphan")
    leads: Mapped[List["ScrapedLead"]] = relationship("ScrapedLead", back_populates="campaign")
