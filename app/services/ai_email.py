import json
import logging
import httpx
from typing import Dict, Any, Optional
from app.core.config import settings

logger = logging.getLogger("ai_email_service")


def has_chinese_or_non_english(text: str) -> bool:
    """Detects if text contains Chinese, Japanese, Korean, or unwanted Asian scripts."""
    import re
    if not text:
        return False
    return bool(re.search(r'[\u4e00-\u9fff\u3040-\u30ff\uac00-\ud7af]', text))


def build_html_email(lead: Any, pitch_text: str, has_website: bool) -> str:
    """
    Builds an ultra-premium, responsive, and mobile-friendly HTML email template.
    Injects scraped lead data and AI-generated pitch text with bulletproof single-line CTA button & arrow alignment.
    Directs prospect to https://nexora-meet-b4aa.vercel.app/
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

    # Site redirect URL
    site_url = html_lib.escape(getattr(settings, "WEBSITE_URL", "https://nexora-meet-b4aa.vercel.app")).rstrip("/") + "/"

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
            ul_style = "margin:0 0 18px 0;padding-left:16px;font-size:14px;line-height:1.65;color:#334155;font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,sans-serif;"
            li_style = "margin:0 0 8px 0;color:#334155;"
            list_html = f'<ul style="{ul_style}">'
            for line in lines:
                clean_line = line.strip()
                for prefix in ["- ", "* ", "• ", "-", "*", "•"]:
                    if clean_line.startswith(prefix):
                        clean_line = clean_line[len(prefix):].strip()
                        break
                list_html += f'<li style="{li_style}">{clean_line}</li>'
            list_html += '</ul>'
            pitch_html += list_html
        else:
            paragraph_text = " ".join(lines)
            pitch_html += f'<p style="margin:0 0 18px 0;font-size:15px;line-height:1.65;color:#334155;font-family:-apple-system,BlinkMacSystemFont,\'Segoe UI\',Roboto,sans-serif;">{paragraph_text}</p>'

    # Services to highlight
    if has_website:
        services_list = [
            ("🔍", "SEO & Google Search Rankings", "Boost your local search visibility and organic customer traffic"),
            ("⚡", "WhatsApp & Lead Flow Automations", "Automate customer support, booking inquiries & operations"),
            ("📊", "Web & App Scraping APIs", "Extract competitive market data and build custom data scrapers"),
            ("🔧", "Modern UI/UX Web Upgrades", "Upgrade your existing site into a fast, high-converting experience"),
        ]
    else:
        services_list = [
            ("🌐", "Modern High-Speed Website Design", "Mobile-first, high-converting website built for your brand"),
            ("📈", "Local Search & Google Maps Setup", "Rank on Google Maps and local customer searches from day one"),
            ("💬", "Automated WhatsApp Lead Capture", "Instant customer response system and lead management"),
            ("🎨", "Free Homepage Concept Design", "We'll build a live homepage draft for your business — free"),
        ]

    services_html = ""
    for icon, title, desc in services_list:
        services_html += f"""
        <tr>
            <td style="padding:12px 18px;border-bottom:1px solid #f1f5f9;">
                <table border="0" cellpadding="0" cellspacing="0" width="100%">
                    <tr>
                        <td width="36" valign="top" style="font-size:22px;padding-right:12px;">{icon}</td>
                        <td>
                            <p style="margin:0;font-size:14px;font-weight:700;color:#0f172a;font-family:sans-serif;">{title}</p>
                            <p style="margin:3px 0 0 0;font-size:12px;color:#64748b;line-height:1.45;font-family:sans-serif;">{desc}</p>
                        </td>
                    </tr>
                </table>
            </td>
        </tr>"""

    # Lead context badge with left border accent
    website_link_html = ""
    if website and website.lower() not in ('not specified', 'none'):
        website_link_html = f'<br/>🌐 <a href="{website}" style="color:#2563eb;text-decoration:none;word-break:break-all;font-size:12px;font-weight:600;">{website}</a>'

    context_badge = f"""
    <table border="0" cellpadding="0" cellspacing="0" width="100%" style="background:#f8fafc;border-radius:12px;margin-bottom:24px;border:1px solid #e2e8f0;border-left:4px solid #6366f1;width:100% !important;">
        <tr>
            <td style="padding:18px 20px;">
                <p style="margin:0 0 6px 0;font-size:10px;text-transform:uppercase;letter-spacing:0.08em;color:#6366f1;font-weight:800;font-family:sans-serif;">PREPARED EXCLUSIVELY FOR</p>
                <p style="margin:0 0 6px 0;font-size:17px;font-weight:800;color:#0f172a;font-family:sans-serif;line-height:1.2;">{biz_name}</p>
                <p style="margin:0;font-size:12px;color:#64748b;font-family:sans-serif;line-height:1.5;word-break:break-word;">
                    📍 {city} &nbsp;&bull;&nbsp; 🏷️ {service}
                    {'&nbsp;&bull;&nbsp; ⭐ ' + rating + ' (' + reviews + ' reviews)' if rating else ''}
                    {website_link_html}
                </p>
            </td>
        </tr>
    </table>"""

    year = datetime.now().year
    sender_name = html_lib.escape(settings.SMTP_FROM_NAME or "Nexora AI Team")

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width,initial-scale=1.0">
    <title>Partnership Opportunity — {biz_name}</title>
    <style>
        @media only screen and (max-width: 600px) {{
            .main-table {{ padding: 12px 4px !important; }}
            .content-cell {{ padding: 20px 16px 8px 16px !important; }}
            .services-cell {{ padding: 0 16px 20px 16px !important; }}
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
                    <div style="margin-top:6px;">
                        <span style="display:inline-block;font-size:10px;font-weight:700;letter-spacing:0.08em;text-transform:uppercase;color:#818cf8;background:rgba(99,102,241,0.15);padding:4px 12px;border-radius:20px;border:1px solid rgba(99,102,241,0.3);font-family:sans-serif;">
                            OFFICIAL PARTNERSHIP INVITATION
                        </span>
                    </div>
                </td></tr>

                <!-- Main Email Card -->
                <tr><td>
                    <table border="0" cellpadding="0" cellspacing="0" width="100%" style="background:#ffffff;border-radius:20px;overflow:hidden;border:1px solid #334155;box-shadow:0 20px 40px rgba(0,0,0,0.3);width:100% !important;">
                        
                        <!-- Top Accent Line -->
                        <tr><td style="background:linear-gradient(135deg,#6366f1 0%,#2563eb 50%,#06b6d4 100%);height:6px;line-height:6px;font-size:6px;">&nbsp;</td></tr>
                        
                        <!-- Content Area -->
                        <tr><td class="content-cell" style="padding:28px 24px 8px 24px;">
                            {context_badge}
                            {pitch_html}
                        </td></tr>

                        <!-- Services Section -->
                        <tr><td class="services-cell" style="padding:0 24px 24px 24px;">
                            <p style="margin:0 0 12px 0;font-size:11px;text-transform:uppercase;letter-spacing:0.08em;color:#64748b;font-weight:800;font-family:sans-serif;">OUR CORE CAPABILITIES</p>
                            <table border="0" cellpadding="0" cellspacing="0" width="100%" style="background:#f8fafc;border-radius:12px;border:1px solid #e2e8f0;overflow:hidden;width:100% !important;">
                                {services_html}
                            </table>
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
                                Direct Website Link: <a href="{site_url}" target="_blank" style="color:#4f46e5;text-decoration:underline;font-weight:600;">{site_url}</a>
                            </p>
                        </td></tr>

                        <!-- Divider -->
                        <tr><td style="padding:0 24px;"><div style="border-top:1px solid #f1f5f9;height:1px;line-height:1px;">&nbsp;</div></td></tr>

                        <!-- Footer -->
                        <tr><td class="footer-cell" style="padding:22px 24px 26px 24px;background:#fafafa;">
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
            "temperature": 0.70
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
        strict_lang_instruction = "CRITICAL MANDATORY INSTRUCTION: You MUST write ALL content strictly in clean, professional ENGLISH. You are STRICTLY FORBIDDEN from using Chinese characters, Kanji, or any non-English script. Do NOT output Chinese text under any circumstances.\n\n"

        if has_website:
            system_prompt = (
                strict_lang_instruction +
                "You are a sales outreach assistant for Nexora AI. Write a short, highly-personalized sales pitch in English (NOT a full email, no greetings like 'Hi' or sign-offs like 'Best regards').\n\n"
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
                "Return JSON: {\"subject\": \"...\", \"body\": \"...\"}"
            )
        else:
            system_prompt = (
                strict_lang_instruction +
                "You are a sales outreach assistant for Nexora AI. Write a short, highly-personalized sales pitch in English (NOT a full email, no greetings like 'Hi' or sign-offs like 'Best regards').\n\n"
                "Structure your pitch body exactly as follows:\n"
                "1. Start with a friendly, natural opening paragraph referencing their business and why having a professional online presence is critical for businesses in their category.\n"
                "2. Present 2-3 key features of a modern website using clean bullet points (prefix with '- ' or '* '). Leave a blank line before and after the list for spacing.\n"
                "3. Conclude with a brief proposal offering a free homepage mockup draft and asking if they are open to a quick chat.\n\n"
                "Tone must be consultative, professional, and warm. Stay around 100-140 words total. Do NOT invent fake ratings or reviews.\n"
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
                # Intercept Chinese / non-English output and force fallback if detected
                if has_chinese_or_non_english(parsed["subject"]) or has_chinese_or_non_english(parsed["body"]):
                    logger.warning(f"AI generated non-English/Chinese text for lead '{lead.bussiness_name}'. Rejecting and using local English fallback template.")
                    return self._fallback_generate_initial(lead, campaign, has_website)

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
        strict_lang_instruction = "CRITICAL MANDATORY INSTRUCTION: You MUST write ALL content strictly in clean, professional ENGLISH. You are STRICTLY FORBIDDEN from using Chinese characters or non-English script. Do NOT output Chinese text under any circumstances.\n\n"

        system_prompt = (
            strict_lang_instruction +
            "You are a sales follow-up assistant. Write a short, professional follow-up email in English. "
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
                # Intercept Chinese / non-English output and force fallback if detected
                if has_chinese_or_non_english(parsed["subject"]) or has_chinese_or_non_english(parsed["body"]):
                    logger.warning(f"AI generated non-English/Chinese follow-up for lead '{lead.bussiness_name}'. Rejecting and using local English fallback template.")
                    fallback = self._fallback_followup(lead, campaign)
                    fallback["html"] = build_html_email(lead, fallback["body"], has_website)
                    return fallback

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
