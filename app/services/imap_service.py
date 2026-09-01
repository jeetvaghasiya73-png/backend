import imaplib
import email
from email.header import decode_header
import logging
from datetime import datetime, timezone
from typing import List, Dict, Any, Optional, Tuple
from app.core.config import settings

logger = logging.getLogger("imap_service")

class IMAPReplyService:
    def __init__(self):
        self.host = settings.IMAP_HOST
        self.port = settings.IMAP_PORT
        self.username = settings.IMAP_USERNAME
        self.password = settings.IMAP_PASSWORD

    def fetch_new_replies(self) -> List[Dict[str, Any]]:
        """
        Connects to IMAP server, polls the Inbox, and retrieves unread/unseen messages.
        Filters out emails not corresponding to active leads.
        Returns a list of dicts: [{'sender': str, 'subject': str, 'body': str, 'received_at': datetime}]
        """
        if not self.host or not self.username or not self.password:
            logger.warning("IMAP inbox credentials not configured in environment settings. Skipping reply checks.")
            return []

        replies = []
        try:
            logger.info(f"Connecting to IMAP inbox {self.host}:{self.port}...")
            mail = imaplib.IMAP4_SSL(self.host, self.port, timeout=20)
            mail.login(self.username, self.password)
            mail.select("inbox")

            # Search for all UNSEEN emails
            status, response_data = mail.search(None, "UNSEEN")
            if status != "OK":
                logger.error("IMAP search failed to fetch message list status.")
                return []

            mail_ids = response_data[0].split()
            logger.info(f"Found {len(mail_ids)} unread messages in mailbox.")

            for m_id in mail_ids:
                # Fetch RFC822 format raw email message
                res_status, data = mail.fetch(m_id, "(RFC822)")
                if res_status != "OK":
                    continue

                raw_email = data[0][1]
                msg = email.message_from_bytes(raw_email)

                # 1. Parse Sender
                from_header = msg.get("From", "")
                sender_name, sender_email = self._parse_from_address(from_header)
                if not sender_email:
                    continue

                # 2. Parse Subject
                subject_header = msg.get("Subject", "")
                subject = self._decode_mime_header(subject_header)

                # 3. Parse Body
                body = self._extract_email_body(msg)

                # 4. Parse Date
                date_header = msg.get("Date")
                received_at = self._parse_date(date_header)

                replies.append({
                    "sender": sender_email,
                    "sender_name": sender_name,
                    "subject": subject,
                    "body": body,
                    "received_at": received_at,
                    "imap_uid": m_id.decode()
                })

                # Mark as SEEN (read) so we don't process it in the next loop iteration
                mail.store(m_id, "+FLAGS", "\\Seen")

            mail.close()
            mail.logout()
            logger.info(f"Successfully processed {len(replies)} inbox replies.")
            return replies

        except imaplib.IMAP4.error as e:
            logger.error(f"IMAP protocol failure: {str(e)}")
            return []
        except Exception as e:
            logger.error(f"Unhandled error during IMAP reply fetch: {str(e)}")
            return []

    def _decode_mime_header(self, header_val: str) -> str:
        if not header_val:
            return ""
        decoded_parts = decode_header(header_val)
        header_text = []
        for part, encoding in decoded_parts:
            if isinstance(part, bytes):
                if encoding:
                    header_text.append(part.decode(encoding, errors="ignore"))
                else:
                    header_text.append(part.decode("utf-8", errors="ignore"))
            else:
                header_text.append(str(part))
        return "".join(header_text)

    def _parse_from_address(self, from_val: str) -> Tuple[str, str]:
        """
        Parses header value like 'John Doe <john@example.com>' or 'john@example.com'
        Returns (name, email)
        """
        if not from_val:
            return "", ""
        parsed = email.utils.parseaddr(from_val)
        return parsed[0], parsed[1].lower().strip()

    def _extract_email_body(self, msg: email.message.Message) -> str:
        body = ""
        if msg.is_multipart():
            for part in msg.walk():
                content_type = part.get_content_type()
                content_disposition = str(part.get("Content-Disposition"))
                
                # Fetch text/plain first, or fallback to text/html
                if content_type == "text/plain" and "attachment" not in content_disposition:
                    charset = part.get_content_charset() or "utf-8"
                    body = part.get_payload(decode=True).decode(charset, errors="ignore")
                    break
                elif content_type == "text/html" and "attachment" not in content_disposition:
                    charset = part.get_content_charset() or "utf-8"
                    body = part.get_payload(decode=True).decode(charset, errors="ignore")
        else:
            charset = msg.get_content_charset() or "utf-8"
            body = msg.get_payload(decode=True).decode(charset, errors="ignore")
            
        return body.strip()

    def _parse_date(self, date_val: Optional[str]) -> datetime:
        if not date_val:
            return datetime.now(timezone.utc)
        try:
            parsed_tuple = email.utils.parsedate_to_datetime(date_val)
            if parsed_tuple.tzinfo is None:
                return parsed_tuple.replace(tzinfo=timezone.utc)
            return parsed_tuple
        except Exception:
            return datetime.now(timezone.utc)

imap_service = IMAPReplyService()
