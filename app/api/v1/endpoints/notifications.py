from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from datetime import datetime, timezone

from app.dependencies.database import get_db
from app.dependencies.auth import get_current_admin_user
from app.models.notification import Notification
from app.schemas.notification import NotificationOut, NotificationCreate, NotificationUpdate
from app.models.contact import ContactMessage
from app.models.lead import Lead

router = APIRouter()

@router.get("/", response_model=List[NotificationOut])
def get_notifications(
    db: Session = Depends(get_db),
    admin_user = Depends(get_current_admin_user)
):
    """
    Retrieve all notifications sorted by newest first.
    If database notifications table is empty, auto-seeds notifications from contact & lead records.
    """
    count = db.query(Notification).count()
    if count == 0:
        now_utc = datetime.now(timezone.utc)
        
        # 1. Add recent contact messages
        recent_contacts = db.query(ContactMessage).order_by(ContactMessage.created_at.desc()).limit(5).all()
        for msg in recent_contacts:
            db.add(Notification(
                title="New Contact Inquiry",
                message=f"{msg.name or 'Visitor'}: \"{msg.message[:55] + '...' if msg.message and len(msg.message) > 55 else (msg.message or 'New message')}\"",
                type="inquiry",
                read=False,
                link="/admin/dashboard/contacts",
                created_at=msg.created_at or now_utc
            ))
            
        # 2. Add recent inbound leads
        recent_leads = db.query(Lead).order_by(Lead.created_at.desc()).limit(5).all()
        for lead in recent_leads:
            db.add(Notification(
                title="New Inbound Lead",
                message=f"{lead.name or 'Prospect'} requested services ({lead.company or 'Direct Inbound'}).",
                type="lead",
                read=False,
                link="/admin/dashboard/leads",
                created_at=lead.created_at or now_utc
            ))
            
        # 3. Add system engine notifications
        db.add(Notification(
            title="CRM Engine Synchronized",
            message="PostgreSQL/SQLite database connected • All notification services online.",
            type="system",
            read=True,
            link="/admin/dashboard",
            created_at=now_utc
        ))
        
        db.add(Notification(
            title="Autonomous Email Worker",
            message="Email automation standby mode • IMAP listener active.",
            type="email",
            read=False,
            link="/admin/dashboard/email-outreach",
            created_at=now_utc
        ))
        
        db.commit()

    return db.query(Notification).order_by(Notification.created_at.desc()).limit(50).all()

@router.post("/", response_model=NotificationOut, status_code=status.HTTP_201_CREATED)
def create_notification(
    notif_in: NotificationCreate,
    db: Session = Depends(get_db),
    admin_user = Depends(get_current_admin_user)
):
    """
    Create a new notification record in the database.
    """
    notif = Notification(
        title=notif_in.title,
        message=notif_in.message,
        type=notif_in.type or "system",
        read=notif_in.read or False,
        link=notif_in.link or "/admin/dashboard",
        created_at=datetime.now(timezone.utc)
    )
    db.add(notif)
    db.commit()
    db.refresh(notif)
    return notif

@router.post("/test", response_model=NotificationOut, status_code=status.HTTP_201_CREATED)
def trigger_test_notification(
    db: Session = Depends(get_db),
    admin_user = Depends(get_current_admin_user)
):
    """
    Trigger a live backend test notification into the database.
    """
    import random
    companies = ["Acme Corp", "Apex Innovations", "Starlight Media", "Vanguard Tech", "Quantum Labs"]
    comp = random.choice(companies)
    
    notif = Notification(
        title=f"⚡ Live Test: Inquiry from {comp}",
        message="Backend notification trigger active! Inbound service request generated.",
        type="inquiry",
        read=False,
        link="/admin/dashboard/leads",
        created_at=datetime.now(timezone.utc)
    )
    db.add(notif)
    db.commit()
    db.refresh(notif)
    return notif

@router.put("/{notif_id}/read", response_model=NotificationOut)
def mark_notification_read(
    notif_id: int,
    db: Session = Depends(get_db),
    admin_user = Depends(get_current_admin_user)
):
    """
    Mark a specific notification as read in database.
    """
    notif = db.query(Notification).filter(Notification.id == notif_id).first()
    if not notif:
        raise HTTPException(status_code=404, detail="Notification not found")
    notif.read = True
    db.commit()
    db.refresh(notif)
    return notif

@router.put("/read-all")
def mark_all_notifications_read(
    db: Session = Depends(get_db),
    admin_user = Depends(get_current_admin_user)
):
    """
    Mark all unread notifications as read in database.
    """
    updated_count = db.query(Notification).filter(Notification.read == False).update({"read": True})
    db.commit()
    return {"message": f"Successfully marked {updated_count} notifications as read.", "count": updated_count}

@router.delete("/clear")
def clear_all_notifications(
    db: Session = Depends(get_db),
    admin_user = Depends(get_current_admin_user)
):
    """
    Clear/delete all notifications from database.
    """
    num_deleted = db.query(Notification).delete()
    db.commit()
    return {"message": f"Successfully cleared {num_deleted} notifications."}
