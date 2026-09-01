from typing import List, Optional
from sqlalchemy.orm import Session
from app.models.service import Service
from app.repositories.base import BaseRepository

class ServiceRepository(BaseRepository[Service]):
    def get_by_slug(self, db: Session, *, slug: str) -> Optional[Service]:
        return db.query(self.model).filter(self.model.slug == slug).first()

    def get_active(self, db: Session) -> List[Service]:
        return db.query(self.model).filter(self.model.active == True).all()

service_repo = ServiceRepository(Service)
