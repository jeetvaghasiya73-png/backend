from sqlalchemy import Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.database.session import Base

class SEOSetting(Base):
    __tablename__ = "seo_settings"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    page_route: Mapped[str] = mapped_column(String(255), unique=True, index=True, nullable=False) # e.g. "/about", "/"
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    keywords: Mapped[str] = mapped_column(String(500), nullable=True) # comma separated
    og_image: Mapped[str] = mapped_column(String(500), nullable=True)
