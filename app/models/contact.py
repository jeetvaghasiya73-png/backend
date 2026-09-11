from typing import Optional, List
from datetime import datetime, timezone
from sqlalchemy import Integer, String, Text, DateTime, Boolean
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.session import Base

class ContactMessage(Base):
    __tablename__ = "contact_messages"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    email: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    subject: Mapped[str] = mapped_column(String(255), nullable=True)
    message: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(String(50), default="unread") # unread, read, replied
    auto_reply_sent: Mapped[bool] = mapped_column(Boolean, default=False, server_default="FALSE")
    auto_reply_status: Mapped[Optional[str]] = mapped_column(String(50), default="pending", server_default="pending")
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=lambda: datetime.now(timezone.utc)
    )

    # Relationships
    messages: Mapped[List["EmailMessage"]] = relationship("EmailMessage", foreign_keys="[EmailMessage.contact_id]", cascade="all, delete-orphan")

