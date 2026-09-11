import smtplib
import logging
from email.message import EmailMessage
from email.utils import formataddr
from typing import Tuple, Optional, List
from app.core.config import settings

logger = logging.getLogger("smtp_service")

import os
import base64
try:
    from google.oauth2.credentials import Credentials
    from google.auth.transport.requests import Request
    from googleapiclient.discovery import build
    HAS_GMAIL_API = True
except ImportError:
    HAS_GMAIL_API = False

logger = logging.getLogger("smtp_service")

class SMTPEmailSender:
    def __init__(self):
        self.from_email = settings.SMTP_FROM_EMAIL or settings.SMTP_USERNAME or "info@nexora.ai"
        self.from_name = settings.SMTP_FROM_NAME or "Nexora AI"
        self.scopes = ['https://www.googleapis.com/auth/gmail.send']
        
        backend_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        self.token_path = os.path.join(backend_dir, "token.json")
        self.credentials_path = os.path.join(backend_dir, "credentials.json")

    def _send_via_smtp(self, msg: EmailMessage, recipient: str) -> Tuple[bool, Optional[str]]:
        """Sends email using standard SMTP via smtplib."""
        if not settings.SMTP_HOST or not settings.SMTP_USERNAME or not settings.SMTP_PASSWORD:
            return False, "SMTP parameters missing. Please configure SMTP_HOST, SMTP_USERNAME, and SMTP_PASSWORD."
            
        try:
            host = settings.SMTP_HOST
            port = settings.SMTP_PORT
            
            logger.info(f"Connecting to SMTP gateway {host}:{port}...")
            
            use_ssl = getattr(settings, 'SMTP_USE_SSL', False) or port == 465
            
            if use_ssl:
                server = smtplib.SMTP_SSL(host, port, timeout=20)
            else:
                server = smtplib.SMTP(host, port, timeout=20)
                
            server.ehlo()
            if not use_ssl and getattr(settings, 'SMTP_USE_TLS', True):
                server.starttls()
                server.ehlo()
                
            server.login(settings.SMTP_USERNAME, settings.SMTP_PASSWORD)
            server.send_message(msg)
            server.quit()
            
            logger.info(f"Email successfully sent via SMTP to <{recipient}>")
            return True, None
        except Exception as e:
            error_msg = f"SMTP Transmission Failed: {str(e)}"
            logger.error(error_msg)
            return False, error_msg

    def _get_gmail_service(self):
        """Establish and return an authenticated Gmail API service from env vars or token.json."""
        if not HAS_GMAIL_API:
            return None
        creds = None
        
        # 1. Check environment variables first (Cloud deployment)
        client_id = os.getenv("GMAIL_CLIENT_ID") or getattr(settings, "GMAIL_CLIENT_ID", None)
        client_secret = os.getenv("GMAIL_CLIENT_SECRET") or getattr(settings, "GMAIL_CLIENT_SECRET", None)
        refresh_token = os.getenv("GMAIL_REFRESH_TOKEN") or getattr(settings, "GMAIL_REFRESH_TOKEN", None)
        
        if client_id and client_secret and refresh_token:
            try:
                creds = Credentials(
                    token=None,
                    refresh_token=refresh_token,
                    token_uri="https://oauth2.googleapis.com/token",
                    client_id=client_id,
                    client_secret=client_secret,
                    scopes=self.scopes
                )
                creds.refresh(Request())
                return build('gmail', 'v1', credentials=creds)
            except Exception as e:
                logger.warning(f"Failed to initialize Gmail API from environment variables: {e}")
        else:
            missing = []
            if not client_id: missing.append("GMAIL_CLIENT_ID")
            if not client_secret: missing.append("GMAIL_CLIENT_SECRET")
            if not refresh_token: missing.append("GMAIL_REFRESH_TOKEN")
            logger.info(f"Gmail OAuth env vars missing in system environment: {', '.join(missing)}")

        # 2. Fallback to local token.json file
        if os.path.exists(self.token_path):
            try:
                creds = Credentials.from_authorized_user_file(self.token_path, self.scopes)
                if creds and creds.expired and creds.refresh_token:
                    creds.refresh(Request())
                    with open(self.token_path, 'w') as token:
                        token.write(creds.to_json())
                if creds and creds.valid:
                    return build('gmail', 'v1', credentials=creds)
            except Exception as e:
                logger.warning(f"Failed to initialize Gmail API from token.json: {e}")
                
        return None

    def send_email(
        self,
        recipient_email: str,
        subject: str,
        body: str,
        is_html: bool = False,
        html_body: Optional[str] = None,
        server=None,
    ) -> Tuple[bool, Optional[str]]:
        """
        Sends an email using Gmail API or standard SMTP based on available credentials.
        """
        actual_recipient = recipient_email
        if settings.EMAIL_TEST_MODE and settings.EMAIL_TEST_RECIPIENT and "example.com" not in settings.EMAIL_TEST_RECIPIENT:
            actual_recipient = settings.EMAIL_TEST_RECIPIENT
            logger.info(
                f"[TEST MODE] Redirecting outreach from <{recipient_email}> to test recipient <{actual_recipient}>"
            )

        msg = EmailMessage()
        msg["Subject"] = subject
        msg["From"] = formataddr((self.from_name, self.from_email))
        msg["To"] = actual_recipient

        if html_body:
            import re
            plain = re.sub(r"<[^>]+>", "", html_body)
            plain = re.sub(r"\s+", " ", plain).strip()
            msg.set_content(plain)
            msg.add_alternative(html_body, subtype="html")
        elif is_html:
            wrapped = self.wrap_in_html_template(body, subject)
            import re
            plain = re.sub(r"<[^>]+>", "", wrapped)
            plain = re.sub(r"\s+", " ", plain).strip()
            msg.set_content(plain)
            msg.add_alternative(wrapped, subtype="html")
        else:
            msg.set_content(body)

        errors = []

        # Strategy 1: Gmail API Transport (Preferred on cloud platforms like Render where SMTP ports are blocked)
        has_gmail_env = bool(os.getenv("GMAIL_REFRESH_TOKEN") or getattr(settings, "GMAIL_REFRESH_TOKEN", None))
        has_token_file = os.path.exists(self.token_path)
        
        if has_gmail_env or has_token_file:
            try:
                gmail_service = self._get_gmail_service()
                if gmail_service:
                    encoded_message = base64.urlsafe_b64encode(msg.as_bytes()).decode()
                    create_message = {'raw': encoded_message}
                    send_message = (gmail_service.users().messages().send(userId="me", body=create_message).execute())
                    logger.info(f"Email successfully sent via Gmail API to <{actual_recipient}> (ID: {send_message['id']})")
                    return True, None
                else:
                    errors.append("Gmail API: Service initialization returned None (check credentials)")
            except Exception as e:
                gmail_err = f"Gmail API failed: {str(e)}"
                logger.warning(f"{gmail_err}. Trying standard SMTP fallback...")
                errors.append(gmail_err)

        # Strategy 2: Standard SMTP Transport
        if settings.SMTP_HOST and settings.SMTP_USERNAME and settings.SMTP_PASSWORD and "example.com" not in settings.SMTP_HOST:
            smtp_success, smtp_err = self._send_via_smtp(msg, actual_recipient)
            if smtp_success:
                return True, None
            if smtp_err:
                errors.append(f"SMTP: {smtp_err}")

        error_summary = " | ".join(errors) if errors else "No valid email transport configured. Please set GMAIL_REFRESH_TOKEN, GMAIL_CLIENT_ID, GMAIL_CLIENT_SECRET or SMTP credentials in environment variables."
        logger.error(f"All email dispatch methods failed for <{actual_recipient}>: {error_summary}")
        return False, error_summary


    def wrap_in_html_template(self, body_text: str, subject_text: str) -> str:
        """Converts plain text with newlines into an ultra-premium HTML template with website CTA redirect."""
        if "<html" in body_text.lower() or "<div" in body_text.lower():
            return body_text

        import html
        from datetime import datetime
        from app.core.config import settings

        escaped_text = html.escape(body_text)
        paragraphs = [p.strip() for p in escaped_text.split("\n\n") if p.strip()]
        formatted_paragraphs = []
        for p in paragraphs:
            p_clean = p.replace("\n", "<br />")
            formatted_paragraphs.append(
                f'<p style="margin: 0 0 18px 0; font-size: 15px; line-height: 1.65; color: #334155;">{p_clean}</p>'
            )

        body_html = "".join(formatted_paragraphs)
        safe_subject = html.escape(subject_text)
        year = datetime.now().year
        site_url = html.escape(getattr(settings, "WEBSITE_URL", "https://nexora-meet-b4aa.vercel.app")).rstrip("/") + "/"
        sender_name = html.escape(settings.SMTP_FROM_NAME or "Nexora AI Team")

        return f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{safe_subject}</title>
    <style>
        @media only screen and (max-width: 600px) {{
            .main-table {{ padding: 12px 4px !important; }}
            .content-cell {{ padding: 20px 16px 8px 16px !important; }}
            .cta-cell {{ padding: 12px 16px 24px 16px !important; }}
            .footer-cell {{ padding: 18px 16px 20px 16px !important; }}
        }}
    </style>
</head>
<body style="margin:0;padding:0;background-color:#0f172a;font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,Helvetica,Arial,sans-serif;-webkit-font-smoothing:antialiased;">
    <table border="0" cellpadding="0" cellspacing="0" width="100%" class="main-table" style="background-color:#0f172a;padding:32px 8px;">
        <tr><td align="center">
            <table border="0" cellpadding="0" cellspacing="0" width="100%" style="max-width:600px;">

                <!-- Header Brand Banner -->
                <tr><td style="padding:0 0 20px 0;" align="center">
                    <a href="{site_url}" target="_blank" style="text-decoration:none;">
                        <span style="font-size:24px;font-weight:900;color:#ffffff;letter-spacing:-0.03em;font-family:sans-serif;">NEXORA<span style="color:#6366f1;">.AI</span></span>
                    </a>
                </td></tr>

                <!-- Main Email Card -->
                <tr><td>
                    <table border="0" cellpadding="0" cellspacing="0" width="100%" style="background:#ffffff;border-radius:20px;overflow:hidden;border:1px solid #334155;box-shadow:0 20px 40px rgba(0,0,0,0.3);width:100% !important;">
                        
                        <!-- Top Accent Line -->
                        <tr><td style="background:linear-gradient(135deg,#6366f1 0%,#2563eb 50%,#06b6d4 100%);height:6px;line-height:6px;font-size:6px;">&nbsp;</td></tr>
                        
                        <!-- Content Area -->
                        <tr><td class="content-cell" style="padding:28px 24px 8px 24px;">
                            {body_html}
                        </td></tr>

                        <!-- Bulletproof Centered CTA Button with Single-Line Arrow Alignment -->
                        <tr><td class="cta-cell" style="padding:8px 24px 32px 24px;" align="center">
                            <table border="0" cellpadding="0" cellspacing="0" role="presentation" align="center" style="margin:0 auto;">
                                <tr>
                                    <td align="center" bgcolor="#4f46e5" style="border-radius:50px;background:linear-gradient(135deg,#4f46e5 0%,#2563eb 100%);box-shadow:0 8px 24px rgba(79,70,229,0.35);">
                                        <a href="{site_url}" target="_blank" style="font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,Helvetica,Arial,sans-serif;font-size:15px;font-weight:700;color:#ffffff;text-decoration:none;display:inline-block;padding:16px 36px;white-space:nowrap;letter-spacing:0.02em;">
                                            <span style="vertical-align:middle;display:inline-block;">Visit Our Website &amp; View Our Work</span>
                                            <span style="vertical-align:middle;display:inline-block;margin-left:8px;font-size:18px;line-height:1;font-weight:900;">&rarr;</span>
                                        </a>
                                    </td>
                                </tr>
                            </table>
                            <p style="margin:12px 0 0 0;font-size:12px;color:#64748b;font-family:sans-serif;font-weight:500;">
                                Direct Link: <a href="{site_url}" target="_blank" style="color:#4f46e5;text-decoration:underline;font-weight:600;">{site_url}</a>
                            </p>
                        </td></tr>

                        <!-- Footer -->
                        <tr><td class="footer-cell" style="padding:22px 24px 26px 24px;background:#fafafa;border-top:1px solid #f1f5f9;">
                            <table border="0" cellpadding="0" cellspacing="0" width="100%" style="width:100% !important;">
                                <tr>
                                    <td>
                                        <p style="margin:0;font-size:11px;color:#94a3b8;line-height:1.6;font-family:sans-serif;">
                                            Sent by <strong style="color:#475569;">{sender_name}</strong> &bull; <a href="{site_url}" style="color:#4f46e5;text-decoration:none;font-weight:600;">{site_url}</a><br/>
                                            &copy; {year} Nexora AI &bull; All Rights Reserved
                                        </p>
                                    </td>
                                    <td align="right" valign="top">
                                        <a href="{site_url}#contact" style="font-size:11px;color:#6366f1;text-decoration:underline;font-family:sans-serif;font-weight:600;">Contact Us</a>
                                    </td>
                                </tr>
                            </table>
                        </td></tr>
                    </table>
                </td></tr>
            </table>
        </td></tr>
    </table>
</body>
</html>"""

smtp_sender = SMTPEmailSender()
