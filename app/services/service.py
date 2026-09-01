import re
import time
from sqlalchemy.orm import Session
from app.repositories.service import service_repo
from app.schemas.service import ServiceCreate, ServiceUpdate
from app.models.service import Service

def slugify(text: str) -> str:
    text = text.lower()
    text = re.sub(r"[^\w\s-]", "", text)
    text = re.sub(r"[\s_-]+", "-", text)
    return text.strip("-")

class ServiceService:
    def create_service(self, db: Session, *, service_in: ServiceCreate) -> Service:
        obj_data = service_in.model_dump()
        if not obj_data.get("slug"):
            obj_data["slug"] = slugify(obj_data["title"])
            
        existing = service_repo.get_by_slug(db, slug=obj_data["slug"])
        if existing:
            obj_data["slug"] = f"{obj_data['slug']}-{int(time.time())}"
            
        return service_repo.create(db, obj_in=obj_data)

    def update_service(self, db: Session, *, db_obj: Service, service_in: ServiceUpdate) -> Service:
        obj_data = service_in.model_dump(exclude_unset=True)
        if "title" in obj_data and "slug" not in obj_data:
            obj_data["slug"] = slugify(obj_data["title"])
            
        if "slug" in obj_data:
            existing = service_repo.get_by_slug(db, slug=obj_data["slug"])
            if existing and existing.id != db_obj.id:
                obj_data["slug"] = f"{obj_data['slug']}-{int(time.time())}"
                
        return service_repo.update(db, db_obj=db_obj, obj_in=obj_data)

service_service = ServiceService()
