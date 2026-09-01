from datetime import datetime, timezone
from sqlalchemy import Integer, String, Text, DateTime
from sqlalchemy.orm import Mapped, mapped_column
from app.database.session import Base

class ScrapedListing(Base):
    __tablename__ = "scraped_listings"

    docid: Mapped[str] = mapped_column(String(100), primary_key=True)
    name: Mapped[str] = mapped_column(String(255), nullable=True)
    distance: Mapped[str] = mapped_column(String(100), nullable=True)
    NewAddress: Mapped[str] = mapped_column(Text, nullable=True)
    lat: Mapped[str] = mapped_column(String(100), nullable=True)
    lon: Mapped[str] = mapped_column(String(100), nullable=True)
    compRating: Mapped[str] = mapped_column(String(50), nullable=True)
    verified: Mapped[str] = mapped_column(String(50), nullable=True)
    area: Mapped[str] = mapped_column(String(255), nullable=True)
    type: Mapped[str] = mapped_column(String(100), nullable=True)
    VNumber: Mapped[str] = mapped_column(String(100), nullable=True)
    totalReviews: Mapped[str] = mapped_column(String(50), nullable=True)
    city: Mapped[str] = mapped_column(String(100), nullable=True)
    vertical: Mapped[str] = mapped_column(String(255), nullable=True)
    vertical_name: Mapped[str] = mapped_column(String(255), nullable=True)
    wpnumber: Mapped[str] = mapped_column(String(100), nullable=True)
    weburl: Mapped[str] = mapped_column(String(500), nullable=True, unique=True)
    resp_rate: Mapped[str] = mapped_column(String(100), nullable=True)
    pincode: Mapped[str] = mapped_column(String(50), nullable=True)
    loccity: Mapped[str] = mapped_column(String(100), nullable=True)
    service_catalog: Mapped[str] = mapped_column(Text, nullable=True)
    price_tagline: Mapped[str] = mapped_column(String(255), nullable=True)
    logo: Mapped[str] = mapped_column(String(500), nullable=True)
    scraped_city: Mapped[str] = mapped_column(String(100), nullable=True)
    scraped_service: Mapped[str] = mapped_column(String(100), nullable=True)
    status: Mapped[str] = mapped_column(String(50), default="pending", index=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=lambda: datetime.now(timezone.utc)
    )
