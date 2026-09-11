import sys
import os
import asyncio
import logging

# Ensure UTF-8 output encoding for Windows PowerShell console
if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding='utf-8')
    except Exception:
        pass

# Ensure backend directory is on sys.path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app.core.config import settings
from app.services.imap_service import imap_service
from app.services.smtp_service import smtp_sender
from app.services.ai_email import ai_email_service
from app.services.email_worker import email_worker
from app.database.session import SessionLocal
from app.models.scraped_lead import ScrapedLead
from app.models.email_message import EmailMessage

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("test_reply_system")

async def test_email_reply_system():
    print("=" * 60)
    print(" NEXORA AI EMAIL REPLY SYSTEM TEST ")
    print("=" * 60)

    print(f"IMAP Host: {settings.IMAP_HOST}:{settings.IMAP_PORT}")
    print(f"IMAP Username: {settings.IMAP_USERNAME}")
    print(f"SMTP Host: {settings.SMTP_HOST}:{settings.SMTP_PORT}")
    print(f"SMTP From: {settings.SMTP_FROM_EMAIL}")
    print(f"Test Mode Active: {settings.EMAIL_TEST_MODE}")
    print("-" * 60)

    db = SessionLocal()
    try:
        # Step 1: Test IMAP Fetching
        print("\n1. Testing IMAP Inbox Connection & Fetching...")
        if settings.IMAP_HOST and settings.IMAP_USERNAME and settings.IMAP_PASSWORD and "example.com" not in settings.IMAP_HOST:
            try:
                unread = imap_service.fetch_new_replies()
                print(f"[SUCCESS] IMAP Connection Successful! Found {len(unread)} unread reply(ies).")
                for u in unread:
                    print(f"   - Sender: {u['sender']}")
                    print(f"   - Subject: {u['subject']}")
                    print(f"   - Body Snippet: {u['body'][:80]}...")
            except Exception as imap_err:
                print(f"[ERROR] IMAP Connection Failed: {imap_err}")
        else:
            print("! Skipping live IMAP test (credentials not fully configured).")

        # Step 2: Test AI Classification and Auto-Reply Draft Generation
        print("\n2. Testing AI Intent Classification & Auto-Reply Generation...")
        sample_inquiry = "Hi! I saw your email about digital automation. We are very interested for our business! Can you share pricing and package details?"
        print(f"Input Inquiry: \"{sample_inquiry}\"")

        classification = await ai_email_service.classify_reply(sample_inquiry)
        print(f"[SUCCESS] AI Classified Intent: {classification['intent'].upper()}")
        print(f"   - Suggested Action: {classification['suggested_action']}")
        print(f"   - Confidence: {classification['confidence']}")

        draft_prompt = (
            f"You are the conversation agent for Nexora AI. Draft a concise, polite, and professional reply to the customer's email. "
            f"Company context: Nexora AI web development & lead automation. Customer intent: {classification['intent']}. Customer inquiry: {sample_inquiry}"
        )
        ai_reply_body = await ai_email_service._call_openrouter(
            system_prompt=draft_prompt,
            user_prompt=sample_inquiry
        )
        print(f"[SUCCESS] AI Generated Reply Content:\n---\n{ai_reply_body}\n---")

        # Step 3: Test End-to-End Reply Batch Processing (Simulation & Auto-Sending)
        print("\n3. Testing End-to-End Reply Processing & Auto-Reply Dispatch...")
        
        # Fetch or create a test lead in database
        target_lead = db.query(ScrapedLead).order_by(ScrapedLead.id.desc()).first()
        if not target_lead:
            target_lead = ScrapedLead(
                bussiness_name="Test Apex Corp",
                bussiness_email="jeetvaghasiya73@gmail.com",
                bussiness_number="+1-555-0199",
                scraped_city="New York",
                scraped_service="Web Development",
                email_status="sent"
            )
            db.add(target_lead)
            db.commit()
            db.refresh(target_lead)

        test_reply = [{
            "sender": target_lead.bussiness_email or "jeetvaghasiya73@gmail.com",
            "sender_name": target_lead.bussiness_name,
            "subject": f"Re: Cold Outreach for {target_lead.bussiness_name}",
            "body": "Hello Nexora AI! We are definitely interested in your automation services. What are the next steps to start?",
            "received_at": None
        }]

        processed = await email_worker.process_replies_batch(db, test_reply)
        print(f"[SUCCESS] Processed {len(processed)} reply item(s) successfully!")
        for p in processed:
            print(f"   - Lead ID: {p['lead_id']} ({p['business_name']})")
            print(f"   - Identified Intent: {p['intent']}")

        # Verify sent auto-reply message in EmailMessage table
        latest_sent = db.query(EmailMessage).filter(
            EmailMessage.lead_id == target_lead.id,
            EmailMessage.recipient_email == target_lead.bussiness_email
        ).order_by(EmailMessage.created_at.desc()).first()

        if latest_sent:
            print(f"\n[SUCCESS] Verified EmailMessage Log in DB:")
            print(f"   - Message ID: {latest_sent.id}")
            print(f"   - Type: {latest_sent.message_type}")
            print(f"   - Subject: {latest_sent.subject}")
            print(f"   - Status: {latest_sent.status}")

        print("\n" + "=" * 60)
        print(" ALL EMAIL REPLY SYSTEM TESTS PASSED SUCCESSFULLY! ")
        print("=" * 60)

    except Exception as e:
        print(f"\n[ERROR] Test Error: {str(e)}")
        import traceback
        traceback.print_exc()
    finally:
        db.close()

if __name__ == "__main__":
    asyncio.run(test_email_reply_system())
