import json
import logging
import httpx
from typing import Dict, Any, Optional
from app.core.config import settings

logger = logging.getLogger("ai_email_service")


def build_html_email(lead: Any, pitch_text: str, has_website: bool) -> str:
    """
    Builds a beautiful, responsive, and mobile-friendly HTML email template.
    Injects scraped lead data and AI-generated pitch text (with bullet point parsing).
    """
    import html as html_lib
    import re
    from datetime import datetime

    biz_name = html_lib.escape(lead.bussiness_name or "your business")
    city = html_lib.escape(lead.scraped_city or "your area")
    service = html_lib.escape(lead.scraped_service or lead.category or "your industry")
    website = html_lib.escape(lead.bussiness_website or "")
    rating = html_lib.escape(str(lead.rating or ""))
    reviews = html_lib.escape(str(lead.total_review or "0"))

    # Convert pitch text into styled HTML blocks (paragraphs and lists)
    escaped_pitch = html_lib.escape(pitch_text)
    
    # Replace markdown bold **text** with <strong>text</strong>
    escaped_pitch = re.sub(r'\*\*(.*?)\*\*', r'<strong style="font-weight:700;color:#0f172a;">\1</strong>', escaped_pitch)
    
    # Split text into blocks by double newlines
    blocks = [b.strip() for b in escaped_pitch.split("\n\n") if b.strip()]
    pitch_html = ""
    
    for block in blocks:
        lines = [l.strip() for l in block.split("\n") if l.strip()]
        if not lines:
            continue
            
        # Check if the block is a bulleted list
        is_list = True
        for line in lines:
            clean_line = line.strip()
            if not (clean_line.startswith("-") or clean_line.startswith("*") or clean_line.startswith("•")):
                is_list = False
                break
                
        if is_list:
            ul_style = "margin:0 0 16px 0;padding-left:20px;font-size:14px;line-height:1.6;color:#334155;font-family:sans-serif;"
            li_style = "margin:0 0 8px 0;color:#334155;"
            list_html = f'<ul style="{ul_style}">'
            for line in lines:
                clean_line = line.strip()
                # Strip list prefixes
                for prefix in ["- ", "* ", "• ", "-", "*", "•"]:
                    if clean_line.startswith(prefix):
                        clean_line = clean_line[len(prefix):].strip()
                        break
                list_html += f'<li style="{li_style}">{clean_line}</li>'
            list_html += '</ul>'
            pitch_html += list_html
        else:
            # Join lines with a single space to restore normal wrapping
            paragraph_text = " ".join(lines)
            pitch_html += f'<p style="margin:0 0 16px 0;font-size:14px;line-height:1.6;color:#334155;font-family:sans-serif;">{paragraph_text}</p>'

    # Services to highlight
    if has_website:
        services_list = [
            ("🔍", "SEO & Search Rankings", "Boost your Google visibility and organic traffic"),
            ("⚡", "WhatsApp & Workflow Automations", "Automate customer support, lead flows & operations"),
            ("📊", "Web & App Scraping", "Extract competitive data and build custom Scraper APIs"),
            ("🔧", "Web Dev Upgrades", "Modernize your site with faster, premium UI/UX"),
        ]
    else:
        services_list = [
            ("🌐", "Modern Website Design", "Fast, mobile-friendly site that builds trust"),
            ("📈", "Local SEO Setup", "Rank on Google Maps and local searches from day one"),
            ("💬", "WhatsApp Business Setup", "Automated customer messaging and lead capture"),
            ("🎨", "Free Homepage Mockup", "We'll design a draft homepage for your business — free"),
        ]

    services_html = ""
    for icon, title, desc in services_list:
        services_html += f"""
        <tr>
            <td style="padding:10px 16px;border-bottom:1px solid #f1f5f9;">
                <table border="0" cellpadding="0" cellspacing="0" width="100%">
                    <tr>
                        <td width="36" valign="top" style="font-size:20px;padding-right:12px;">{icon}</td>
                        <td>
                            <p style="margin:0;font-size:14px;font-weight:700;color:#1e293b;font-family:sans-serif;">{title}</p>
                            <p style="margin:2px 0 0 0;font-size:12px;color:#64748b;line-height:1.4;font-family:sans-serif;">{desc}</p>
                        </td>
                    </tr>
                </table>
            </td>
        </tr>"""

    # Lead context badge
    website_link_html = ""
    if website and website.lower() not in ('not specified', 'none'):
        website_link_html = f'<br/>🌐 <a href="{website}" style="color:#2563eb;text-decoration:none;word-break:break-all;font-size:12px;">{website}</a>'

    context_badge = f"""
    <table border="0" cellpadding="0" cellspacing="0" width="100%" style="background:#f8fafc;border-radius:10px;margin-bottom:24px;border:1px solid #e2e8f0;width:100% !important;">
        <tr>
            <td style="padding:16px 20px;">
                <p style="margin:0 0 6px 0;font-size:10px;text-transform:uppercase;letter-spacing:0.05em;color:#94a3b8;font-weight:700;font-family:sans-serif;">PREPARED FOR</p>
                <p style="margin:0 0 6px 0;font-size:16px;font-weight:800;color:#0f172a;font-family:sans-serif;line-height:1.2;">{biz_name}</p>
                <p style="margin:0;font-size:12px;color:#64748b;font-family:sans-serif;line-height:1.5;word-break:break-word;">
                    📍 {city} &nbsp;&bull;&nbsp; 🏷️ {service}
                    {'&nbsp;&bull;&nbsp; ⭐ ' + rating + ' (' + reviews + ' reviews)' if rating else ''}
                    {website_link_html}
                </p>
            </td>
        </tr>
    </table>"""

    year = datetime.now().year
    sender_name = html_lib.escape(settings.SMTP_FROM_NAME or "Nexora AI")

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width,initial-scale=1.0">
    <title>Partnership Opportunity — {biz_name}</title>
    <style>
        @media only screen and (max-width: 600px) {{
            .main-table {{
                padding: 12px 6px !important;
            }}
            .content-cell {{
                padding: 20px 14px 8px 14px !important;
            }}
            .services-cell {{
                padding: 0 14px 20px 14px !important;
            }}
            .cta-cell {{
                padding: 8px 14px 20px 14px !important;
            }}
            .cta-button {{
                width: 100% !important;
                box-sizing: border-box !important;
                text-align: center !important;
                padding: 14px 20px !important;
            }}
            .footer-cell {{
                padding: 16px 14px 20px 14px !important;
            }}
        }}
    </style>
</head>
<body style="margin:0;padding:0;background-color:#f1f5f9;font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,Helvetica,Arial,sans-serif;-webkit-font-smoothing:antialiased;">
    <table border="0" cellpadding="0" cellspacing="0" width="100%" class="main-table" style="background-color:#f1f5f9;padding:24px 8px;">
        <tr><td align="center">
            <table border="0" cellpadding="0" cellspacing="0" width="100%" style="max-width:600px;">

                <!-- Logo Bar -->
                <tr><td style="padding:0 0 16px 0;" align="center">
                    <span style="font-size:22px;font-weight:900;color:#1e3a8a;letter-spacing:-0.03em;font-family:sans-serif;">NEXORA<span style="color:#2563eb;">AI</span></span>
                </td></tr>

                <!-- Main Card -->
                <tr><td>
                    <table border="0" cellpadding="0" cellspacing="0" width="100%" style="background:#ffffff;border-radius:16px;overflow:hidden;border:1px solid #e2e8f0;box-shadow:0 4px 24px rgba(0,0,0,0.06);width:100% !important;">
                        
                        <!-- Top Gradient -->
                        <tr><td style="background:linear-gradient(135deg,#2563eb 0%,#7c3aed 100%);height:6px;line-height:6px;font-size:6px;">&nbsp;</td></tr>
                        
                        <!-- Content Area (uses highly responsive fluid 20px/14px padding) -->
                        <tr><td class="content-cell" style="padding:24px 20px 8px 20px;">
                            {context_badge}
                            {pitch_html}
                        </td></tr>

                        <!-- Services Section -->
                        <tr><td class="services-cell" style="padding:0 20px 20px 20px;">
                            <p style="margin:0 0 10px 0;font-size:11px;text-transform:uppercase;letter-spacing:0.06em;color:#94a3b8;font-weight:700;font-family:sans-serif;">WHAT WE OFFER</p>
                            <table border="0" cellpadding="0" cellspacing="0" width="100%" style="background:#fafbfc;border-radius:10px;border:1px solid #e2e8f0;overflow:hidden;width:100% !important;">
                                {services_html}
                            </table>
                        </td></tr>

                        <!-- CTA Button -->
                        <tr><td class="cta-cell" style="padding:8px 20px 28px 20px;" align="center">
                            <a href="mailto:{html_lib.escape(settings.SMTP_FROM_EMAIL or '')}" class="cta-button" style="display:inline-block;background:linear-gradient(135deg,#2563eb,#1d4ed8);color:#ffffff;font-size:14px;font-weight:700;padding:14px 30px;border-radius:10px;text-decoration:none;letter-spacing:0.01em;box-shadow:0 4px 12px rgba(37,99,235,0.25);font-family:sans-serif;">
                                Let's Talk — Reply to This Email
                            </a>
                            <p style="margin:10px 0 0 0;font-size:11px;color:#94a3b8;font-family:sans-serif;">Takes 2 minutes. No commitment.</p>
                        </td></tr>

                        <!-- Divider -->
                        <tr><td style="padding:0 20px;"><div style="border-top:1px solid #f1f5f9;height:1px;line-height:1px;">&nbsp;</div></td></tr>

                        <!-- Footer -->
                        <tr><td class="footer-cell" style="padding:20px 20px 24px 20px;background:#fafafa;">
                            <table border="0" cellpadding="0" cellspacing="0" width="100%" style="width:100% !important;">
                                <tr>
                                    <td>
                                        <p style="margin:0;font-size:11px;color:#94a3b8;line-height:1.5;font-family:sans-serif;">
                                            Sent by <strong style="color:#64748b;">{sender_name}</strong><br/>
                                            &copy; {year} Nexora AI &bull; Anand, Gujarat, India
                                        </p>
                                    </td>
                                    <td align="right" valign="top">
                                        <a href="#unsubscribe" style="font-size:11px;color:#94a3b8;text-decoration:underline;font-family:sans-serif;">Unsubscribe</a>
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



class AIEmailService:
    def __init__(self):
        self.api_key = settings.OPENROUTER_API_KEY
        self.model = settings.OPENROUTER_MODEL
        self.api_url = "https://openrouter.ai/api/v1/chat/completions"

    async def _call_openrouter(self, system_prompt: str, user_prompt: str, response_format: Optional[str] = None) -> str:
        """
        Sends requests asynchronously to OpenRouter API.
        Includes a fallback mechanism if keys are missing or API fails.
        """
        if not self.api_key:
            logger.warning("OPENROUTER_API_KEY not found. Fallback mode will be triggered.")
            raise ValueError("OpenRouter API key is missing.")

        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
            "HTTP-Referer": "http://localhost:3000",
            "X-Title": "Nexora AI Outreach System"
        }

        payload = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ],
            "temperature": 0.85
        }

        if response_format == "json":
            payload["response_format"] = {"type": "json_object"}

        async with httpx.AsyncClient(timeout=30.0) as client:
            try:
                response = await client.post(self.api_url, headers=headers, json=payload)
                response.raise_for_status()
                data = response.json()
                content = data["choices"][0]["message"]["content"]
                return content.strip()
            except httpx.HTTPStatusError as e:
                error_body = e.response.text
                logger.error(f"OpenRouter API returned HTTP {e.response.status_code}: {error_body}")
                raise
            except Exception as e:
                logger.error(f"Error calling OpenRouter: {str(e)}")
                raise

    async def generate_initial_email(self, lead: Any, campaign: Optional[Any] = None, has_website: bool = False) -> Dict[str, str]:
        """
        Agent 1 outreach generator.
        Creates a personalized subject and pitch body based on scraped business data.
        The pitch body is then injected into our branded HTML template.
        """
        if has_website:
            system_prompt = (
                "You are a sales outreach assistant for Nexora AI. Write a short, highly-personalized sales pitch (NOT a full email, no greetings like 'Hi' or sign-offs like 'Best regards').\n\n"
                "Structure your pitch body exactly as follows:\n"
                "1. Start with a natural, observations-based opening paragraph referencing their business and their existing website, explaining why we are reaching out.\n"
                "2. Introduce a list of 2-3 specific, high-impact growth points tailored to their category using clear bullet points (prefix with '- ' or '* '). Leave a blank line before and after the list for spacing.\n"
                "3. Conclude with a single brief sentence proposing a quick chat.\n\n"
                "Services to pitch (choose the 1-2 most relevant to their industry):\n"
                "- SEO to boost Google rankings & organic traffic\n"
                "- WhatsApp & Workflow Automations to save hours of manual operations\n"
                "- Web & App Scraping & custom Scraper APIs for automated data gathering\n"
                "- Web Dev upgrades for a faster, higher-converting user interface\n\n"
                "Keep the tone professional, friendly, and non-spammy. Stay around 100-140 words total. Do NOT invent fake ratings or reviews.\n"
                "CRITICAL VARIETY INSTRUCTION: To ensure outreach diversity, write a completely unique intro and vary the sentence structure. Do NOT reuse the same wording or phrasing structure across different emails.\n\n"
                "Return JSON: {\"subject\": \"...\", \"body\": \"...\"}"
            )
        else:
            system_prompt = (
                "You are a sales outreach assistant for Nexora AI. Write a short, highly-personalized sales pitch (NOT a full email, no greetings like 'Hi' or sign-offs like 'Best regards').\n\n"
                "Structure your pitch body exactly as follows:\n"
                "1. Start with a friendly, natural opening paragraph referencing their business and why having a professional online presence is critical for businesses in their category.\n"
                "2. Present 2-3 key features of a modern website using clean bullet points (prefix with '- ' or '* '). Leave a blank line before and after the list for spacing.\n"
                "3. Conclude with a brief proposal offering a free homepage mockup draft and asking if they are open to a quick chat.\n\n"
                "Tone must be consultative, professional, and warm. Stay around 100-140 words total. Do NOT invent fake ratings or reviews.\n"
                "CRITICAL VARIETY INSTRUCTION: To ensure outreach diversity, write a completely unique intro and vary the sentence structure. Do NOT reuse the same wording or phrasing structure across different emails.\n\n"
                "Return JSON: {\"subject\": \"...\", \"body\": \"...\"}"
            )

        lead_context = (
            f"Business Name: {lead.bussiness_name or 'Unknown'}\n"
            f"Category/Service: {lead.scraped_service or lead.category or 'Business Service'}\n"
            f"City: {lead.scraped_city or 'your city'}\n"
            f"Website: {lead.bussiness_website or 'Not specified'}\n"
            f"Address/Area: {lead.bussiness_area or 'Not specified'}\n"
            f"Rating: {lead.rating or 'No ratings'} (Reviews: {lead.total_review or '0'})\n"
        )
        if campaign:
            lead_context += (
                f"Campaign Description: {campaign.description or 'Custom growth partnership'}\n"
                f"Campaign Instructions: {campaign.email_template}\n"
            )

        try:
            content = await self._call_openrouter(system_prompt, lead_context, response_format="json")
            parsed = json.loads(content)
            if "subject" in parsed and "body" in parsed:
                # Wrap the AI pitch text in our branded HTML template
                parsed["html"] = build_html_email(lead, parsed["body"], has_website)
                return parsed
            raise ValueError("JSON missing 'subject' or 'body' keys.")
        except Exception as e:
            logger.warning(f"Failed to generate outreach via OpenRouter ({str(e)}). Using local fallback templates.")
            return self._fallback_generate_initial(lead, campaign, has_website)

    async def classify_reply(self, email_body: str) -> Dict[str, Any]:
        """
        Agent 2 reply classifier.
        Categorizes an incoming prospect reply to decide the next action.
        """
        system_prompt = (
            "You are an incoming email replies classifier. Classify the user email reply into one of these intents:\n"
            "- INTERESTED: Prospect wants a meeting, pricing info, or is interested in moving forward.\n"
            "- QUESTION: Prospect asks specific questions about services, location, or details.\n"
            "- OBJECTION: Prospect presents a barrier (e.g. too busy, no budget, already have a provider).\n"
            "- FOLLOW_UP_LATER: Prospect asks to check in later (e.g. next month, in 6 months).\n"
            "- NOT_INTERESTED: Prospect says no, thanks, not interested, but without explicitly asking to unsubscribe.\n"
            "- UNSUBSCRIBE: Prospect demands to unsubscribe, stop contacting, remove from list, or displays anger.\n"
            "- MEETING_REQUEST: Prospect asks directly for calendar links or suggests a calendar date/time.\n"
            "- NEEDS_HUMAN: Email contains complex requests or needs manual administrator attention.\n"
            "- UNKNOWN: The email reply cannot be categorized.\n\n"
            "You MUST return a JSON object with exactly these keys: 'intent', 'confidence', 'reason', 'suggested_action'.\n"
            "Example:\n"
            "{\n"
            "  \"intent\": \"INTERESTED\",\n"
            "  \"confidence\": 0.95,\n"
            "  \"reason\": \"Prospect asked for a package pricing catalog list.\",\n"
            "  \"suggested_action\": \"REPLY_WITH_PRICING\"\n"
            "}"
        )

        try:
            content = await self._call_openrouter(system_prompt, f"Prospect Email Reply:\n{email_body}", response_format="json")
            parsed = json.loads(content)
            if "intent" in parsed:
                parsed["intent"] = parsed["intent"].upper()
                return parsed
            raise ValueError("JSON missing 'intent' key.")
        except Exception as e:
            logger.warning(f"Failed to classify reply via OpenRouter ({str(e)}). Using local fallback heuristic classification.")
            return self._fallback_classify_reply(email_body)

    async def generate_followup(self, lead: Any, conversation_history: str, campaign: Any, has_website: bool = False) -> Dict[str, str]:
        """
        Agent 2 follow-up email generator.
        Generates a contextual follow-up message keeping the conversation thread alive.
        """
        system_prompt = (
            "You are a sales follow-up assistant. Write a short, professional follow-up email. "
            "Refer politely to the previous conversation history provided. Keep it under 80 words. "
            "Return a JSON object containing exactly 'subject' and 'body'."
        )

        user_prompt = (
            f"Business: {lead.bussiness_name or 'Unknown'}\n"
            f"Offer: {campaign.description or 'Growth solutions'}\n"
            f"Campaign Instructions: {campaign.email_template}\n"
            f"Conversation History:\n{conversation_history}"
        )

        try:
            content = await self._call_openrouter(system_prompt, user_prompt, response_format="json")
            parsed = json.loads(content)
            if "subject" in parsed and "body" in parsed:
                parsed["html"] = build_html_email(lead, parsed["body"], has_website)
                return parsed
            raise ValueError("JSON missing keys.")
        except Exception as e:
            logger.warning(f"Failed to generate follow-up via OpenRouter ({str(e)}). Using local follow-up fallback template.")
            fallback = self._fallback_followup(lead, campaign)
            fallback["html"] = build_html_email(lead, fallback["body"], has_website)
            return fallback

    def _fallback_generate_initial(self, lead: Any, campaign: Optional[Any] = None, has_website: bool = False) -> Dict[str, str]:
        biz_name = lead.bussiness_name or "your team"
        city = lead.scraped_city or "your area"
        service = lead.scraped_service or lead.category or "business"

        if has_website:
            subject = f"Growth & Automation ideas for {biz_name}"
            body = (
                f"I came across your business page while researching in {city} and was impressed by your work in {service}.\n\n"
                f"We specialize in helping businesses scale and automate operations. Based on your current setup, here is how we can help:\n\n"
                f"- SEO Rankings: Boost your Google search positions and drive organic client inquiries.\n"
                f"- Workflow Automations: Save hours of manual business operations and lead tracking.\n"
                f"- Scraper & Lead APIs: Set up automated systems to pull and scrape fresh industry data.\n\n"
                f"Would you be open to a quick 2-minute chat next week to see how these could fit?"
            )
        else:
            subject = f"Establishing a modern online presence for {biz_name}"
            body = (
                f"I noticed your business doing excellent work in {service} in {city}, but I couldn't find a website for your company online.\n\n"
                f"We help local businesses build trust and acquire clients by setting up modern online presences:\n\n"
                f"- Mobile-First Design: A fast, premium homepage optimized for smartphones.\n"
                f"- Google Maps SEO: Make your business searchable on Google Maps for local queries.\n"
                f"- WhatsApp Integrations: Automated customer replies and booking links.\n\n"
                f"We can draft a free custom homepage mockup for you. Would you be open to a quick 2-minute chat to review it?"
            )
        
        html_content = build_html_email(lead, body, has_website)
        return {"subject": subject, "body": body, "html": html_content}

    def _fallback_classify_reply(self, email_body: str) -> Dict[str, Any]:
        body_lower = email_body.lower()
        
        if any(w in body_lower for w in ["unsubscribe", "remove me", "stop contacting", "don't email", "no more emails", "remove"]):
            intent = "UNSUBSCRIBE"
            suggested = "SUPPRESS_AND_CANCEL"
            reason = "Keyword matches unsubscribe requests."
        elif any(w in body_lower for w in ["interested", "call", "schedule", "zoom", "meet", "pricing", "cost", "price", "tell me more"]):
            intent = "INTERESTED"
            suggested = "GENERATE_REPLY_AND_NOTIFY"
            reason = "Keyword matches positive interest or details inquiries."
        elif any(w in body_lower for w in ["no thanks", "not interested", "go away", "stop", "busy"]):
            intent = "NOT_INTERESTED"
            suggested = "CANCEL_CAMPAIGN"
            reason = "Prospect declined further conversation."
        else:
            intent = "QUESTION"
            suggested = "NOTIFY_ADMIN"
            reason = "Heuristic check default."
            
        return {
            "intent": intent,
            "confidence": 0.70,
            "reason": f"Fallback heuristic: {reason}",
            "suggested_action": suggested
        }

    def _fallback_followup(self, lead: Any, campaign: Optional[Any] = None) -> Dict[str, str]:
        biz_name = lead.bussiness_name or "your team"
        subject = f"Following up: Growth & Automation for {biz_name}"
        body = (
            f"Hi team at {biz_name},\n\n"
            f"I wanted to follow up on my previous note. I know you're busy running operations, "
            f"but I wanted to see if you had 2 minutes to check out our SEO, Web Dev, or Workflow Automation ideas for {biz_name}.\n\n"
            f"If not, no worries at all! Just let me know and I will stop following up.\n\n"
            f"Best,\n"
            f"{settings.SMTP_FROM_NAME}"
        )
        return {"subject": subject, "body": body}

ai_email_service = AIEmailService()
