import asyncio
import logging
import random
from datetime import datetime, timezone, timedelta
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.database.session import SessionLocal
from app.models.campaign import Campaign
from app.models.scraped_lead import ScrapedLead
from app.models.email_message import EmailMessage
from app.models.followup import FollowUp
from app.services.smtp_service import smtp_sender
from app.services.ai_email import ai_email_service
from app.services.imap_service import imap_service
from app.core.config import settings


logger = logging.getLogger("email_worker")

class EmailOutreachWorker:
    def __init__(self):
        self._running = False
        self._task = None
        self.is_sender_active = False
        self.status = "idle" # idle, generating, sending, sleeping
        self.current_lead = None # Dict of current lead info
        self.logs = [] # List of logs
        self.active_connections = [] # List of WebSocket connections
        self._wakeup_event = asyncio.Event()

    def wake_up(self):
        """Wake up the worker loop immediately if it is sleeping/polling."""
        try:
            self._wakeup_event.set()
        except Exception:
            pass
        
    async def add_log(self, message: str):
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        formatted = f"[{timestamp}] {message}"
        self.logs.append(formatted)
        if len(self.logs) > 50:
            self.logs.pop(0)
        logger.info(message)
        await self.broadcast_activity()

    async def broadcast_activity(self):
        import json
        payload = {
            "is_active": self.is_sender_active,
            "status": self.status,
            "current_lead": self.current_lead,
            "logs": self.logs
        }
        for connection in list(self.active_connections):
            try:
                await connection.send_json(payload)
            except Exception:
                if connection in self.active_connections:
                    self.active_connections.remove(connection)

    def start(self):
        if self._running:
            return
        self._running = True
        self._task = asyncio.create_task(self._main_loop())
        logger.info("Outreach background worker thread started.")

    def stop(self):
        self._running = False
        if self._task:
            self._task.cancel()
            logger.info("Outreach background worker thread stopped.")

    async def _main_loop(self):
        while self._running:
            try:
                db = SessionLocal()
                try:
                    await self._process_autonomous_sending(db)
                    await self._process_incoming_replies(db)
                    await self._process_due_followups(db)
                finally:
                    db.close()
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Unexpected error in worker loop: {str(e)}", exc_info=True)
            
            # Poll every 20 seconds for changes, or wake up immediately if triggered
            try:
                await asyncio.wait_for(self._wakeup_event.wait(), timeout=20.0)
                self._wakeup_event.clear()
            except asyncio.TimeoutError:
                pass


    async def _send_single_lead(self, lead_id: int):
        """Processes and sends a single lead outreach using an isolated database session."""
        db = SessionLocal()
        try:
            # Fetch the lead in this task's session
            lead = db.query(ScrapedLead).filter(ScrapedLead.id == lead_id).first()
            if not lead:
                return
            
            # Double-check constraints
            if lead.email_status not in ("pending", "failed") or lead.unsubscribe or lead.bounced:
                return

            # Ensure default campaign is linked
            campaign = None
            if lead.campaign_id:
                campaign = db.query(Campaign).filter(Campaign.id == lead.campaign_id).first()
            if not campaign:
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
                lead.campaign_id = campaign.id
                db.commit()

            # Skip leads with no email address
            email = (lead.bussiness_email or "").strip()
            if not email or "@" not in email:
                lead.email_status = "skipped"
                lead.email_error = "No business email address found."
                db.commit()
                await self.add_log(f"Auto-Sender: Skipping lead '{lead.bussiness_name or 'Unknown'}' — no email address.")
                return

            # Determine website presence to route pitch style
            website = (lead.bussiness_website or "").strip()
            has_website = bool(website and website.lower() not in ("not specified", "none", "no website", "no"))

            self.current_lead = {
                "id": lead.id,
                "name": lead.bussiness_name,
                "email": lead.bussiness_email,
                "website": lead.bussiness_website or "None",
                "has_website": has_website
            }
            await self.broadcast_activity()
            await self.add_log(f"Auto-Sender: Personalizing outreach for '{lead.bussiness_name}' ({lead.scraped_city or 'Unknown city'}) [{'Has Website' if has_website else 'No Website'}]...")
            
            lead.personalization_status = "generating"
            lead.email_status = "sending"
            db.commit()

            # Generate AI outreach
            try:
                personalization = await ai_email_service.generate_initial_email(lead, has_website=has_website)
                subject = personalization["subject"]
                body = personalization["body"]
                html_content = personalization.get("html")
                
                lead.email_subject = subject
                lead.email_body = body
                lead.personalization_status = "success"
                db.commit()
                await self.add_log(f"✓ AI pitch ready for '{lead.bussiness_name}' — Subject: '{subject}'")
            except Exception as e:
                await self.add_log(f"✗ AI failed for '{lead.bussiness_name}' (ID: {lead.id}): {str(e)}")
                lead.personalization_status = "failed"
                lead.email_status = "failed"
                lead.email_error = f"AI Generation Failed: {str(e)}"
                db.commit()
                return

            # Create message log record
            msg = EmailMessage(
                lead_id=lead.id,
                message_type="INITIAL",
                subject=subject,
                body=body,
                recipient_email=lead.bussiness_email,
                sender_email=settings.SMTP_FROM_EMAIL or "sender@example.com",
                status="SENDING"
            )
            db.add(msg)
            db.commit()

            # Send through SMTP gateway
            await self.add_log(f"Sending to <{lead.bussiness_email}>...")
            success, error_msg = smtp_sender.send_email(
                recipient_email=lead.bussiness_email,
                subject=subject,
                body=body,
                html_body=html_content,
            )

            if success:
                now_utc = datetime.now(timezone.utc)
                lead.email_status = "sent"
                lead.email_sent_at = now_utc
                lead.last_email_at = now_utc
                lead.email_error = None
                
                msg.status = "SENT"
                msg.sent_at = now_utc
                msg.error_message = None
                await self.add_log(f"✓ Sent to '{lead.bussiness_name}' <{lead.bussiness_email}>")

                # Check and schedule follow-ups if enabled
                if campaign.followup_enabled:
                    scheduled_time = now_utc + timedelta(days=campaign.followup_interval_days)
                    followup = FollowUp(
                        lead_id=lead.id,
                        campaign_id=campaign.id,
                        email_message_id=msg.id,
                        scheduled_at=scheduled_time,
                        attempt_number=1,
                        status="SCHEDULED"
                    )
                    db.add(followup)
                    lead.next_followup_at = scheduled_time
                    lead.followup_count = 0
                    await self.add_log(f"Auto-Sender: Scheduled Follow-Up #1 for '{lead.bussiness_name}' on {scheduled_time.strftime('%Y-%m-%d %H:%M')}")
            else:
                lead.email_status = "failed"
                lead.email_error = error_msg
                msg.status = "FAILED"
                msg.error_message = error_msg
                await self.add_log(f"✗ Failed for '{lead.bussiness_name}': {error_msg}")

            db.commit()

            # Enforce randomized delay between emails to prevent spam flags (bypass for testing)
            if settings.EMAIL_TEST_MODE:
                delay = 1
            else:
                delay = random.randint(settings.AUTONOMOUS_DELAY_MIN, settings.AUTONOMOUS_DELAY_MAX)

            if not settings.EMAIL_TEST_MODE:
                await asyncio.sleep(delay)

        except Exception as e:
            await self.add_log(f"✗ Error processing lead {lead_id}: {str(e)}")
        finally:
            db.close()

    async def _process_autonomous_sending(self, db: Session):
        """
        Sends batches of personalized HTML emails to scraped leads autonomously and concurrently.
        """
        if not self.is_sender_active:
            if self.status != "idle" or self.current_lead is not None:
                self.status = "idle"
                self.current_lead = None
                await self.broadcast_activity()
            return

        # Check autonomous window limits
        interval_ago = datetime.now(timezone.utc) - timedelta(hours=settings.AUTONOMOUS_SEND_INTERVAL_HOURS)
        sent_in_window = db.query(EmailMessage).filter(
            EmailMessage.sent_at >= interval_ago,
            EmailMessage.status == "SENT"
        ).count()

        if sent_in_window >= settings.AUTONOMOUS_BATCH_SIZE:
            next_run_sec = int((interval_ago + timedelta(hours=settings.AUTONOMOUS_SEND_INTERVAL_HOURS) - datetime.now(timezone.utc)).total_seconds())
            next_run_min = max(1, next_run_sec // 60)
            self.status = "sleeping"
            self.current_lead = None
            await self.broadcast_activity()
            if not self.logs or "Batch limit reached" not in self.logs[-1]:
                await self.add_log(f"Auto-Sender: Batch limit reached ({sent_in_window}/{settings.AUTONOMOUS_BATCH_SIZE} sent in last {settings.AUTONOMOUS_SEND_INTERVAL_HOURS}h). Next window opens in ~{next_run_min} min.")
            return

        # Retrieve pending leads up to batch size
        max_batch_run = 100
        limit_remaining = min(max_batch_run, settings.AUTONOMOUS_BATCH_SIZE - sent_in_window)
        leads = db.query(ScrapedLead).filter(
            ScrapedLead.email_status.in_(["pending", "failed"]),
            ScrapedLead.unsubscribe == False,
            ScrapedLead.bounced == False
        ).order_by(ScrapedLead.created_at.asc()).limit(limit_remaining).all()

        if not leads:
            self.status = "idle"
            self.current_lead = None
            self.is_sender_active = False
            await self.broadcast_activity()
            await self.add_log("Auto-Sender: No pending leads found in database. Stopped bot.")
            return

        self.status = "generating"
        await self.broadcast_activity()
        await self.add_log(f"Auto-Sender: Starting concurrent dispatch for {len(leads)} leads...")

        # Concurrency throttle (max 5 simultaneous sends)
        sem = asyncio.Semaphore(5)

        async def worker(lead_id):
            async with sem:
                await self._send_single_lead(lead_id)

        # Create concurrent tasks
        tasks = [asyncio.create_task(worker(lead.id)) for lead in leads]
        await asyncio.gather(*tasks)

        self.status = "idle"
        self.current_lead = None
        self.is_sender_active = False
        await self.broadcast_activity()
        await self.add_log("Auto-Sender: Completed processing all leads in the current cycle.")


    async def _process_active_campaigns(self, db: Session):
        """
        Polls active campaigns and processes a single pending lead from the queue.
        Enforces daily limits and randomized delay windows.
        """
        active_campaigns = db.query(Campaign).filter(Campaign.status == "RUNNING").all()
        for campaign in active_campaigns:
            # 1. Enforce Daily limits check
            today = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)
            sent_today = db.query(EmailMessage).filter(
                EmailMessage.campaign_id == campaign.id,
                EmailMessage.sent_at >= today,
                EmailMessage.status == "SENT"
            ).count()

            if sent_today >= campaign.daily_limit:
                logger.info(f"Campaign '{campaign.name}' (ID: {campaign.id}) hit daily limit ({sent_today}/{campaign.daily_limit}). Skipping sending.")
                continue

            # 2. Get next pending lead in queue
            lead = db.query(ScrapedLead).filter(
                ScrapedLead.campaign_id == campaign.id,
                ScrapedLead.email_status == "pending",
                ScrapedLead.unsubscribe == False,
                ScrapedLead.bounced == False
            ).order_by(ScrapedLead.created_at.asc()).first()

            if not lead:
                # No more pending leads, mark campaign as completed
                total_leads = db.query(ScrapedLead).filter(ScrapedLead.campaign_id == campaign.id).count()
                sent_total = db.query(EmailMessage).filter(
                    EmailMessage.campaign_id == campaign.id,
                    EmailMessage.status == "SENT"
                ).count()
                
                if total_leads > 0 and sent_total >= total_leads:
                    campaign.status = "COMPLETED"
                    campaign.completed_at = datetime.now(timezone.utc)
                    db.commit()
                    logger.info(f"Campaign '{campaign.name}' has completed processing all leads.")
                continue

            # 3. Personalization and Sending
            logger.info(f"Processing lead <{lead.bussiness_email}> for Campaign '{campaign.name}'")
            lead.personalization_status = "generating"
            lead.email_status = "sending"
            db.commit()

            # Generate AI outreach text
            try:
                personalization = await ai_email_service.generate_initial_email(lead, campaign)
                subject = personalization["subject"]
                body = personalization["body"]
                
                lead.email_subject = subject
                lead.email_body = body
                lead.personalization_status = "success"
                db.commit()
            except Exception as e:
                logger.error(f"Personalization generation failed for lead {lead.id}: {str(e)}")
                lead.personalization_status = "failed"
                lead.email_status = "failed"
                lead.email_error = f"AI Generation Failed: {str(e)}"
                db.commit()
                continue

            # Create message draft log record
            msg = EmailMessage(
                campaign_id=campaign.id,
                lead_id=lead.id,
                message_type="INITIAL",
                subject=subject,
                body=body,
                recipient_email=lead.bussiness_email,
                sender_email=campaign.sender_email or settings.SMTP_FROM_EMAIL or "sender@example.com",
                status="SENDING"
            )
            db.add(msg)
            db.commit()

            # Send through SMTP gateway
            success, error_msg = smtp_sender.send_email(
                recipient_email=lead.bussiness_email,
                subject=subject,
                body=body,
                is_html=True
            )

            if success:
                now_utc = datetime.now(timezone.utc)
                lead.email_status = "sent"
                lead.email_sent_at = now_utc
                lead.last_email_at = now_utc
                lead.email_error = None
                
                msg.status = "SENT"
                msg.sent_at = now_utc
                msg.error_message = None
                
                # Check and schedule follow-ups if enabled
                if campaign.followup_enabled:
                    scheduled_time = now_utc + timedelta(days=campaign.followup_interval_days)
                    followup = FollowUp(
                        lead_id=lead.id,
                        campaign_id=campaign.id,
                        email_message_id=msg.id,
                        scheduled_at=scheduled_time,
                        attempt_number=1,
                        status="SCHEDULED"
                    )
                    db.add(followup)
                    lead.next_followup_at = scheduled_time
                    lead.followup_count = 0
                    
                logger.info(f"Outreach successfully processed for lead {lead.id}")
            else:
                lead.email_status = "failed"
                lead.email_error = error_msg
                msg.status = "FAILED"
                msg.error_message = error_msg
                logger.error(f"Outreach SMTP failed for lead {lead.id}: {error_msg}")

            db.commit()

            # Enforce randomized delay config between emails to prevent spam flags
            delay = random.randint(campaign.delay_min, campaign.delay_max)
            logger.info(f"Sleeping for {delay} seconds before next outreach...")
            await asyncio.sleep(delay)

    async def _process_due_followups(self, db: Session):
        """
        Finds scheduled follow-ups that are past their due time and processes them.
        """
        now = datetime.now(timezone.utc)
        due_followups = db.query(FollowUp).filter(
            FollowUp.status == "SCHEDULED",
            FollowUp.scheduled_at <= now
        ).all()

        for followup in due_followups:
            lead = db.query(ScrapedLead).filter(ScrapedLead.id == followup.lead_id).first()
            campaign = db.query(Campaign).filter(Campaign.id == followup.campaign_id).first()

            if not lead or not campaign or campaign.status != "RUNNING":
                continue

            # Cancel follow-up if lead unsubscribed, bounced, or already replied
            if lead.unsubscribe or lead.bounced or lead.reply_status != "unprocessed":
                followup.status = "CANCELLED"
                followup.reason = f"Cancelled: Suppression or reply received (reply_status: {lead.reply_status})"
                db.commit()
                await self.add_log(f"Auto-Sender: Cancelled Follow-Up #{followup.attempt_number} for '{lead.bussiness_name}' (reason: replied/unsubscribed)")
                continue

            # Check if campaign max followups is exceeded
            if lead.followup_count >= campaign.max_followups:
                followup.status = "CANCELLED"
                followup.reason = f"Max followups limit ({campaign.max_followups}) reached."
                db.commit()
                continue

            # Log execution starting
            await self.add_log(f"Auto-Sender: Generating AI Follow-Up #{followup.attempt_number} for '{lead.bussiness_name}'...")
            followup.status = "PROCESSING"
            db.commit()

            # Retrieve previous emails context for follow-up generation
            past_messages = db.query(EmailMessage).filter(
                EmailMessage.lead_id == lead.id,
                EmailMessage.campaign_id == campaign.id,
                EmailMessage.status == "SENT"
            ).order_by(EmailMessage.created_at.asc()).all()

            history = ""
            for pm in past_messages:
                history += f"Role: {pm.message_type}, Subject: {pm.subject}\nBody: {pm.body}\n---\n"

            # Determine website presence
            website = (lead.bussiness_website or "").strip()
            has_website = bool(website and website.lower() not in ("not specified", "none", "no website", "no"))

            try:
                followup_details = await ai_email_service.generate_followup(lead, history, campaign, has_website=has_website)
                subject = followup_details["subject"]
                body = followup_details["body"]
                html_content = followup_details.get("html")
            except Exception as e:
                logger.error(f"AI Followup generation failed for lead {lead.id}: {str(e)}")
                followup.status = "FAILED"
                followup.reason = f"AI generation failed: {str(e)}"
                db.commit()
                await self.add_log(f"✗ AI Follow-Up failed for '{lead.bussiness_name}': {str(e)}")
                continue

            # Send email
            await self.add_log(f"Auto-Sender: Dispatching Follow-Up #{followup.attempt_number} to <{lead.bussiness_email}>...")
            success, error_msg = smtp_sender.send_email(
                recipient_email=lead.bussiness_email,
                subject=subject,
                body=body,
                html_body=html_content
            )

            if success:
                now_utc = datetime.now(timezone.utc)
                followup.status = "SENT"
                followup.completed_at = now_utc
                
                # Update lead outreach count details
                lead.followup_count += 1
                lead.last_email_at = now_utc
                
                # Log sent email message
                msg = EmailMessage(
                    campaign_id=campaign.id,
                    lead_id=lead.id,
                    message_type="FOLLOW_UP",
                    subject=subject,
                    body=body,
                    recipient_email=lead.bussiness_email,
                    sender_email=campaign.sender_email or settings.SMTP_FROM_EMAIL or "sender@example.com",
                    status="SENT",
                    sent_at=now_utc
                )
                db.add(msg)
                db.commit()
                
                # Schedule NEXT follow-up if attempt count is under maximum limit
                if lead.followup_count < campaign.max_followups:
                    next_time = now_utc + timedelta(days=campaign.followup_interval_days)
                    next_followup = FollowUp(
                        lead_id=lead.id,
                        campaign_id=campaign.id,
                        email_message_id=msg.id,
                        scheduled_at=next_time,
                        attempt_number=lead.followup_count + 1,
                        status="SCHEDULED"
                    )
                    db.add(next_followup)
                    lead.next_followup_at = next_time
                    await self.add_log(f"✓ Follow-Up #{followup.attempt_number} sent to '{lead.bussiness_name}'. Scheduled Follow-Up #{lead.followup_count + 1} on {next_time.strftime('%Y-%m-%d %H:%M')}")
                else:
                    lead.next_followup_at = None
                    await self.add_log(f"✓ Follow-Up #{followup.attempt_number} sent to '{lead.bussiness_name}'. Max follow-up attempts reached.")
            else:
                followup.status = "FAILED"
                followup.reason = error_msg
                logger.error(f"Follow-up SMTP failed for lead {lead.id}: {error_msg}")
                await self.add_log(f"✗ Follow-Up #{followup.attempt_number} failed for '{lead.bussiness_name}': {error_msg}")

            db.commit()

    async def _process_incoming_replies(self, db: Session):
        """
        Polls IMAP mail folder, matches senders to leads, classifies intent,
        cancels future followups, suppresses unsubscribes, and drafts auto-replies.
        """
        unread_replies = imap_service.fetch_new_replies()
        for reply in unread_replies:
            sender_email = reply["sender"]
            
            # Find lead associated with sender email
            lead = db.query(ScrapedLead).filter(ScrapedLead.bussiness_email == sender_email).first()
            if not lead:
                logger.info(f"Received reply from <{sender_email}>, but no matching lead found in database. Skipping.")
                continue

            # Skip if we already logged this message (check duplicate)
            existing = db.query(EmailMessage).filter(
                EmailMessage.lead_id == lead.id,
                EmailMessage.message_type == "REPLY",
                EmailMessage.recipient_email == settings.SMTP_FROM_EMAIL, # replies come to our outreach inbox
                EmailMessage.body == reply["body"]
            ).first()
            if existing:
                continue

            logger.info(f"Processing incoming reply from lead ID {lead.id} (<{sender_email}>)")

            # Record reply message
            now_utc = datetime.now(timezone.utc)
            reply_msg = EmailMessage(
                campaign_id=lead.campaign_id,
                lead_id=lead.id,
                message_type="REPLY",
                subject=reply["subject"],
                body=reply["body"],
                recipient_email=settings.SMTP_FROM_EMAIL or "inbox@example.com",
                sender_email=sender_email,
                status="SENT",
                created_at=reply["received_at"] or now_utc,
                sent_at=reply["received_at"] or now_utc,
                reply_received_at=reply["received_at"] or now_utc
            )
            db.add(reply_msg)

            # Classify intent with OpenRouter agent
            try:
                classification = await ai_email_service.classify_reply(reply["body"])
                intent = classification["intent"]
                suggested_action = classification["suggested_action"]
                confidence = classification["confidence"]
                reason = classification["reason"]
            except Exception as e:
                logger.error(f"Reply classification agent failed: {str(e)}")
                intent = "UNKNOWN"
                suggested_action = "NEEDS_HUMAN"
                confidence = 0.5
                reason = "AI classifier crashed."

            # Update lead reply status
            lead.reply_status = intent.lower()

            # Cancel all future followups immediately
            db.query(FollowUp).filter(
                FollowUp.lead_id == lead.id,
                FollowUp.status == "SCHEDULED"
            ).update({"status": "CANCELLED", "reason": f"Replied (Intent: {intent})"})
            lead.next_followup_at = None

            # Handle Intent Actions
            if intent == "UNSUBSCRIBE":
                lead.unsubscribe = True
                logger.info(f"Lead ID {lead.id} (<{sender_email}>) unsubscribed. Added to permanent suppression list.")
            elif intent == "NOT_INTERESTED":
                logger.info(f"Lead ID {lead.id} (<{sender_email}>) marked NOT_INTERESTED.")
            elif intent in ("INTERESTED", "MEETING_REQUEST", "QUESTION"):
                # Handle AUTO automation modes
                campaign = db.query(Campaign).filter(Campaign.id == lead.campaign_id).first()
                if campaign and campaign.automation_mode == "AUTO":
                    # Generate auto-response
                    try:
                        logger.info(f"Generating auto-reply for lead ID {lead.id} ({intent})")
                        draft_system_prompt = (
                            f"You are the conversation agent for Nexora AI. Draft a polite, professional reply to the customer's email. "
                            f"Context: {campaign.description}. Customer intent: {intent}. Customer question/email: {reply['body']}"
                        )
                        reply_content = await ai_email_service._call_openrouter(
                            system_prompt=draft_system_prompt,
                            user_prompt=reply["body"]
                        )
                        
                        # Auto-send
                        success, smtp_err = smtp_sender.send_email(
                            recipient_email=sender_email,
                            subject=f"Re: {reply['subject']}",
                            body=reply_content,
                            is_html=False
                        )
                        if success:
                            # Log auto-reply message
                            sent_reply = EmailMessage(
                                campaign_id=campaign.id,
                                lead_id=lead.id,
                                message_type="MANUAL", # counted as manual outreach response
                                subject=f"Re: {reply['subject']}",
                                body=reply_content,
                                recipient_email=sender_email,
                                sender_email=campaign.sender_email or settings.SMTP_FROM_EMAIL or "sender@example.com",
                                status="SENT",
                                sent_at=datetime.now(timezone.utc)
                            )
                            db.add(sent_reply)
                            logger.info(f"Auto-reply sent successfully to lead {lead.id}")
                        else:
                            logger.error(f"Failed to auto-send reply: {smtp_err}")
                    except Exception as ex:
                        logger.error(f"Error in auto-reply logic: {str(ex)}")

            db.commit()

email_worker = EmailOutreachWorker()
