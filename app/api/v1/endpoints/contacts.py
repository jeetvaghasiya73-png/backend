from typing import List
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.dependencies.database import get_db
from app.dependencies.auth import get_current_admin_user, get_current_user_from_api_token
from app.repositories.contact import contact_repo
from app.schemas.contact import ContactCreate, ContactUpdate, ContactOut

router = APIRouter()

@router.post("/", response_model=ContactOut, status_code=status.HTTP_201_CREATED)
def create_contact(
    contact_in: ContactCreate,
    db: Session = Depends(get_db),
    admin_user = Depends(get_current_admin_user)
):
    """
    Submit a new contact message (Admin only).
    """
    return contact_repo.create(db, obj_in=contact_in.model_dump())

@router.get("/", response_model=List[ContactOut])
def read_contacts(
    skip: int = 0,
    limit: int = 100,
    db: Session = Depends(get_db),
    admin_user = Depends(get_current_admin_user)
):
    """
    Get all contact messages (Admin only).
    """
    return contact_repo.get_multi(db, skip=skip, limit=limit)

@router.put("/{contact_id}", response_model=ContactOut)
def update_contact(
    contact_id: int,
    contact_in: ContactUpdate,
    db: Session = Depends(get_db),
    admin_user = Depends(get_current_admin_user)
):
    """
    Update a contact message (Admin only).
    """
    contact = contact_repo.get(db, id=contact_id)
    if not contact:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Contact message not found"
        )
    return contact_repo.update(db, db_obj=contact, obj_in=contact_in)

@router.delete("/{contact_id}", response_model=ContactOut)
def delete_contact(
    contact_id: int,
    db: Session = Depends(get_db),
    admin_user = Depends(get_current_admin_user)
):
    """
    Delete a contact message (Admin only).
    """
    contact = contact_repo.get(db, id=contact_id)
    if not contact:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Contact message not found"
        )
    return contact_repo.remove(db, id=contact_id)
