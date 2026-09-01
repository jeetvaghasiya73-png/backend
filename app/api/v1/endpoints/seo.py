from typing import List
from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session

from app.dependencies.database import get_db
from app.dependencies.auth import get_current_admin_user, get_current_user_from_api_token
from app.repositories.seo import seo_repo
from app.schemas.seo import SEOSettingCreate, SEOSettingUpdate, SEOSettingOut

router = APIRouter()

@router.post("/", response_model=SEOSettingOut, status_code=status.HTTP_201_CREATED)
def create_seo_setting(
    seo_in: SEOSettingCreate,
    db: Session = Depends(get_db),
    admin_user = Depends(get_current_admin_user)
):
    """
    Create a new SEO page setting (Admin only).
    """
    existing = seo_repo.get_by_route(db, page_route=seo_in.page_route)
    if existing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"SEO setting already exists for route: {seo_in.page_route}"
        )
    return seo_repo.create(db, obj_in=seo_in.model_dump())

@router.get("/", response_model=List[SEOSettingOut])
def read_seo_settings(
    skip: int = 0,
    limit: int = 100,
    db: Session = Depends(get_db),
    user=Depends(get_current_user_from_api_token)
):
    """
    Get all SEO settings (Protected).
    """
    return seo_repo.get_multi(db, skip=skip, limit=limit)

@router.get("/route", response_model=SEOSettingOut)
def read_seo_setting_by_route(
    page_route: str = Query(..., description="Route of page, e.g. '/' or '/blogs'"),
    db: Session = Depends(get_db),
    user=Depends(get_current_user_from_api_token)
):
    """
    Get SEO setting for a specific page route (Protected).
    """
    seo = seo_repo.get_by_route(db, page_route=page_route)
    if not seo:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="SEO setting not found for route"
        )
    return seo

@router.put("/{seo_id}", response_model=SEOSettingOut)
def update_seo_setting(
    seo_id: int,
    seo_in: SEOSettingUpdate,
    db: Session = Depends(get_db),
    admin_user = Depends(get_current_admin_user)
):
    """
    Update an SEO setting (Admin only).
    """
    seo = seo_repo.get(db, id=seo_id)
    if not seo:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="SEO setting not found"
        )
    return seo_repo.update(db, db_obj=seo, obj_in=seo_in)

@router.delete("/{seo_id}", response_model=SEOSettingOut)
def delete_seo_setting(
    seo_id: int,
    db: Session = Depends(get_db),
    admin_user = Depends(get_current_admin_user)
):
    """
    Delete an SEO setting (Admin only).
    """
    seo = seo_repo.get(db, id=seo_id)
    if not seo:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="SEO setting not found"
        )
    return seo_repo.remove(db, id=seo_id)
