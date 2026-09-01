from datetime import datetime, timezone
from typing import Optional
from sqlalchemy import Integer, String, Text, DateTime, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.database.session import Base

class FollowUp(Base):
    __tablename__ = "followups"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    lead_id: Mapped[int] = mapped_column(Integer, ForeignKey("scraped_leads.id", ondelete="CASCADE"), nullable=False)
    campaign_id: Mapped[int] = mapped_column(Integer, ForeignKey("campaigns.id", ondelete="CASCADE"), nullable=False)
    email_message_id: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey("email_messages.id", ondelete="SET NULL"), nullable=True)
    
    scheduled_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, index=True)
    attempt_number: Mapped[int] = mapped_column(Integer, default=1, server_default="1")
    status: Mapped[str] = mapped_column(String(50), default="SCHEDULED", server_default="SCHEDULED")  # SCHEDULED, PROCESSING, SENT, CANCELLED, FAILED
    reason: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=lambda: datetime.now(timezone.utc)
    )
    completed_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)

    # Relationships
    campaign: Mapped["Campaign"] = relationship("Campaign", back_populates="followups")
    lead: Mapped["ScrapedLead"] = relationship("ScrapedLead", back_populates="followups")
    email_message: Mapped[Optional["EmailMessage"]] = relationship("EmailMessage")
