from typing import List
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.dependencies.database import get_db
from app.dependencies.auth import get_current_admin_user, get_current_user_from_api_token
from app.repositories.testimonial import testimonial_repo
from app.schemas.testimonial import TestimonialCreate, TestimonialUpdate, TestimonialOut

router = APIRouter()

@router.post("/", response_model=TestimonialOut, status_code=status.HTTP_201_CREATED)
def create_testimonial(
    testimonial_in: TestimonialCreate,
    db: Session = Depends(get_db),
    admin_user = Depends(get_current_admin_user)
):
    """
    Create a new testimonial (Admin only).
    """
    return testimonial_repo.create(db, obj_in=testimonial_in.model_dump())

@router.get("/", response_model=List[TestimonialOut])
def read_testimonials(
    skip: int = 0,
    limit: int = 100,
    db: Session = Depends(get_db),
    user=Depends(get_current_user_from_api_token)
):
    """
    Get all testimonials (Protected).
    """
    return testimonial_repo.get_multi(db, skip=skip, limit=limit)

@router.put("/{testimonial_id}", response_model=TestimonialOut)
def update_testimonial(
    testimonial_id: int,
    testimonial_in: TestimonialUpdate,
    db: Session = Depends(get_db),
    admin_user = Depends(get_current_admin_user)
):
    """
    Update a testimonial (Admin only).
    """
    testimonial = testimonial_repo.get(db, id=testimonial_id)
    if not testimonial:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Testimonial not found"
        )
    return testimonial_repo.update(db, db_obj=testimonial, obj_in=testimonial_in)

@router.delete("/{testimonial_id}", response_model=TestimonialOut)
def delete_testimonial(
    testimonial_id: int,
    db: Session = Depends(get_db),
    admin_user = Depends(get_current_admin_user)
):
    """
    Delete a testimonial (Admin only).
    """
    testimonial = testimonial_repo.get(db, id=testimonial_id)
    if not testimonial:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Testimonial not found"
        )
    return testimonial_repo.remove(db, id=testimonial_id)
