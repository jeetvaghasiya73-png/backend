import unittest
from unittest.mock import MagicMock, patch
from datetime import datetime, timezone

from app.core.config import settings
from app.services.smtp_service import SMTPEmailSender
from app.services.ai_email import ai_email_service
from app.models.base import Base as _
from app.models.scraped_lead import ScrapedLead
from app.models.campaign import Campaign

class TestOutreachSystem(unittest.TestCase):

    def setUp(self):
        # Setup test inputs
        self.mock_lead = ScrapedLead(
            id=123,
            bussiness_name="Test Business Anand",
            bussiness_email="prospect@example.com",
            scraped_city="Anand",
            scraped_service="Solar Installer",
            category="Energy"
        )
        self.mock_campaign = Campaign(
            id=1,
            name="Anand Solar Pitch",
            description="Pitching custom solar lead automation.",
            email_template="Introduce services politely. Reference Anand city."
        )

    def test_ai_email_fallback_generation(self):
        """Verify that fallback outreach email generation outputs correct format."""
        result = ai_email_service._fallback_generate_initial(self.mock_lead, self.mock_campaign)
        self.assertIn("subject", result)
        self.assertIn("body", result)
        self.assertIn("Test Business Anand", result["subject"])
        self.assertIn("Anand", result["body"])
        self.assertIn("Solar Installer", result["body"])

    def test_autonomous_email_generation_no_campaign(self):
        """Verify that fallback outreach email generation behaves correctly without a campaign."""
        result = ai_email_service._fallback_generate_initial(self.mock_lead)
        self.assertIn("subject", result)
        self.assertIn("body", result)
        self.assertIn("SEO & Web Development", result["body"])
        self.assertIn("WhatsApp & Workflow Automations", result["body"])

    def test_ai_email_fallback_classification(self):
        """Verify that fallback intent classification parses keywords accurately."""
        # Unsubscribe checks
        unsub_reply = "Please remove me from your list immediately and unsubscribe."
        unsub_class = ai_email_service._fallback_classify_reply(unsub_reply)
        self.assertEqual(unsub_class["intent"], "UNSUBSCRIBE")

        # Interested checks
        int_reply = "Hi! I am interested in this automation service, how much is the price?"
        int_class = ai_email_service._fallback_classify_reply(int_reply)
        self.assertEqual(int_class["intent"], "INTERESTED")

        # Not interested checks
        ni_reply = "No thanks, go away."
        ni_class = ai_email_service._fallback_classify_reply(ni_reply)
        self.assertEqual(ni_class["intent"], "NOT_INTERESTED")

    def test_ai_email_fallback_followup(self):
        """Verify that fallback follow-up email is generated correctly."""
        result = ai_email_service._fallback_followup(self.mock_lead, self.mock_campaign)
        self.assertIn("subject", result)
        self.assertIn("body", result)
        self.assertIn("Following up", result["subject"])
        self.assertIn("Test Business Anand", result["body"])

    @patch("smtplib.SMTP")
    def test_smtp_sender_test_mode(self, mock_smtp_class):
        """Verify that SMTPEmailSender behaves correctly, respecting settings.EMAIL_TEST_MODE."""
        # Setup mocks
        mock_server = MagicMock()
        mock_smtp_class.return_value = mock_server
        
        # Instantiate test sender
        sender = SMTPEmailSender()
        sender.username = "test_user@example.com"
        sender.password = "test_pass"
        sender.from_email = "test_user@example.com"
        
        # Force test mode active
        with patch.object(settings, "EMAIL_TEST_MODE", True), \
             patch.object(settings, "EMAIL_TEST_RECIPIENT", "admin@example.com"):
            
            success, err = sender.send_email(
                recipient_email="customer@example.com",
                subject="Test Subject",
                body="Test Body"
            )
            
            self.assertTrue(success)
            self.assertIsNone(err)
            
            # Check SMTP call logs
            mock_smtp_class.assert_called_once_with(settings.SMTP_HOST, settings.SMTP_PORT, timeout=15)
            mock_server.starttls.assert_called_once()
            mock_server.login.assert_called_once_with("test_user@example.com", "test_pass")
            mock_server.send_message.assert_called_once()
            mock_server.quit.assert_called_once()

if __name__ == "__main__":
    unittest.main()
