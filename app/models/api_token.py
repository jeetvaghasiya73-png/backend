from datetime import datetime, timezone
from sqlalchemy import Integer, String, Boolean, DateTime, ForeignKey, Float
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.session import Base

class ApiToken(Base):
    __tablename__ = "api_tokens"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    token: Mapped[str] = mapped_column(String(255), unique=True, index=True, nullable=False)
    user_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.id"), nullable=False)
    description: Mapped[str] = mapped_column(String(255), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=lambda: datetime.now(timezone.utc)
    )
    expires_at: Mapped[datetime] = mapped_column(DateTime, nullable=True)
    
    usages = relationship("ApiTokenUsage", back_populates="api_token")


class ApiTokenUsage(Base):
    __tablename__ = "api_token_usages"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    token_id: Mapped[int] = mapped_column(Integer, ForeignKey("api_tokens.id"), nullable=False)
    endpoint: Mapped[str] = mapped_column(String(255), nullable=False)
    ip_address: Mapped[str] = mapped_column(String(50), nullable=True)
    duration_ms: Mapped[float] = mapped_column(Float, nullable=True)
    used_at: Mapped[datetime] = mapped_column(
        DateTime, default=lambda: datetime.now(timezone.utc)
    )

    api_token = relationship("ApiToken", back_populates="usages")
