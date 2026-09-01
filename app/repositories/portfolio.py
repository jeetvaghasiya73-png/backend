from typing import List, Optional
from sqlalchemy.orm import Session
from app.models.portfolio import Portfolio
from app.repositories.base import BaseRepository

class PortfolioRepository(BaseRepository[Portfolio]):
    def get_by_slug(self, db: Session, *, slug: str) -> Optional[Portfolio]:
        return db.query(self.model).filter(self.model.slug == slug).first()

    def get_featured(self, db: Session) -> List[Portfolio]:
        return (
            db.query(self.model)
            .filter(self.model.featured == True)
            .order_by(self.model.created_at.desc())
            .all()
        )

portfolio_repo = PortfolioRepository(Portfolio)
