import re
import time
from sqlalchemy.orm import Session
from app.repositories.portfolio import portfolio_repo
from app.schemas.portfolio import PortfolioCreate, PortfolioUpdate
from app.models.portfolio import Portfolio

def slugify(text: str) -> str:
    text = text.lower()
    text = re.sub(r"[^\w\s-]", "", text)
    text = re.sub(r"[\s_-]+", "-", text)
    return text.strip("-")

class PortfolioService:
    def create_portfolio(self, db: Session, *, portfolio_in: PortfolioCreate) -> Portfolio:
        obj_data = portfolio_in.model_dump()
        if not obj_data.get("slug"):
            obj_data["slug"] = slugify(obj_data["title"])
            
        existing = portfolio_repo.get_by_slug(db, slug=obj_data["slug"])
        if existing:
            obj_data["slug"] = f"{obj_data['slug']}-{int(time.time())}"
            
        return portfolio_repo.create(db, obj_in=obj_data)

    def update_portfolio(self, db: Session, *, db_obj: Portfolio, portfolio_in: PortfolioUpdate) -> Portfolio:
        obj_data = portfolio_in.model_dump(exclude_unset=True)
        if "title" in obj_data and "slug" not in obj_data:
            obj_data["slug"] = slugify(obj_data["title"])
            
        if "slug" in obj_data:
            existing = portfolio_repo.get_by_slug(db, slug=obj_data["slug"])
            if existing and existing.id != db_obj.id:
                obj_data["slug"] = f"{obj_data['slug']}-{int(time.time())}"
                
        return portfolio_repo.update(db, db_obj=db_obj, obj_in=obj_data)

portfolio_service = PortfolioService()
