import re
import time
from sqlalchemy.orm import Session
from app.repositories.blog import blog_repo
from app.schemas.blog import BlogCreate, BlogUpdate
from app.models.blog import Blog

def slugify(text: str) -> str:
    text = text.lower()
    text = re.sub(r"[^\w\s-]", "", text)
    text = re.sub(r"[\s_-]+", "-", text)
    return text.strip("-")

class BlogService:
    def create_blog(self, db: Session, *, blog_in: BlogCreate) -> Blog:
        obj_data = blog_in.model_dump()
        if not obj_data.get("slug"):
            obj_data["slug"] = slugify(obj_data["title"])
            
        existing = blog_repo.get_by_slug(db, slug=obj_data["slug"])
        if existing:
            obj_data["slug"] = f"{obj_data['slug']}-{int(time.time())}"
            
        return blog_repo.create(db, obj_in=obj_data)

    def update_blog(self, db: Session, *, db_obj: Blog, blog_in: BlogUpdate) -> Blog:
        obj_data = blog_in.model_dump(exclude_unset=True)
        if "title" in obj_data and "slug" not in obj_data:
            obj_data["slug"] = slugify(obj_data["title"])
            
        if "slug" in obj_data:
            existing = blog_repo.get_by_slug(db, slug=obj_data["slug"])
            if existing and existing.id != db_obj.id:
                obj_data["slug"] = f"{obj_data['slug']}-{int(time.time())}"
                
        return blog_repo.update(db, db_obj=db_obj, obj_in=obj_data)

blog_service = BlogService()
