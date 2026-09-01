from typing import List
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.dependencies.database import get_db
from app.dependencies.auth import get_current_admin_user, get_current_user_from_api_token
from app.repositories.lead import lead_repo
from app.schemas.lead import LeadCreate, LeadUpdate, LeadOut

router = APIRouter()

@router.post("/", response_model=LeadOut, status_code=status.HTTP_201_CREATED)
def create_lead(
    lead_in: LeadCreate,
    db: Session = Depends(get_db),
    user=Depends(get_current_user_from_api_token)
):
    """
    Submit a new lead (Protected).
    """
    return lead_repo.create(db, obj_in=lead_in.model_dump())

@router.get("/", response_model=List[LeadOut])
def read_leads(
    skip: int = 0,
    limit: int = 100,
    db: Session = Depends(get_db),
    admin_user = Depends(get_current_admin_user)
):
    """
    Get all leads (Admin only).
    """
    return lead_repo.get_multi(db, skip=skip, limit=limit)

@router.put("/{lead_id}", response_model=LeadOut)
def update_lead(
    lead_id: int,
    lead_in: LeadUpdate,
    db: Session = Depends(get_db),
    admin_user = Depends(get_current_admin_user)
):
    """
    Update a lead (Admin only).
    """
    lead = lead_repo.get(db, id=lead_id)
    if not lead:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Lead not found"
        )
    return lead_repo.update(db, db_obj=lead, obj_in=lead_in)

@router.delete("/{lead_id}", response_model=LeadOut)
def delete_lead(
    lead_id: int,
    db: Session = Depends(get_db),
    admin_user = Depends(get_current_admin_user)
):
    """
    Delete a lead (Admin only).
    """
    lead = lead_repo.get(db, id=lead_id)
    if not lead:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Lead not found"
        )
    return lead_repo.remove(db, id=lead_id)
