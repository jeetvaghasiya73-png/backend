from typing import List
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.dependencies.database import get_db
from app.dependencies.auth import get_current_admin_user, get_current_user_from_api_token
from app.repositories.blog import blog_repo
from app.services.blog import blog_service
from app.schemas.blog import BlogCreate, BlogUpdate, BlogOut

router = APIRouter()

@router.post("/", response_model=BlogOut, status_code=status.HTTP_201_CREATED)
def create_blog(
    blog_in: BlogCreate,
    db: Session = Depends(get_db),
    admin_user = Depends(get_current_admin_user)
):
    """
    Create a new blog post (Admin only).
    """
    return blog_service.create_blog(db, blog_in=blog_in)

@router.get("/", response_model=List[BlogOut])
def read_blogs(
    skip: int = 0,
    limit: int = 100,
    db: Session = Depends(get_db)
):
    """
    Get all blogs (Admin or general retrieval).
    """
    return blog_repo.get_multi(db, skip=skip, limit=limit)

@router.get("/published", response_model=List[BlogOut])
def read_published_blogs(
    skip: int = 0,
    limit: int = 100,
    db: Session = Depends(get_db),
    user=Depends(get_current_user_from_api_token)
):
    """
    Get all published blogs (Protected).
    """
    return blog_repo.get_published(db, skip=skip, limit=limit)

@router.get("/{slug}", response_model=BlogOut)
def read_blog_by_slug(
    slug: str,
    db: Session = Depends(get_db),
    user=Depends(get_current_user_from_api_token)
):
    """
    Get a single published blog by slug (Protected).
    """
    blog = blog_repo.get_by_slug(db, slug=slug)
    if not blog:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Blog not found"
        )
    return blog

@router.put("/{blog_id}", response_model=BlogOut)
def update_blog(
    blog_id: int,
    blog_in: BlogUpdate,
    db: Session = Depends(get_db),
    admin_user = Depends(get_current_admin_user)
):
    """
    Update a blog post (Admin only).
    """
    blog = blog_repo.get(db, id=blog_id)
    if not blog:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Blog not found"
        )
    return blog_service.update_blog(db, db_obj=blog, blog_in=blog_in)

@router.delete("/{blog_id}", response_model=BlogOut)
def delete_blog(
    blog_id: int,
    db: Session = Depends(get_db),
    admin_user = Depends(get_current_admin_user)
):
    """
    Delete a blog post (Admin only).
    """
    blog = blog_repo.get(db, id=blog_id)
    if not blog:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Blog not found"
        )
    return blog_repo.remove(db, id=blog_id)
