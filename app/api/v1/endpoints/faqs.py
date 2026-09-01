from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.dependencies.database import get_db
from app.dependencies.auth import get_current_admin_user, get_current_user_from_api_token
from app.repositories.faq import faq_repo
from app.schemas.faq import FAQCreate, FAQUpdate, FAQOut

router = APIRouter()

@router.post("/", response_model=FAQOut, status_code=status.HTTP_201_CREATED)
def create_faq(
    faq_in: FAQCreate,
    db: Session = Depends(get_db),
    admin_user = Depends(get_current_admin_user)
):
    """
    Create a new FAQ (Admin only).
    """
    return faq_repo.create(db, obj_in=faq_in.model_dump())

@router.get("/", response_model=List[FAQOut])
def read_faqs(
    category: Optional[str] = None,
    db: Session = Depends(get_db),
    user=Depends(get_current_user_from_api_token)
):
    """
    Get all FAQs, optionally filtered by category, ordered by order_index (Protected).
    """
    if category:
        return faq_repo.get_by_category(db, category=category)
    return faq_repo.get_all_ordered(db)

@router.put("/{faq_id}", response_model=FAQOut)
def update_faq(
    faq_id: int,
    faq_in: FAQUpdate,
    db: Session = Depends(get_db),
    admin_user = Depends(get_current_admin_user)
):
    """
    Update an FAQ (Admin only).
    """
    faq = faq_repo.get(db, id=faq_id)
    if not faq:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="FAQ not found"
        )
    return faq_repo.update(db, db_obj=faq, obj_in=faq_in)

@router.delete("/{faq_id}", response_model=FAQOut)
def delete_faq(
    faq_id: int,
    db: Session = Depends(get_db),
    admin_user = Depends(get_current_admin_user)
):
    """
    Delete an FAQ (Admin only).
    """
    faq = faq_repo.get(db, id=faq_id)
    if not faq:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="FAQ not found"
        )
    return faq_repo.remove(db, id=faq_id)
