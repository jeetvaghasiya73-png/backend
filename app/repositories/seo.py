from typing import Optional
from sqlalchemy.orm import Session
from app.models.seo import SEOSetting
from app.repositories.base import BaseRepository

class SEOSettingRepository(BaseRepository[SEOSetting]):
    def get_by_route(self, db: Session, *, page_route: str) -> Optional[SEOSetting]:
        return db.query(self.model).filter(self.model.page_route == page_route).first()

seo_repo = SEOSettingRepository(SEOSetting)
