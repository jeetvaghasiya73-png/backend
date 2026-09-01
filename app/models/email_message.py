from datetime import datetime, timezone
from typing import Optional
from sqlalchemy import Integer, String, Text, DateTime, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.database.session import Base

class EmailMessage(Base):
    __tablename__ = "email_messages"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    campaign_id: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey("campaigns.id", ondelete="SET NULL"), nullable=True)
    lead_id: Mapped[int] = mapped_column(Integer, ForeignKey("scraped_leads.id", ondelete="CASCADE"), nullable=False)
    
    message_type: Mapped[str] = mapped_column(String(50), default="INITIAL", server_default="INITIAL")  # INITIAL, FOLLOW_UP, REPLY, MANUAL
    subject: Mapped[str] = mapped_column(String(255), nullable=False)
    body: Mapped[str] = mapped_column(Text, nullable=False)
    recipient_email: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    sender_email: Mapped[str] = mapped_column(String(255), nullable=False)
    
    status: Mapped[str] = mapped_column(String(50), default="DRAFT", server_default="DRAFT")  # DRAFT, QUEUED, SENDING, SENT, FAILED, BOUNCED, REPLIED, CANCELLED
    provider_message_id: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    error_message: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=lambda: datetime.now(timezone.utc)
    )
    sent_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    reply_received_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)

    # Relationships
    campaign: Mapped[Optional["Campaign"]] = relationship("Campaign", back_populates="messages")
    lead: Mapped["ScrapedLead"] = relationship("ScrapedLead", back_populates="messages")
