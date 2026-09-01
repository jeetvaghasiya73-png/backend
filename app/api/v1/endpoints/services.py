from typing import List
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.dependencies.database import get_db
from app.dependencies.auth import get_current_admin_user, get_current_user_from_api_token
from app.repositories.service import service_repo
from app.services.service import service_service
from app.schemas.service import ServiceCreate, ServiceUpdate, ServiceOut

router = APIRouter()

@router.post("/", response_model=ServiceOut, status_code=status.HTTP_201_CREATED)
def create_service(
    service_in: ServiceCreate,
    db: Session = Depends(get_db),
    admin_user = Depends(get_current_admin_user)
):
    """
    Create a new service (Admin only).
    """
    return service_service.create_service(db, service_in=service_in)

@router.get("/", response_model=List[ServiceOut])
def read_services(
    skip: int = 0,
    limit: int = 100,
    db: Session = Depends(get_db),
    user=Depends(get_current_user_from_api_token)
):
    """
    Get all services (Protected).
    """
    return service_repo.get_multi(db, skip=skip, limit=limit)

@router.get("/active", response_model=List[ServiceOut])
def read_active_services(
    db: Session = Depends(get_db),
    user=Depends(get_current_user_from_api_token)
):
    """
    Get active services only (Protected).
    """
    return service_repo.get_active(db)

@router.get("/{slug}", response_model=ServiceOut)
def read_service_by_slug(
    slug: str,
    db: Session = Depends(get_db),
    user=Depends(get_current_user_from_api_token)
):
    """
    Get a single service by slug (Protected).
    """
    service = service_repo.get_by_slug(db, slug=slug)
    if not service:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Service not found"
        )
    return service

@router.put("/{service_id}", response_model=ServiceOut)
def update_service(
    service_id: int,
    service_in: ServiceUpdate,
    db: Session = Depends(get_db),
    admin_user = Depends(get_current_admin_user)
):
    """
    Update a service (Admin only).
    """
    service = service_repo.get(db, id=service_id)
    if not service:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Service not found"
        )
    return service_service.update_service(db, db_obj=service, service_in=service_in)

@router.delete("/{service_id}", response_model=ServiceOut)
def delete_service(
    service_id: int,
    db: Session = Depends(get_db),
    admin_user = Depends(get_current_admin_user)
):
    """
    Delete a service (Admin only).
    """
    service = service_repo.get(db, id=service_id)
    if not service:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Service not found"
        )
    return service_repo.remove(db, id=service_id)
