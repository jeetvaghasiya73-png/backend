from typing import List, Optional
from datetime import datetime, timezone, timedelta
from fastapi import APIRouter, Depends, HTTPException, status, Query, WebSocket, WebSocketDisconnect
from sqlalchemy.orm import Session
from sqlalchemy import func, or_, case
from pydantic import BaseModel

from app.dependencies.database import get_db
from app.dependencies.auth import get_current_admin_user
from app.models.campaign import Campaign
from app.models.email_message import EmailMessage
from app.models.followup import FollowUp
from app.models.scraped_lead import ScrapedLead
from app.schemas.email import (
    CampaignCreate,
    CampaignUpdate,
    CampaignOut,
    EmailMessageOut,
    FollowUpOut,
    EmailAnalyticsOut
)
from app.schemas.scraped_lead import ScrapedLeadOut
from app.services.smtp_service import smtp_sender
from app.services.email_worker import email_worker

router = APIRouter()

@router.get("/sender/status")
def get_sender_status(admin_user = Depends(get_current_admin_user)):
    """Retrieve the current autonomous email sender process status."""
    return {"is_active": email_worker.is_sender_active}

@router.post("/sender/toggle")
async def toggle_sender_status(admin_user = Depends(get_current_admin_user)):
    """Toggle the autonomous email sender process status (Start / Pause)."""
    new_status = not email_worker.is_sender_active
    await email_worker.set_sender_active(new_status)
    return {"is_active": email_worker.is_sender_active}

@router.get("/sender/activity")
def get_sender_activity(admin_user = Depends(get_current_admin_user)):
    """Retrieve the current autonomous email sender's log history and process status."""
    return {
        "is_active": email_worker.is_sender_active,
        "status": email_worker.status,
        "current_lead": email_worker.current_lead,
        "logs": email_worker.logs
    }

@router.websocket("/sender/ws")
async def sender_websocket_endpoint(websocket: WebSocket):
    await websocket.accept()
    email_worker.active_connections.append(websocket)
    try:
        # Send initial state immediately
        payload = {
            "is_active": email_worker.is_sender_active,
            "status": email_worker.status,
            "current_lead": email_worker.current_lead,
            "logs": email_worker.logs
        }
        await websocket.send_json(payload)
        while True:
            # Keep connection alive; discard any client messages
            await websocket.receive_text()
    except WebSocketDisconnect:
        pass
    finally:
        if websocket in email_worker.active_connections:
            email_worker.active_connections.remove(websocket)

# --- Campaigns Endpoints ---

@router.get("/campaigns", response_model=List[CampaignOut])
def get_campaigns(
    db: Session = Depends(get_db),
    admin_user = Depends(get_current_admin_user)
):
    """List all email outreach campaigns (Admin only)."""
    return db.query(Campaign).order_by(Campaign.created_at.desc()).all()

@router.post("/campaigns", response_model=CampaignOut)
def create_campaign(
    campaign_in: CampaignCreate,
    db: Session = Depends(get_db),
    admin_user = Depends(get_current_admin_user)
):
    """Create a new outreach campaign (Admin only)."""
    campaign = Campaign(**campaign_in.model_dump())
    db.add(campaign)
    db.commit()
    db.refresh(campaign)
    return campaign

@router.get("/campaigns/{id}", response_model=CampaignOut)
def get_campaign(
    id: int,
    db: Session = Depends(get_db),
    admin_user = Depends(get_current_admin_user)
):
    """Get details of a specific campaign (Admin only)."""
    campaign = db.query(Campaign).filter(Campaign.id == id).first()
    if not campaign:
        raise HTTPException(status_code=404, detail="Campaign not found.")
    return campaign

@router.post("/campaigns/{id}/start")
def start_campaign(
    id: int,
    db: Session = Depends(get_db),
    admin_user = Depends(get_current_admin_user)
):
    """Start campaign, select target leads and queue initial emails (Admin only)."""
    campaign = db.query(Campaign).filter(Campaign.id == id).first()
    if not campaign:
        raise HTTPException(status_code=404, detail="Campaign not found.")
    
    campaign.status = "RUNNING"
    campaign.started_at = datetime.now(timezone.utc)
    
    # Select target leads matching the campaign filters that aren't already in another campaign
    query = db.query(ScrapedLead).filter(
        ScrapedLead.campaign_id == None,
        ScrapedLead.unsubscribe == False,
        ScrapedLead.bounced == False
    )
    if campaign.target_city:
        query = query.filter(ScrapedLead.scraped_city.ilike(f"%{campaign.target_city}%"))
    if campaign.target_service:
        query = query.filter(ScrapedLead.scraped_service.ilike(f"%{campaign.target_service}%"))
        
    leads = query.all()
    queued_count = 0
    for lead in leads:
        lead.campaign_id = campaign.id
        lead.email_status = "pending"
        queued_count += 1
        
    db.commit()
    return {"message": f"Campaign started. Queued {queued_count} leads for personalization."}

@router.post("/campaigns/{id}/pause")
def pause_campaign(
    id: int,
    db: Session = Depends(get_db),
    admin_user = Depends(get_current_admin_user)
):
    """Pause an active campaign (Admin only)."""
    campaign = db.query(Campaign).filter(Campaign.id == id).first()
    if not campaign:
        raise HTTPException(status_code=404, detail="Campaign not found.")
    campaign.status = "PAUSED"
    campaign.paused_at = datetime.now(timezone.utc)
    db.commit()
    return {"message": "Campaign paused successfully."}

@router.post("/campaigns/{id}/resume")
def resume_campaign(
    id: int,
    db: Session = Depends(get_db),
    admin_user = Depends(get_current_admin_user)
):
    """Resume a paused campaign (Admin only)."""
    campaign = db.query(Campaign).filter(Campaign.id == id).first()
    if not campaign:
        raise HTTPException(status_code=404, detail="Campaign not found.")
    campaign.status = "RUNNING"
    campaign.paused_at = None
    db.commit()
    return {"message": "Campaign resumed successfully."}

@router.post("/campaigns/{id}/stop")
def stop_campaign(
    id: int,
    db: Session = Depends(get_db),
    admin_user = Depends(get_current_admin_user)
):
    """Stop/Cancel a campaign (Admin only)."""
    campaign = db.query(Campaign).filter(Campaign.id == id).first()
    if not campaign:
        raise HTTPException(status_code=404, detail="Campaign not found.")
    campaign.status = "PAUSED" # Keep status paused/cancelled
    
    # Cancel all pending leads in queue
    db.query(ScrapedLead).filter(
        ScrapedLead.campaign_id == campaign.id,
        ScrapedLead.email_status == "pending"
    ).update({"email_status": "pending", "campaign_id": None})
    
    # Cancel scheduled followups
    db.query(FollowUp).filter(
        FollowUp.campaign_id == campaign.id,
        FollowUp.status == "SCHEDULED"
    ).update({"status": "CANCELLED", "reason": "Campaign stopped by administrator"})
    
    db.commit()
    return {"message": "Campaign stopped. All pending outreach and scheduled followups cancelled."}

# --- Queue & Messages Endpoints ---

@router.get("/queue", response_model=List[EmailMessageOut])
def get_queue(
    db: Session = Depends(get_db),
    admin_user = Depends(get_current_admin_user)
):
    """Get current outgoing message queue logs (Admin only)."""
    # 1. Fetch real campaign queued/draft/sending emails
    real_queue = db.query(EmailMessage).filter(
        EmailMessage.status.in_(["DRAFT", "QUEUED", "SENDING"])
    ).order_by(EmailMessage.created_at.desc()).all()
    
    # 2. Fetch pending leads that don't have EmailMessage logs yet (limit to top 150)
    pending_leads = db.query(ScrapedLead).filter(
        ScrapedLead.email_status == "pending",
        ScrapedLead.unsubscribe == False,
        ScrapedLead.bounced == False,
        ScrapedLead.bussiness_email.isnot(None),
        ScrapedLead.bussiness_email != ""
    ).order_by(ScrapedLead.created_at.desc()).limit(150).all()
    
    already_in_msg = {m.lead_id for m in real_queue}
    
    # Construct virtual EmailMessageOut records for pending leads
    virtual_queue = []
    from app.core.config import settings
    sender_email = getattr(settings, "SMTP_FROM_EMAIL", "info@nexora.ai")
    
    for lead in pending_leads:
        if lead.id in already_in_msg:
            continue
        virtual_queue.append(
            EmailMessage(
                id=lead.id * -100, # Unique virtual ID mapping
                campaign_id=lead.campaign_id,
                lead_id=lead.id,
                message_type="INITIAL",
                subject="AI Personalization Pending",
                body="Email template personalization will be generated autonomously on dispatch.",
                recipient_email=lead.bussiness_email,
                sender_email=sender_email,
                status="QUEUED",
                created_at=lead.created_at
            )
        )
        
    return real_queue + virtual_queue

@router.get("/messages", response_model=List[EmailMessageOut])
def get_messages(
    db: Session = Depends(get_db),
    admin_user = Depends(get_current_admin_user)
):
    """Get full outreach message logs history (Admin only)."""
    return db.query(EmailMessage).order_by(EmailMessage.created_at.desc()).limit(100).all()

@router.post("/messages/{id}/retry")
def retry_failed_message(
    id: int,
    db: Session = Depends(get_db),
    admin_user = Depends(get_current_admin_user)
):
    """Retry a failed email message send (Admin only)."""
    msg = db.query(EmailMessage).filter(EmailMessage.id == id).first()
    if not msg:
        raise HTTPException(status_code=404, detail="Email message not found.")
    
    msg.status = "QUEUED"
    msg.error_message = None
    
    # Update lead status
    lead = db.query(ScrapedLead).filter(ScrapedLead.id == msg.lead_id).first()
    if lead:
        lead.email_status = "pending"
        lead.email_error = None
        
    db.commit()
    return {"message": "Email queued for retry successfully."}

@router.post("/messages/{id}/approve")
def approve_draft_message(
    id: int,
    db: Session = Depends(get_db),
    admin_user = Depends(get_current_admin_user)
):
    """Approve a draft AI generated email for manual sending (Admin only)."""
    msg = db.query(EmailMessage).filter(EmailMessage.id == id).first()
    if not msg:
        raise HTTPException(status_code=404, detail="Email message not found.")
    
    if msg.status != "DRAFT":
        raise HTTPException(status_code=400, detail="Only messages in DRAFT status can be approved.")

    success, error_msg = smtp_sender.send_email(
        recipient_email=msg.recipient_email,
        subject=msg.subject,
        body=msg.body,
        is_html=True
    )

    if success:
        now_utc = datetime.now(timezone.utc)
        msg.status = "SENT"
        msg.sent_at = now_utc
        
        lead = db.query(ScrapedLead).filter(ScrapedLead.id == msg.lead_id).first()
        if lead:
            lead.email_status = "sent"
            lead.email_sent_at = now_utc
            lead.last_email_at = now_utc
    else:
        msg.status = "FAILED"
        msg.error_message = error_msg
        lead = db.query(ScrapedLead).filter(ScrapedLead.id == msg.lead_id).first()
        if lead:
            lead.email_status = "failed"
            lead.email_error = error_msg
            
    db.commit()
    return {"status": msg.status, "error": msg.error_message}

# --- Conversations Endpoints ---

@router.get("/conversations")
def get_conversations(
    db: Session = Depends(get_db),
    admin_user = Depends(get_current_admin_user)
):
    """List all leads that have replied along with their categorized intent (Admin only). Batched & optimized."""
    leads_replied = db.query(ScrapedLead).filter(
        ScrapedLead.reply_status != "unprocessed"
    ).order_by(ScrapedLead.last_email_at.desc()).all()
    
    if not leads_replied:
        return []

    lead_ids = [l.id for l in leads_replied]

    # Batch query all email messages across all replied leads in ONE single database query
    all_messages = db.query(EmailMessage).filter(
        EmailMessage.lead_id.in_(lead_ids)
    ).order_by(EmailMessage.created_at.asc()).all()

    from collections import defaultdict
    thread_map = defaultdict(list)
    for m in all_messages:
        thread_map[m.lead_id].append({
            "id": m.id,
            "type": m.message_type,
            "subject": m.subject,
            "body": m.body,
            "sender": m.sender_email,
            "recipient": m.recipient_email,
            "timestamp": m.created_at
        })

    output = []
    for lead in leads_replied:
        output.append({
            "lead_id": lead.id,
            "business_name": lead.bussiness_name,
            "email": lead.bussiness_email,
            "intent": lead.reply_status,
            "last_contact": lead.last_email_at,
            "thread": thread_map[lead.id]
        })
    return output


class SendCustomReplyRequest(BaseModel):
    subject: str
    body: str

@router.post("/conversations/{lead_id}/generate-draft")
async def generate_reply_draft_for_lead(
    lead_id: int,
    db: Session = Depends(get_db),
    admin_user = Depends(get_current_admin_user)
):
    """
    Step 2 & 3: Identify lead context and generate a tailored AI email draft proposal for admin approval.
    """
    lead = db.query(ScrapedLead).filter(ScrapedLead.id == lead_id).first()
    if not lead:
        raise HTTPException(status_code=404, detail="Lead not found.")

    # Fetch thread history
    messages = db.query(EmailMessage).filter(
        EmailMessage.lead_id == lead_id
    ).order_by(EmailMessage.created_at.asc()).all()

    thread_data = [{
        "id": m.id,
        "type": m.message_type,
        "sender": m.sender_email,
        "recipient": m.recipient_email,
        "subject": m.subject,
        "body": m.body,
        "timestamp": m.created_at
    } for m in messages]

    from app.services.ai_email import ai_email_service
    draft = await ai_email_service.generate_ai_reply_draft(lead, thread_data)

    from app.core.config import settings
    is_test_mode = getattr(settings, "EMAIL_TEST_MODE", True)
    test_email = getattr(settings, "SMTP_TO_TEST_EMAIL", "") or getattr(settings, "SMTP_FROM_EMAIL", "")

    return {
        "lead_id": lead.id,
        "business_name": lead.bussiness_name,
        "recipient_email": lead.bussiness_email,
        "intent": lead.reply_status or "INTERESTED",
        "scraped_city": lead.scraped_city,
        "scraped_service": lead.scraped_service or lead.category,
        "subject": draft.get("subject", f"Re: Growth Discussion for {lead.bussiness_name}"),
        "body": draft.get("body", ""),
        "mode": "test" if is_test_mode else "production",
        "test_recipient": test_email if is_test_mode else None,
        "thread": thread_data
    }


@router.post("/conversations/{lead_id}/generate-meeting-draft")
async def generate_meeting_draft_for_lead(
    lead_id: int,
    db: Session = Depends(get_db),
    admin_user = Depends(get_current_admin_user)
):
    """
    Generates a tailored 'Thank you for your inquiry, let's arrange a meeting soon' email template for admin approval.
    """
    lead = db.query(ScrapedLead).filter(ScrapedLead.id == lead_id).first()
    if not lead:
        raise HTTPException(status_code=404, detail="Lead not found.")

    # Fetch thread history from EmailMessage or lead.email_message
    messages = db.query(EmailMessage).filter(
        EmailMessage.lead_id == lead_id
    ).order_by(EmailMessage.created_at.asc()).all()

    thread_data = [{
        "id": m.id,
        "type": m.message_type,
        "sender": m.sender_email,
        "recipient": m.recipient_email,
        "subject": m.subject,
        "body": m.body,
        "timestamp": m.created_at
    } for m in messages]

    from app.services.ai_email import ai_email_service
    draft = await ai_email_service.generate_meeting_email_draft(lead, thread_data)

    from app.core.config import settings
    is_test_mode = getattr(settings, "EMAIL_TEST_MODE", True)
    test_email = getattr(settings, "SMTP_TO_TEST_EMAIL", "") or getattr(settings, "SMTP_FROM_EMAIL", "")

    return {
        "lead_id": lead.id,
        "business_name": lead.bussiness_name,
        "recipient_email": lead.bussiness_email,
        "intent": lead.reply_status or "INTERESTED",
        "scraped_city": lead.scraped_city,
        "scraped_service": lead.scraped_service or lead.category,
        "subject": draft.get("subject", f"Thank you for your inquiry — Let's arrange a meeting for {lead.bussiness_name}"),
        "body": draft.get("body", ""),
        "mode": "test" if is_test_mode else "production",
        "test_recipient": test_email if is_test_mode else None,
        "thread": thread_data
    }


@router.post("/conversations/{lead_id}/send-custom")
def send_custom_reply_to_lead(
    lead_id: int,
    payload: SendCustomReplyRequest,
    db: Session = Depends(get_db),
    admin_user = Depends(get_current_admin_user)
):
    """
    Step 4 & 5: Admin approves and sends the tailored email draft directly to the business via SMTP.
    Supports Test Mode (sends to configured test email) vs Production Mode (sends to actual business).
    """
    lead = db.query(ScrapedLead).filter(ScrapedLead.id == lead_id).first()
    if not lead:
        raise HTTPException(status_code=404, detail="Lead not found.")

    if not lead.bussiness_email:
        raise HTTPException(status_code=400, detail="Lead does not have a valid recipient email address.")

    from app.core.config import settings
    from app.services.smtp_service import smtp_sender
    from app.services.email_worker import sync_lead_email_messages

    sender_email = getattr(settings, "SMTP_FROM_EMAIL", "info@nexora.ai")
    
    # Check Test Mode vs Production Mode
    is_test_mode = getattr(settings, "EMAIL_TEST_MODE", True)
    test_target_email = getattr(settings, "SMTP_TO_TEST_EMAIL", "") or sender_email

    actual_recipient = test_target_email if is_test_mode else lead.bussiness_email
    subject_to_send = f"[TEST MODE -> {lead.bussiness_email}] {payload.subject}" if is_test_mode else payload.subject

    # Send email via SMTP
    success, error_msg = smtp_sender.send_email(
        recipient_email=actual_recipient,
        subject=subject_to_send,
        body=payload.body,
        is_html=False
    )

    if not success:
        raise HTTPException(status_code=500, detail=f"Failed to send email: {error_msg}")

    now_utc = datetime.now(timezone.utc)

    # Save to EmailMessage DB table
    new_msg = EmailMessage(
        campaign_id=lead.campaign_id,
        lead_id=lead.id,
        message_type="AUTO_REPLY",
        subject=payload.subject,
        body=payload.body,
        sender_email=sender_email,
        recipient_email=lead.bussiness_email,
        status="SENT",
        sent_at=now_utc
    )
    db.add(new_msg)
    db.commit()
    db.refresh(new_msg)

    # Sync to scraped_leads.email_message JSON column
    sync_lead_email_messages(db, lead)

    # Update lead status
    lead.last_email_at = now_utc
    lead.email_status = "sent"

    db.commit()

    return {
        "status": "success",
        "mode": "test" if is_test_mode else "production",
        "message_id": new_msg.id,
        "sent_to": actual_recipient,
        "target_business_email": lead.bussiness_email,
        "sent_at": new_msg.sent_at
    }


# --- Analytics Endpoint ---

@router.get("/analytics", response_model=EmailAnalyticsOut)
def get_email_analytics(
    db: Session = Depends(get_db),
    admin_user = Depends(get_current_admin_user)
):
    """Return outreach performance analytics (Admin only). Optimized with batch queries."""
    # 1. Batch all EmailMessage counts in a single query using CASE
    msg_stats = db.query(
        func.sum(case((EmailMessage.status == "SENT", 1), else_=0)).label("total_sent"),
        func.sum(case((EmailMessage.status.in_(["QUEUED", "SENDING"]), 1), else_=0)).label("total_queued_msgs"),
        func.sum(case((EmailMessage.status == "FAILED", 1), else_=0)).label("total_failed"),
        func.sum(case((
            (EmailMessage.message_type == "FOLLOW_UP") & (EmailMessage.status == "SENT"),
            1
        ), else_=0)).label("total_followups"),
    ).first()

    # 2. Batch all ScrapedLead counts in a single query using CASE
    lead_stats = db.query(
        func.sum(case((
            (ScrapedLead.bussiness_email.isnot(None)) & (ScrapedLead.bussiness_email != ""),
            1
        ), else_=0)).label("total_leads"),
        func.sum(case((
            (ScrapedLead.email_status == "pending") &
            (ScrapedLead.unsubscribe == False) &
            (ScrapedLead.bounced == False) &
            (ScrapedLead.bussiness_email.isnot(None)) &
            (ScrapedLead.bussiness_email != ""),
            1
        ), else_=0)).label("pending_leads"),
        func.sum(case((ScrapedLead.reply_status != "unprocessed", 1), else_=0)).label("total_replied"),
        func.sum(case((ScrapedLead.reply_status == "interested", 1), else_=0)).label("total_interested"),
        func.sum(case((ScrapedLead.unsubscribe == True, 1), else_=0)).label("total_unsubscribed"),
    ).first()

    total_campaigns = db.query(func.count(Campaign.id)).scalar() or 0
    total_sent = int(msg_stats.total_sent or 0)
    total_queued = int(msg_stats.total_queued_msgs or 0) + int(lead_stats.pending_leads or 0)

    # 3. Timeline calculations (grouped by day) - last 7 days only
    now = datetime.now(timezone.utc)
    seven_days_ago = now - timedelta(days=7)

    # Dialect-aware date formatting (PostgreSQL uses to_char, SQLite uses strftime)
    dialect_name = db.bind.dialect.name if (db.bind and hasattr(db.bind, "dialect")) else "sqlite"
    if dialect_name == "postgresql":
        sent_date_expr = func.to_char(EmailMessage.sent_at, "YYYY-MM-DD")
        reply_date_expr = func.to_char(EmailMessage.reply_received_at, "YYYY-MM-DD")
    else:
        sent_date_expr = func.strftime("%Y-%m-%d", EmailMessage.sent_at)
        reply_date_expr = func.strftime("%Y-%m-%d", EmailMessage.reply_received_at)

    sent_by_day_query = db.query(
        sent_date_expr.label("day"),
        func.count(EmailMessage.id).label("count")
    ).filter(
        EmailMessage.status == "SENT",
        EmailMessage.sent_at >= seven_days_ago
    ).group_by(sent_date_expr).all()
    sent_by_day = [{"day": str(r[0]), "count": r[1]} for r in sent_by_day_query]

    replies_by_day_query = db.query(
        reply_date_expr.label("day"),
        func.count(EmailMessage.id).label("count")
    ).filter(
        EmailMessage.message_type == "REPLY",
        EmailMessage.reply_received_at >= seven_days_ago
    ).group_by(reply_date_expr).all()
    replies_by_day = [{"day": str(r[0]), "count": r[1]} for r in replies_by_day_query]

    # 4. Category analysis
    category_perf_query = db.query(
        ScrapedLead.scraped_service,
        func.count(ScrapedLead.id).label("sent"),
        func.sum(case((ScrapedLead.reply_status != "unprocessed", 1), else_=0)).label("replied")
    ).group_by(ScrapedLead.scraped_service).all()

    category_performance = [{
        "category": r[0] or "General Business",
        "sent": r[1],
        "replied": int(r[2] or 0)
    } for r in category_perf_query]

    return EmailAnalyticsOut(
        total_campaigns=total_campaigns,
        total_leads=int(lead_stats.total_leads or 0),
        total_sent=total_sent,
        total_queued=total_queued,
        total_failed=int(msg_stats.total_failed or 0),
        total_replied=int(lead_stats.total_replied or 0),
        total_interested=int(lead_stats.total_interested or 0),
        total_unsubscribed=int(lead_stats.total_unsubscribed or 0),
        total_followups=int(msg_stats.total_followups or 0),
        sent_by_day=sent_by_day,
        replies_by_day=replies_by_day,
        category_performance=category_performance
    )

@router.get("/sender/settings")
def get_sender_settings(
    db: Session = Depends(get_db),
    admin_user = Depends(get_current_admin_user)
):
    """Retrieve the global cold email follow-up settings (based on default campaign)."""
    campaign = db.query(Campaign).filter(Campaign.name == "Default Autonomous Outreach").first()
    if not campaign:
        campaign = Campaign(
            name="Default Autonomous Outreach",
            description="Default system campaign for autonomous cold outreach follow-ups.",
            status="RUNNING",
            followup_enabled=True,
            followup_interval_days=3,
            max_followups=3,
            email_template="Pitch cold outreach"
        )
        db.add(campaign)
        db.commit()
        db.refresh(campaign)
    return {
        "followup_enabled": campaign.followup_enabled,
        "followup_interval_days": campaign.followup_interval_days,
        "max_followups": campaign.max_followups,
        "delay_min": campaign.delay_min,
        "delay_max": campaign.delay_max
    }

@router.post("/sender/settings")
def update_sender_settings(
    settings_data: dict,
    db: Session = Depends(get_db),
    admin_user = Depends(get_current_admin_user)
):
    """Update the global cold email follow-up settings."""
    campaign = db.query(Campaign).filter(Campaign.name == "Default Autonomous Outreach").first()
    if not campaign:
        campaign = Campaign(
            name="Default Autonomous Outreach",
            description="Default system campaign for autonomous cold outreach follow-ups.",
            status="RUNNING",
            followup_enabled=True,
            followup_interval_days=3,
            max_followups=3,
            email_template="Pitch cold outreach"
        )
        db.add(campaign)
        db.commit()
        db.refresh(campaign)
        
    if "followup_enabled" in settings_data:
        campaign.followup_enabled = bool(settings_data["followup_enabled"])
    if "followup_interval_days" in settings_data:
        campaign.followup_interval_days = int(settings_data["followup_interval_days"])
    if "max_followups" in settings_data:
        campaign.max_followups = int(settings_data["max_followups"])
    if "delay_min" in settings_data:
        campaign.delay_min = int(settings_data["delay_min"])
    if "delay_max" in settings_data:
        campaign.delay_max = int(settings_data["delay_max"])
        
    db.commit()
    return {
        "followup_enabled": campaign.followup_enabled,
        "followup_interval_days": campaign.followup_interval_days,
        "max_followups": campaign.max_followups,
        "delay_min": campaign.delay_min,
        "delay_max": campaign.delay_max
    }

@router.post("/sender/logs/clear")
def clear_sender_logs(
    admin_user = Depends(get_current_admin_user)
):
    """Clear the active logger queue in the outreach worker."""
    email_worker.logs = []
    return {"status": "success"}


class SimulateReplyRequest(BaseModel):
    lead_id: Optional[int] = None
    reply_text: Optional[str] = None
    subject: Optional[str] = None

@router.post("/replies/check")
async def check_email_replies(
    db: Session = Depends(get_db),
    admin_user = Depends(get_current_admin_user)
):
    """
    Check for incoming email replies safely without throwing 500 server errors.
    """
    try:
        from app.core.config import settings
        from app.services.imap_service import imap_service
        
        is_test_mode = settings.EMAIL_TEST_MODE or not (settings.IMAP_HOST and settings.IMAP_USERNAME and settings.IMAP_PASSWORD and "example.com" not in settings.IMAP_HOST)
        
        if not is_test_mode:
            try:
                unread = imap_service.fetch_new_replies()
                processed = await email_worker.process_replies_batch(db, unread) if unread else []
                return {
                    "status": "success",
                    "mode": "production",
                    "imap_host": settings.IMAP_HOST,
                    "new_replies_count": len(processed),
                    "processed_replies": processed
                }
            except Exception as imap_err:
                return {
                    "status": "warning",
                    "mode": "production",
                    "message": f"Could not connect to IMAP inbox ({settings.IMAP_HOST}): {str(imap_err)}",
                    "new_replies_count": 0,
                    "processed_replies": []
                }

        # --- Test Mode Reply Generator ---
        target_lead = db.query(ScrapedLead).filter(
            ScrapedLead.bussiness_email.isnot(None),
            ScrapedLead.bussiness_email != "",
            or_(ScrapedLead.reply_status == "unprocessed", ScrapedLead.reply_status == None)
        ).order_by(ScrapedLead.id.desc()).first()

        if not target_lead:
            target_lead = db.query(ScrapedLead).filter(
                ScrapedLead.bussiness_email.isnot(None),
                ScrapedLead.bussiness_email != ""
            ).first()

        if not target_lead:
            return {
                "status": "success",
                "mode": "test",
                "message": "No leads found in database to simulate test reply for.",
                "new_replies_count": 0,
                "processed_replies": []
            }

        import random
        test_reply_samples = [
            f"Hi Nexora AI team, we received your email regarding {target_lead.bussiness_name}. We are interested in your web development & lead automation services! Could you please share pricing and portfolio details?",
            f"Hello, thanks for reaching out to {target_lead.bussiness_name}. Can you schedule a call with us next week to discuss custom workflow automations?",
            f"Hi! We'd like to learn more about your SEO and Google Maps ranking services for {target_lead.bussiness_name}. What is the timeline for onboarding?"
        ]
        
        sample_text = random.choice(test_reply_samples)
        now_utc = datetime.now(timezone.utc)
        
        simulated_reply = [{
            "sender": target_lead.bussiness_email,
            "sender_name": target_lead.bussiness_name or "Prospect",
            "subject": f"Re: Digital Solutions for {target_lead.bussiness_name}",
            "body": sample_text,
            "received_at": now_utc
        }]

        processed = await email_worker.process_replies_batch(db, simulated_reply)
        
        return {
            "status": "success",
            "mode": "test",
            "message": f"Generated simulated test reply for lead '{target_lead.bussiness_name}' ({target_lead.bussiness_email})",
            "new_replies_count": len(processed),
            "processed_replies": processed
        }
    except Exception as general_err:
        return {
            "status": "error",
            "message": f"Reply checking encountered an exception: {str(general_err)}",
            "new_replies_count": 0,
            "processed_replies": []
        }

@router.post("/replies/simulate")
async def simulate_custom_email_reply(
    payload: SimulateReplyRequest,
    db: Session = Depends(get_db),
    admin_user = Depends(get_current_admin_user)
):
    """
    Manually simulate a prospect email reply to test AI classification, thread state, and auto-reply dispatch.
    """
    target_lead = None
    if payload.lead_id:
        target_lead = db.query(ScrapedLead).filter(ScrapedLead.id == payload.lead_id).first()
    
    if not target_lead:
        target_lead = db.query(ScrapedLead).filter(
            ScrapedLead.bussiness_email.isnot(None),
            ScrapedLead.bussiness_email != ""
        ).order_by(ScrapedLead.id.desc()).first()

    if not target_lead:
        raise HTTPException(status_code=400, detail="No valid lead found in database to simulate email reply.")

    body_text = payload.reply_text or f"Hi! I am interested in Nexora AI digital services for {target_lead.bussiness_name}. Please send pricing."
    subj_text = payload.subject or f"Re: Outreach Opportunity for {target_lead.bussiness_name}"
    now_utc = datetime.now(timezone.utc)

    simulated = [{
        "sender": target_lead.bussiness_email,
        "sender_name": target_lead.bussiness_name or "Prospect",
        "subject": subj_text,
        "body": body_text,
        "received_at": now_utc
    }]

    processed = await email_worker.process_replies_batch(db, simulated)
    return {
        "status": "success",
        "lead_id": target_lead.id,
        "lead_name": target_lead.bussiness_name,
        "lead_email": target_lead.bussiness_email,
        "processed_count": len(processed),
        "processed": processed
    }


