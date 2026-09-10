from sqlalchemy import Integer, String, Text, Boolean, JSON
from sqlalchemy.orm import Mapped, mapped_column

from app.database.session import Base

class Service(Base):
    __tablename__ = "services"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    slug: Mapped[str] = mapped_column(String(255), unique=True, index=True, nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    icon: Mapped[str] = mapped_column(String(100), nullable=False) # Name of lucide icon
    features: Mapped[list] = mapped_column(JSON, default=list, nullable=False) # e.g. ["Feature 1", "Feature 2"]
    active: Mapped[bool] = mapped_column(Boolean, default=True)
