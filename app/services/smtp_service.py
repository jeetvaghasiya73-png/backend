import smtplib
import logging
from email.message import EmailMessage
from email.utils import formataddr
from typing import Tuple, Optional, List
from app.core.config import settings

logger = logging.getLogger("smtp_service")

import os
import base64
from google.oauth2.credentials import Credentials
from google.auth.transport.requests import Request
from googleapiclient.discovery import build

logger = logging.getLogger("smtp_service")

class SMTPEmailSender:
    def __init__(self):
        # We no longer use SMTP, but we keep the same class interface
        self.from_email = settings.SMTP_FROM_EMAIL or "info@nexora.ai"
        self.from_name = settings.SMTP_FROM_NAME or "Nexora AI"
        
        # Load Gmail API scopes
        self.scopes = ['https://www.googleapis.com/auth/gmail.send']
        
        # Find token path (assumes token.json is in the project root or backend folder)
        backend_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        self.token_path = os.path.join(backend_dir, "token.json")
        self.credentials_path = os.path.join(backend_dir, "credentials.json")

    def _get_gmail_service(self):
        """Establish and return an authenticated Gmail API service."""
        creds = None
        if os.path.exists(self.token_path):
            creds = Credentials.from_authorized_user_file(self.token_path, self.scopes)
            
        if not creds or not creds.valid:
            if creds and creds.expired and creds.refresh_token:
                try:
                    creds.refresh(Request())
                    # Attempt to save the refreshed token
                    with open(self.token_path, 'w') as token:
                        token.write(creds.to_json())
                except Exception as e:
                    logger.error(f"Failed to refresh Gmail token: {e}")
                    raise
            else:
                raise Exception(f"Valid token.json not found at {self.token_path}. Please run generate_gmail_token.py locally first.")
                
        return build('gmail', 'v1', credentials=creds)

    def send_email(
        self,
        recipient_email: str,
        subject: str,
        body: str,
        is_html: bool = False,
        html_body: Optional[str] = None,
        server=None, # kept for signature compatibility
    ) -> Tuple[bool, Optional[str]]:
        """
        Sends an email using the Google Gmail HTTP API.
        """
        actual_recipient = recipient_email
        if settings.EMAIL_TEST_MODE:
            actual_recipient = settings.EMAIL_TEST_RECIPIENT or self.from_email
            logger.info(
                f"[TEST MODE] Redirecting outreach from <{recipient_email}> to test recipient <{actual_recipient}>"
            )

        try:
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

            # Gmail API requires base64url encoded string
            encoded_message = base64.urlsafe_b64encode(msg.as_bytes()).decode()
            create_message = {'raw': encoded_message}

            service = self._get_gmail_service()
            send_message = (service.users().messages().send(userId="me", body=create_message).execute())
            
            logger.info(f"Email successfully sent to <{actual_recipient}> (Message ID: {send_message['id']})")
            return True, None

        except Exception as e:
            error_msg = f"Unexpected error during Gmail API send: {str(e)}"
            logger.error(error_msg)
            return False, error_msg

    def wrap_in_html_template(self, body_text: str, subject_text: str) -> str:
        """Converts plain text with newlines into a basic HTML template. Used as legacy fallback."""
        if "<html" in body_text.lower() or "<div" in body_text.lower():
            return body_text

        import html
        from datetime import datetime

        escaped_text = html.escape(body_text)
        paragraphs = [p.strip() for p in escaped_text.split("\n\n") if p.strip()]
        formatted_paragraphs = []
        for p in paragraphs:
            p_clean = p.replace("\n", "<br />")
            formatted_paragraphs.append(
                f'<p style="margin: 0 0 16px 0; font-size: 15px; line-height: 1.6; color: #334155;">{p_clean}</p>'
            )

        body_html = "".join(formatted_paragraphs)
        safe_subject = html.escape(subject_text)
        year = datetime.now().year

        return f"""<!DOCTYPE html>
                    <html lang="en" xmlns="http://www.w3.org/1999/xhtml" xmlns:v="urn:schemas-microsoft-com:vml" xmlns:o="urn:schemas-microsoft-com:office:office">
                    <head>
                        <meta charset="utf-8">
                        <meta name="viewport" content="width=device-width, initial-scale=1.0">
                        <meta http-equiv="X-UA-Compatible" content="IE=edge">
                        <meta name="color-scheme" content="light">
                        <meta name="supported-color-schemes" content="light">
                        <title>{safe_subject}</title>
                        <!--[if mso]>
                        <noscript>
                            <xml>
                                <o:OfficeDocumentSettings>
                                    <o:PixelsPerInch>96</o:PixelsPerInch>
                                </o:OfficeDocumentSettings>
                            </xml>
                        </noscript>
                        <![endif]-->
                        <style>
                            /* Reset */
                            body, table, td, a {{ -webkit-text-size-adjust: 100%; -ms-text-size-adjust: 100%; }}
                            table, td {{ mso-table-lspace: 0pt; mso-table-rspace: 0pt; }}
                            img {{ -ms-interpolation-mode: bicubic; border: 0; outline: none; text-decoration: none; display: block; }}
                            body {{ margin: 0; padding: 0; width: 100% !important; height: 100% !important; }}

                            /* Base type */
                            body, td, p, span, a {{
                                font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif;
                            }}

                            a {{ color: #2563eb; }}

                            .btn-primary a {{
                                background-color: #2563eb;
                                border-radius: 8px;
                                color: #ffffff !important;
                                display: inline-block;
                                font-weight: 600;
                                padding: 12px 28px;
                                text-decoration: none;
                            }}

                            /* Mobile */
                            @media only screen and (max-width: 600px) {{
                                .email-wrapper {{ width: 100% !important; }}
                                .email-body {{ border-radius: 0 !important; border-left: none !important; border-right: none !important; }}
                                .stack-padding {{ padding-left: 20px !important; padding-right: 20px !important; }}
                                .header-padding {{ padding: 24px 20px !important; }}
                                .footer-padding {{ padding: 20px !important; }}
                                .h1 {{ font-size: 22px !important; line-height: 30px !important; }}
                                .body-text {{ font-size: 15px !important; line-height: 24px !important; }}
                                .btn-primary a {{ display: block !important; text-align: center; padding: 14px 20px !important; }}
                            }}

                            @media (prefers-color-scheme: dark) {{
                                .email-bg {{ background-color: #f8fafc !important; }}
                            }}
                        </style>
                    </head>
                    <body style="margin:0;padding:0;background-color:#f1f5f9;">
                        <!-- Preheader (hidden preview text shown next to subject line in inbox) -->
                        <div style="display:none;max-height:0;overflow:hidden;mso-hide:all;font-size:1px;line-height:1px;color:#f1f5f9;">
                            {safe_subject}
                        </div>
                        <div style="display:none;max-height:0;overflow:hidden;mso-hide:all;">&nbsp;&zwnj;&nbsp;&zwnj;&nbsp;&zwnj;&nbsp;&zwnj;&nbsp;&zwnj;&nbsp;&zwnj;&nbsp;&zwnj;&nbsp;&zwnj;</div>

                        <table role="presentation" border="0" cellpadding="0" cellspacing="0" width="100%" class="email-bg" style="background-color:#f1f5f9;">
                            <tr>
                                <td align="center" style="padding:32px 12px;">

                                    <!--[if mso]>
                                    <table role="presentation" border="0" cellpadding="0" cellspacing="0" width="600" align="center"><tr><td>
                                    <![endif]-->
                                    <table role="presentation" border="0" cellpadding="0" cellspacing="0" width="100%" class="email-wrapper" style="max-width:600px;">

                                        <!-- Card -->
                                        <tr>
                                            <td class="email-body" style="background-color:#ffffff;border-radius:16px;border:1px solid #e2e8f0;overflow:hidden;">

                                                <!-- Accent bar -->
                                                <table role="presentation" border="0" cellpadding="0" cellspacing="0" width="100%">
                                                    <tr>
                                                        <td style="background-color:#2563eb;height:5px;line-height:5px;font-size:1px;">&nbsp;</td>
                                                    </tr>
                                                </table>

                                                <!-- Header / logo -->
                                                <table role="presentation" border="0" cellpadding="0" cellspacing="0" width="100%">
                                                    <tr>
                                                        <td class="header-padding" style="padding:28px 32px 20px 32px;">
                                                            <span style="font-size:18px;font-weight:800;color:#1e3a8a;letter-spacing:-0.02em;">
                                                                NEXORA<span style="color:#2563eb;">AI</span>
                                                            </span>
                                                        </td>
                                                    </tr>
                                                </table>

                                                <!-- Divider -->
                                                <table role="presentation" border="0" cellpadding="0" cellspacing="0" width="100%">
                                                    <tr><td style="padding:0 32px;">
                                                        <div style="border-top:1px solid #f1f5f9;"></div>
                                                    </td></tr>
                                                </table>

                                                <!-- Body content -->
                                                <table role="presentation" border="0" cellpadding="0" cellspacing="0" width="100%">
                                                    <tr>
                                                        <td class="stack-padding body-text" style="padding:28px 32px 32px 32px;font-size:16px;line-height:26px;color:#334155;">
                                                            {body_html}
                                                        </td>
                                                    </tr>
                                                </table>

                                            </td>
                                        </tr>

                                        <!-- Footer -->
                                        <tr>
                                            <td class="footer-padding" style="padding:24px 32px;">
                                                <table role="presentation" border="0" cellpadding="0" cellspacing="0" width="100%">
                                                    <tr>
                                                        <td align="center" style="font-size:12px;line-height:18px;color:#94a3b8;">
                                                            &copy; {year} Nexora AI &bull; Anand, Gujarat, India
                                                            <br>
                                                            <a href="#unsubscribe" style="color:#94a3b8;text-decoration:underline;">Unsubscribe</a>
                                                            &nbsp;&bull;&nbsp;
                                                            <a href="#preferences" style="color:#94a3b8;text-decoration:underline;">Email preferences</a>
                                                        </td>
                                                    </tr>
                                                </table>
                                            </td>
                                        </tr>

                                    </table>
                                    <!--[if mso]>
                                    </td></tr></table>
                                    <![endif]-->

                                </td>
                            </tr>
                        </table>
                    </body>
                    </html>"""

smtp_sender = SMTPEmailSender()
