from typing import List, Optional
from datetime import datetime, timezone
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from pydantic import BaseModel

from app.dependencies.database import get_db
from app.dependencies.auth import get_current_admin_user
from app.repositories.contact import contact_repo
from app.schemas.contact import ContactCreate, ContactUpdate, ContactOut
from app.models.contact import ContactMessage
from app.models.email_message import EmailMessage
from app.models.notification import Notification
from app.services.smtp_service import smtp_sender
from app.core.config import settings

router = APIRouter()

class SendContactReplyRequest(BaseModel):
    subject: str
    body: str

@router.post("/", response_model=ContactOut, status_code=status.HTTP_201_CREATED)
def create_contact(
    contact_in: ContactCreate,
    db: Session = Depends(get_db)
):
    """
    Submit a new website contact message (Public endpoint).
    Triggers automated thank-you email to the inquirer, records initial email message thread, and pushes DB notification.
    """
    contact = contact_repo.create(db, obj_in=contact_in.model_dump())
    now_utc = datetime.now(timezone.utc)
    sender_email = getattr(settings, "SMTP_FROM_EMAIL", "info@nexora.ai")

    # 1. Automated Thank-You & Receipt Confirmation Email
    auto_subject = f"Thank you for choosing Nexora AI - Inquiry Received ({contact.subject or 'Project Request'})"
    auto_body = f"""Hi {contact.name},

Thank you for choosing Nexora AI! We have successfully received your inquiry regarding "{contact.subject or 'your project requirements'}".

Our engineering and strategy team is reviewing your request and we will connect with you shortly for further work and scheduling an initial strategy session.

Your Submitted Inquiry Details:
• Name: {contact.name}
• Email: {contact.email}
• Subject: {contact.subject or 'General Inquiry'}
• Message:
{contact.message}

Warm regards,
The Nexora AI Engineering Team
https://nexora-meet-b4aa.vercel.app/
"""

    try:
        success, error_msg = smtp_sender.send_email(
            recipient_email=contact.email,
            subject=auto_subject,
            body=auto_body,
            is_html=True
        )
        contact.auto_reply_sent = True
        contact.auto_reply_status = "sent" if success else "failed"

        # Record auto-reply in EmailMessage thread table
        auto_msg = EmailMessage(
            contact_id=contact.id,
            message_type="AUTO_REPLY",
            subject=auto_subject,
            body=auto_body,
            recipient_email=contact.email,
            sender_email=sender_email,
            status="SENT" if success else "FAILED",
            error_message=error_msg,
            created_at=now_utc,
            sent_at=now_utc if success else None
        )
        db.add(auto_msg)
        db.commit()
    except Exception as email_err:
        print("Failed to dispatch automated contact thank-you email:", email_err)

    # 2. Trigger real-time Notification for Admin Inbox
    try:
        msg_text = contact.message or ""
        msg_snippet = msg_text[:50] + "..." if len(msg_text) > 50 else (msg_text or "New contact message")
        notif = Notification(
            title="New Website Inquiry",
            message=f"Inquiry from {contact.name} ({contact.email}): \"{msg_snippet}\"",
            type="inquiry",
            read=False,
            link="/admin/dashboard/contacts",
            created_at=now_utc
        )
        db.add(notif)
        db.commit()
    except Exception as notif_err:
        print("Failed to auto-create contact notification:", notif_err)

    db.refresh(contact)
    return contact

@router.get("/", response_model=List[ContactOut])
def read_contacts(
    skip: int = 0,
    limit: int = 100,
    db: Session = Depends(get_db),
    admin_user = Depends(get_current_admin_user)
):
    """
    Get all website contact messages (Admin only).
    """
    return contact_repo.get_multi(db, skip=skip, limit=limit)

@router.get("/{contact_id}/thread")
def get_contact_thread(
    contact_id: int,
    db: Session = Depends(get_db),
    admin_user = Depends(get_current_admin_user)
):
    """
    Retrieve full email exchange thread for a website inquiry (Initial inquiry, auto-reply, and admin responses).
    """
    contact = contact_repo.get(db, id=contact_id)
    if not contact:
        raise HTTPException(status_code=404, detail="Contact message not found.")

    email_msgs = db.query(EmailMessage).filter(
        EmailMessage.contact_id == contact_id
    ).order_by(EmailMessage.created_at.asc()).all()

    thread = [
        {
            "id": 0,
            "type": "INQUIRY",
            "sender": contact.email,
            "recipient": getattr(settings, "SMTP_FROM_EMAIL", "info@nexora.ai"),
            "subject": contact.subject or "Website Inquiry",
            "body": contact.message,
            "timestamp": contact.created_at
        }
    ]

    for m in email_msgs:
        thread.append({
            "id": m.id,
            "type": m.message_type,
            "sender": m.sender_email,
            "recipient": m.recipient_email,
            "subject": m.subject,
            "body": m.body,
            "timestamp": m.created_at
        })

    return {
        "contact_id": contact.id,
        "name": contact.name,
        "email": contact.email,
        "subject": contact.subject,
        "message": contact.message,
        "status": contact.status,
        "auto_reply_sent": contact.auto_reply_sent,
        "thread": thread
    }

@router.post("/{contact_id}/generate-meeting-draft")
async def generate_meeting_draft_for_contact(
    contact_id: int,
    db: Session = Depends(get_db),
    admin_user = Depends(get_current_admin_user)
):
    """
    Generates a tailored 'Thank you for your inquiry, let's arrange a meeting soon' email template for website contacts.
    """
    contact = contact_repo.get(db, id=contact_id)
    if not contact:
        raise HTTPException(status_code=404, detail="Contact message not found.")

    subject = f"Meeting Invitation & Project Review — Nexora AI ({contact.name})"
    body = f"""Hi {contact.name},

Thank you for choosing Nexora AI and submitting your inquiry regarding "{contact.subject or 'your digital project'}".

Our engineering team has reviewed your message:
"{contact.message}"

We would love to arrange a 15-minute strategy call with you to discuss your project requirements in detail and outline the best path forward for further work.

Could you please let us know your preferred date and time for a virtual meeting?

Looking forward to connecting with you soon!

Best regards,
Nexora AI Team
https://nexora-meet-b4aa.vercel.app/
"""

    is_test_mode = getattr(settings, "EMAIL_TEST_MODE", True)
    test_email = getattr(settings, "EMAIL_TEST_RECIPIENT", "") or getattr(settings, "SMTP_FROM_EMAIL", "")

    return {
        "contact_id": contact.id,
        "business_name": contact.name,
        "recipient_email": contact.email,
        "intent": "INTERESTED",
        "subject": subject,
        "body": body,
        "mode": "test" if is_test_mode else "production",
        "test_recipient": test_email if is_test_mode else None
    }

@router.post("/{contact_id}/generate-draft")
async def generate_custom_draft_for_contact(
    contact_id: int,
    db: Session = Depends(get_db),
    admin_user = Depends(get_current_admin_user)
):
    """
    Generates a custom AI response draft addressing the specific website inquiry.
    """
    contact = contact_repo.get(db, id=contact_id)
    if not contact:
        raise HTTPException(status_code=404, detail="Contact message not found.")

    subject = f"Re: {contact.subject or 'Your Inquiry to Nexora AI'}"
    body = f"""Hi {contact.name},

Thank you for reaching out to Nexora AI regarding "{contact.subject or 'your inquiry'}".

We have carefully evaluated your request:
"{contact.message}"

Our team specializes in autonomous AI agents, web applications, custom workflow automations, and digital services. We are fully equipped to assist you with your project requirements.

Please let us know if you would like us to prepare a custom proposal or schedule a preliminary call.

Best regards,
Nexora AI Engineering Team
https://nexora-meet-b4aa.vercel.app/
"""

    is_test_mode = getattr(settings, "EMAIL_TEST_MODE", True)
    test_email = getattr(settings, "EMAIL_TEST_RECIPIENT", "") or getattr(settings, "SMTP_FROM_EMAIL", "")

    return {
        "contact_id": contact.id,
        "business_name": contact.name,
        "recipient_email": contact.email,
        "intent": "INQUIRY",
        "subject": subject,
        "body": body,
        "mode": "test" if is_test_mode else "production",
        "test_recipient": test_email if is_test_mode else None
    }

@router.post("/{contact_id}/send-custom")
def send_custom_reply_to_contact(
    contact_id: int,
    payload: SendContactReplyRequest,
    db: Session = Depends(get_db),
    admin_user = Depends(get_current_admin_user)
):
    """
    Admin approves and dispatches a tailored email reply to a website inquirer.
    Supports Test Mode vs Production Mode and records the exchange in EmailMessage.
    """
    contact = contact_repo.get(db, id=contact_id)
    if not contact:
        raise HTTPException(status_code=404, detail="Contact message not found.")

    sender_email = getattr(settings, "SMTP_FROM_EMAIL", "info@nexora.ai")
    is_test_mode = getattr(settings, "EMAIL_TEST_MODE", True)
    test_target_email = getattr(settings, "EMAIL_TEST_RECIPIENT", "") or sender_email

    actual_recipient = test_target_email if is_test_mode else contact.email
    subject_to_send = f"[TEST MODE -> {contact.email}] {payload.subject}" if is_test_mode else payload.subject

    # Send email via SMTP / Gmail API
    success, error_msg = smtp_sender.send_email(
        recipient_email=actual_recipient,
        subject=subject_to_send,
        body=payload.body,
        is_html=True
    )

    if not success:
        raise HTTPException(status_code=500, detail=f"Failed to send email: {error_msg}")

    now_utc = datetime.now(timezone.utc)

    # Save to EmailMessage DB table
    new_msg = EmailMessage(
        contact_id=contact.id,
        message_type="ADMIN_REPLY",
        subject=payload.subject,
        body=payload.body,
        recipient_email=contact.email,
        sender_email=sender_email,
        status="SENT",
        sent_at=now_utc,
        created_at=now_utc
    )
    db.add(new_msg)

    # Update Contact Status
    contact.status = "replied"
    db.commit()

    return {
        "status": "success",
        "contact_id": contact.id,
        "mode": "test" if is_test_mode else "production",
        "sent_to": actual_recipient,
        "message_id": new_msg.id
    }

@router.put("/{contact_id}", response_model=ContactOut)
def update_contact(
    contact_id: int,
    contact_in: ContactUpdate,
    db: Session = Depends(get_db),
    admin_user = Depends(get_current_admin_user)
):
    """
    Update a contact message status (Admin only).
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

