from typing import List, Optional
from sqlalchemy.orm import Session
from app.models.blog import Blog
from app.repositories.base import BaseRepository

class BlogRepository(BaseRepository[Blog]):
    def get_by_slug(self, db: Session, *, slug: str) -> Optional[Blog]:
        return db.query(self.model).filter(self.model.slug == slug).first()

    def get_published(self, db: Session, *, skip: int = 0, limit: int = 100) -> List[Blog]:
        return (
            db.query(self.model)
            .filter(self.model.published == True)
            .order_by(self.model.created_at.desc())
            .offset(skip)
            .limit(limit)
            .all()
        )

blog_repo = BlogRepository(Blog)
