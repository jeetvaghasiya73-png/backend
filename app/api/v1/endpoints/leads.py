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
    db: Session = Depends(get_db)
):
    """
    Submit a new lead (Public endpoint for prospect inquiries) and trigger DB notification.
    """
    lead = lead_repo.create(db, obj_in=lead_in.model_dump())
    try:
        from app.models.notification import Notification
        from datetime import datetime, timezone
        notif = Notification(
            title="New Inbound Lead",
            message=f"{lead.name or 'Prospect'} requested services ({lead.company or 'Direct Inbound'}).",
            type="lead",
            read=False,
            link="/admin/dashboard/leads",
            created_at=datetime.now(timezone.utc)
        )
        db.add(notif)
        db.commit()
    except Exception as e:
        print("Failed to auto-create lead notification:", e)
        
    return lead

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

from pydantic import BaseModel
from app.models.lead import Lead

class BulkDeleteRequest(BaseModel):
    lead_ids: List[int]

@router.post("/bulk-delete")
def bulk_delete_leads(
    payload: BulkDeleteRequest,
    db: Session = Depends(get_db),
    admin_user = Depends(get_current_admin_user)
):
    """
    Bulk delete specific leads by ID (Admin only).
    """
    if not payload.lead_ids:
        return {"message": "No lead IDs provided.", "count": 0}
        
    try:
        num_deleted = db.query(Lead).filter(Lead.id.in_(payload.lead_ids)).delete(synchronize_session=False)
        db.commit()
        return {"message": f"Successfully deleted {num_deleted} leads.", "count": num_deleted}
    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to bulk delete leads: {str(e)}"
        )

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
