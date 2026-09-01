from typing import List
from sqlalchemy.orm import Session
from app.models.faq import FAQ
from app.repositories.base import BaseRepository

class FAQRepository(BaseRepository[FAQ]):
    def get_all_ordered(self, db: Session) -> List[FAQ]:
        return db.query(self.model).order_by(self.model.order_index.asc()).all()

    def get_by_category(self, db: Session, *, category: str) -> List[FAQ]:
        return (
            db.query(self.model)
            .filter(self.model.category == category)
            .order_by(self.model.order_index.asc())
            .all()
        )

faq_repo = FAQRepository(FAQ)
