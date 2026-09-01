from typing import List, Optional
from datetime import datetime, timezone, timedelta
from fastapi import APIRouter, Depends, HTTPException, status, Query, WebSocket, WebSocketDisconnect
from sqlalchemy.orm import Session
from sqlalchemy import func, or_, case

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
    email_worker.is_sender_active = not email_worker.is_sender_active
    status_str = "started" if email_worker.is_sender_active else "paused"
    if email_worker.is_sender_active:
        email_worker.wake_up()
    await email_worker.add_log(f"Auto-Sender process was manually {status_str} by administrator.")
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
    
    # 2. Fetch pending leads that don't have EmailMessage logs yet
    pending_leads = db.query(ScrapedLead).filter(
        ScrapedLead.email_status == "pending",
        ScrapedLead.unsubscribe == False,
        ScrapedLead.bounced == False,
        ScrapedLead.bussiness_email.isnot(None),
        ScrapedLead.bussiness_email != ""
    ).order_by(ScrapedLead.created_at.desc()).all()
    
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
    """List all leads that have replied along with their categorized intent (Admin only)."""
    leads_replied = db.query(ScrapedLead).filter(
        ScrapedLead.reply_status != "unprocessed"
    ).order_by(ScrapedLead.last_email_at.desc()).all()
    
    output = []
    for lead in leads_replied:
        # Fetch the thread
        messages = db.query(EmailMessage).filter(
            EmailMessage.lead_id == lead.id
        ).order_by(EmailMessage.created_at.asc()).all()
        
        thread = [{
            "id": m.id,
            "type": m.message_type,
            "subject": m.subject,
            "body": m.body,
            "sender": m.sender_email,
            "recipient": m.recipient_email,
            "timestamp": m.created_at
        } for m in messages]
        
        output.append({
            "lead_id": lead.id,
            "business_name": lead.bussiness_name,
            "email": lead.bussiness_email,
            "intent": lead.reply_status,
            "last_contact": lead.last_email_at,
            "thread": thread
        })
    return output

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

    sent_by_day_query = db.query(
        func.strftime("%Y-%m-%d", EmailMessage.sent_at).label("day"),
        func.count(EmailMessage.id).label("count")
    ).filter(
        EmailMessage.status == "SENT",
        EmailMessage.sent_at >= seven_days_ago
    ).group_by("day").all()
    sent_by_day = [{"day": r[0], "count": r[1]} for r in sent_by_day_query]

    replies_by_day_query = db.query(
        func.strftime("%Y-%m-%d", EmailMessage.reply_received_at).label("day"),
        func.count(EmailMessage.id).label("count")
    ).filter(
        EmailMessage.message_type == "REPLY",
        EmailMessage.reply_received_at >= seven_days_ago
    ).group_by("day").all()
    replies_by_day = [{"day": r[0], "count": r[1]} for r in replies_by_day_query]

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


