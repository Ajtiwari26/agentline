import os
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import logging
import requests
import sys

# Import local db methods
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import config
from db.database import log_email, get_lead

logger = logging.getLogger(__name__)

# Base URL for hosted email assets on Vercel
EMAIL_ASSETS_URL = "https://email-service-five-orpin.vercel.app"

# ──────────────────────────────────────────────────
# Plain-text templates (CourseWallah modes purged)
# ──────────────────────────────────────────────────
# Purged CourseWallah plain-text templates to ensure only Nukkad Tech Solutions
# content is ever sent to business clients.


# ──────────────────────────────────────────────────
# Gemini-powered personalization
# ──────────────────────────────────────────────────
def _generate_personalized_pitch(lead_data: dict) -> dict:
    """
    Uses Gemini 2.5 Flash to generate personalized pitch + callout.
    Falls back to generic values if Gemini fails or no lead data exists.
    """
    import config
    company = getattr(config, "COMPANY", "nukkad").lower()

    if company == "bla_bli_blu":
        default_pitch = (
            "Thanks for speaking with our fragrance consultant Kavya today! We loved discussing your scent preferences. "
            "At Bla Bli Blu, we craft designer-grade perfumes with a 25% fragrance oil concentration that dry down "
            "into rich, luxurious notes. Try our Risk-Free Scent Trial discovery packs today and find your signature scent!"
        )
        default_callout = (
            "Get <b style=\"color:#2563EB;\">100% wallet cashback</b> on your discovery pack, making your "
            "<b style=\"color:#2563EB;\">scent trial absolutely free</b> when you upgrade to a full bottle."
        )
    else:
        default_pitch = (
            "Thanks for speaking with our AI voice assistant today! We loved learning about your business. "
            "Nukkad Tech Solutions can revolutionize your operations by automating crucial "
            "tasks like lead follow-ups and customer inquiries, ensuring timely engagement with every "
            "potential client. Our platform can seamlessly manage scheduling, dispatch information "
            "via WhatsApp and email, and significantly streamline your day-to-day operations."
        )
        default_callout = (
            "This comprehensive automation will not only <b style=\"color:#DC2626;\">save your team valuable time</b> "
            "and <b style=\"color:#DC2626;\">reduce administrative costs</b>, but also "
            "<b style=\"color:#DC2626;\">improve lead conversion rates</b>, ultimately boosting your growth and revenue."
        )

    result = {"pitch": default_pitch, "callout": default_callout}

    if not lead_data:
        return result

    name = lead_data.get("name", "")
    notes = lead_data.get("notes", "")
    interest = lead_data.get("interest_level", "")

    if not notes and not name:
        return result

    try:
        from google import genai
        sa_key_path = os.getenv("GOOGLE_APPLICATION_CREDENTIALS", "")
        if sa_key_path and os.path.exists(sa_key_path):
            from google.oauth2 import service_account
            scopes = ["https://www.googleapis.com/auth/cloud-platform"]
            credentials = service_account.Credentials.from_service_account_file(sa_key_path, scopes=scopes)
            client = genai.Client(
                vertexai=True,
                project=os.getenv("GCP_PROJECT", "igsl-67e70"),
                location="us-central1",
                credentials=credentials
            )
        else:
            client = genai.Client(api_key=getattr(config, "GEMINI_API_KEY", ""))

        if company == "bla_bli_blu":
            prompt = f"""You are writing two pieces of text for a personalized customer email from a premium fragrance brand.

Lead Name: {name}
Customer Notes (Scent preferences, review feedback, or interests): {notes}
Interest Level: {interest}

Generate a JSON object with exactly two keys:
1. "pitch": Start with "Thanks for speaking with our fragrance consultant Kavya today! We loved discussing your scent preferences." Then 2-3 MORE sentences recommending Bla Bli Blu's trial set, combos, or specific perfume types (like Old Money for office wear, Love Drunk for nights out, By the Beach for fresh wear, or Lights Off for rich sweetness) based on their notes.
2. "callout": A single impactful sentence about our 100% cashback offer. Include HTML bold+blue tags around 3 key benefit phrases, like: This makes your <b style="color:#2563EB;">scent trial absolutely free</b> by giving you <b style="color:#2563EB;">100% wallet cashback</b> to buy your <b style="color:#2563EB;">signature full-size bottle</b>.

Output ONLY valid JSON. No markdown backticks.
{{
  "pitch": "...",
  "callout": "..."
}}"""
        else:
            prompt = f"""You are writing two pieces of text for a personalized business email.

Lead Name: {name}
Business Notes: {notes}
Interest Level: {interest}

Generate a JSON object with exactly two keys:
1. "pitch": Start with "Thanks for speaking with our AI voice assistant today! We loved learning about your business." Then 2-3 MORE sentences explaining how Nukkad Tech Solutions can specifically help THIS lead's business. Be specific to their industry.
2. "callout": A single impactful sentence about quantitative benefits. Include HTML bold+red tags around 3 key benefit phrases, like: This will not only <b style="color:#DC2626;">save your team valuable time</b> and <b style="color:#DC2626;">reduce costs</b>, but also <b style="color:#DC2626;">improve conversion rates</b>.

Output ONLY valid JSON. No markdown backticks.
{{
  "pitch": "...",
  "callout": "..."
}}"""

        response = client.models.generate_content(
            model="gemini-2.5-flash",
            contents=prompt
        )
        import json
        text_response = response.text.strip()
        if text_response.startswith("```json"):
            text_response = text_response[7:]
        if text_response.startswith("```"):
            text_response = text_response[3:]
        if text_response.endswith("```"):
            text_response = text_response[:-3]
        
        parsed = json.loads(text_response.strip())
        if "pitch" in parsed and "callout" in parsed:
            logger.info("Successfully generated personalized pitch and callout via Gemini.")
            return parsed
        
    except Exception as e:
        logger.error(f"Gemini personalization failed: {e}. Using defaults.")
        
    return result


# ──────────────────────────────────────────────────
# Designer HTML email template — Gmail-compatible
# Uses hosted images, emoji icons, pure HTML/CSS
# NO SVGs, NO data: URIs (Gmail strips both)
# ──────────────────────────────────────────────────
def _build_blabliblu_email_html(lead_name: str, pitch_text: str, callout_text: str) -> str:
    logo_url = "https://images.unsplash.com/photo-1541643600914-78b084683601?auto=format&fit=crop&q=80&w=200"
    hero_image_url = "https://images.unsplash.com/photo-1594035910387-fea47794261f?auto=format&fit=crop&q=80&w=600"
    display_name = lead_name if lead_name else "there"

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8"/>
<meta content="width=device-width, initial-scale=1.0" name="viewport"/>
<title>Discover Bla Bli Blu Fragrances</title>
<link href="https://fonts.googleapis.com" rel="preconnect"/>
<link crossorigin="" href="https://fonts.gstatic.com" rel="preconnect"/>
<link href="https://fonts.googleapis.com/css2?family=Playfair+Display:ital,wght@0,600;0,700;1,400&family=Inter:wght@400;500;600;700&display=swap" rel="stylesheet"/>
</head>
<body style="margin:0; padding:0; background-color:#f4f6fa; font-family:'Inter', sans-serif; color:#1e293b; -webkit-font-smoothing:antialiased;">
<table border="0" cellpadding="0" cellspacing="0" width="100%" style="background-color:#f4f6fa; padding:40px 0;">
  <tr>
    <td align="center">
      <table border="0" cellpadding="0" cellspacing="0" width="100%" style="max-width:600px; background-color:#ffffff; border:1px solid #e2e8f0; border-radius:16px; overflow:hidden; box-shadow:0 4px 20px rgba(15,23,42,0.05);">
        
        <!-- Header -->
        <tr>
          <td align="center" style="padding:32px 24px; background-color:#0f172a; color:#ffffff;">
            <h1 style="font-family:'Playfair Display', serif; font-size:36px; font-weight:700; margin:0; letter-spacing:0.05em; color:#3b82f6;">BLA BLA BLU</h1>
            <p style="font-family:'Inter', sans-serif; font-size:14px; text-transform:uppercase; letter-spacing:0.2em; margin:8px 0 0 0; opacity:0.8;">Luxury French Grade Perfumes</p>
          </td>
        </tr>
        
        <!-- Body Content -->
        <tr>
          <td style="padding:32px 24px;">
            <!-- Greeting -->
            <h2 style="font-family:'Playfair Display', serif; font-size:22px; font-weight:600; color:#0f172a; margin:0 0 20px 0;">Dearest {display_name},</h2>
            
            <!-- Hero Section -->
            <div style="margin-bottom:40px;">
              <p style="font-family:'Inter', sans-serif; font-size:16px; line-height:1.7; color:#475569; margin:0 0 24px 0;">
                {pitch_text}
              </p>
              <img src="{hero_image_url}" alt="Premium Fragrances" width="100%" style="width:100%; height:auto; border-radius:12px; display:block; border:1px solid #e2e8f0;" />
            </div>
            
            <!-- Offer Strip -->
            <table border="0" cellpadding="0" cellspacing="0" width="100%" style="background-color:#eff6ff; border-left:4px solid #2563eb; border-radius:8px; margin-bottom:40px;">
              <tr>
                <td style="padding:24px;">
                  <p style="font-family:'Inter', sans-serif; font-size:13px; font-weight:700; color:#2563eb; margin:0 0 6px 0; text-transform:uppercase; letter-spacing:0.1em;">Risk-Free Scent Trial</p>
                  <p style="font-family:'Inter', sans-serif; font-size:15px; color:#1e3a8a; margin:0; line-height:1.5;">{callout_text}</p>
                </td>
              </tr>
            </table>
            
            <!-- Fragrance Collection Grid -->
            <h3 style="font-family:'Playfair Display', serif; font-size:24px; font-weight:600; color:#0f172a; margin:0 0 24px 0; text-align:center;">Our Signature Collections</h3>
            
            <table border="0" cellpadding="0" cellspacing="0" width="100%" style="margin-bottom:32px;">
              <tr>
                <!-- Col 1 -->
                <td width="50%" valign="top" style="padding-right:10px; padding-bottom:20px;">
                  <div style="background-color:#f8fafc; border:1px solid #e2e8f0; border-radius:8px; padding:20px; min-height:140px;">
                    <div style="font-size:20px; margin-bottom:8px;">💼</div>
                    <h4 style="font-family:'Playfair Display', serif; font-size:16px; font-weight:700; color:#0f172a; margin:0 0 4px 0;">Old Money</h4>
                    <p style="font-family:'Inter', sans-serif; font-size:13px; color:#64748b; margin:0; line-height:1.4;">Crisp green apple, damask rose, cedarwood, tonka. Perfect for executive confidence.</p>
                  </div>
                </td>
                <!-- Col 2 -->
                <td width="50%" valign="top" style="padding-left:10px; padding-bottom:20px;">
                  <div style="background-color:#f8fafc; border:1px solid #e2e8f0; border-radius:8px; padding:20px; min-height:140px;">
                    <div style="font-size:20px; margin-bottom:8px;">❤️</div>
                    <h4 style="font-family:'Playfair Display', serif; font-size:16px; font-weight:700; color:#0f172a; margin:0 0 4px 0;">Love Drunk</h4>
                    <p style="font-family:'Inter', sans-serif; font-size:13px; color:#64748b; margin:0; line-height:1.4;">Warm cinnamon, sweet dates, praline, vanilla. An alluring and romantic statement.</p>
                  </div>
                </td>
              </tr>
              <tr>
                <!-- Col 3 -->
                <td width="50%" valign="top" style="padding-right:10px;">
                  <div style="background-color:#f8fafc; border:1px solid #e2e8f0; border-radius:8px; padding:20px; min-height:140px;">
                    <div style="font-size:20px; margin-bottom:8px;">🌊</div>
                    <h4 style="font-family:'Playfair Display', serif; font-size:16px; font-weight:700; color:#0f172a; margin:0 0 4px 0;">By The Beach</h4>
                    <p style="font-family:'Inter', sans-serif; font-size:13px; color:#64748b; margin:0; line-height:1.4;">Fresh lemon, bergamot, crisp apple, aquatic musk. Uplifting and energizing.</p>
                  </div>
                </td>
                <!-- Col 4 -->
                <td width="50%" valign="top" style="padding-left:10px;">
                  <div style="background-color:#f8fafc; border:1px solid #e2e8f0; border-radius:8px; padding:20px; min-height:140px;">
                    <div style="font-size:20px; margin-bottom:8px;">✨</div>
                    <h4 style="font-family:'Playfair Display', serif; font-size:16px; font-weight:700; color:#0f172a; margin:0 0 4px 0;">Lights Off</h4>
                    <p style="font-family:'Inter', sans-serif; font-size:13px; color:#64748b; margin:0; line-height:1.4;">Passionfruit, sweet caramel, rich amber. Seductive, sweet, and mysterious.</p>
                  </div>
                </td>
              </tr>
            </table>
            
            <!-- CTA Section -->
            <div style="text-align:center; margin-top:40px;">
              <a href="https://blabliblu.in/" style="display:inline-block; background-color:#2563eb; color:#ffffff; border-radius:8px; padding:14px 28px; font-family:'Inter', sans-serif; font-size:14px; font-weight:600; text-decoration:none; box-shadow:0 4px 6px -1px rgba(37,99,235,0.2);">
                Order Trial Set
              </a>
            </div>
          </td>
        </tr>
        
        <!-- Footer -->
        <tr>
          <td align="center" style="background-color:#0f172a; padding:40px 24px; text-align:center;">
            <div style="font-family:'Playfair Display', serif; font-size:20px; font-weight:700; color:#ffffff; margin-bottom:8px; letter-spacing:0.05em;">
              Bla Bli Blu Perfumes
            </div>
            <div style="font-family:'Inter', sans-serif; font-size:13px; color:#94a3b8; margin-bottom:20px;">
              © 2026 Bla Bli Blu. All rights reserved.
            </div>
            <div style="font-family:'Inter', sans-serif; font-size:12px;">
              <a href="#" style="color:#3b82f6; text-decoration:none; margin:0 8px;">Unsubscribe</a> | 
              <a href="#" style="color:#3b82f6; text-decoration:none; margin:0 8px;">Privacy Policy</a> | 
              <a href="mailto:support@blabliblu.in" style="color:#3b82f6; text-decoration:none; margin:0 8px;">Contact Us</a>
            </div>
          </td>
        </tr>
        
      </table>
    </td>
  </tr>
</table>
</body>
</html>"""

def _build_portfolio_html(lead_name: str, pitch_text: str, callout_text: str) -> str:
    logo_url = f"{EMAIL_ASSETS_URL}/logo.png"
    ai_phone_url = f"{EMAIL_ASSETS_URL}/ai-phone.png"
    display_name = lead_name if lead_name else "there"

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8"/>
<meta content="width=device-width, initial-scale=1.0" name="viewport"/>
<title>Nukkad Tech Solutions Newsletter</title>
<link href="https://fonts.googleapis.com" rel="preconnect"/>
<link crossorigin="" href="https://fonts.gstatic.com" rel="preconnect"/>
<link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;600;700&amp;family=Sora:wght@600;700&amp;display=swap" rel="stylesheet"/>
</head>
<body style="margin:0; padding:0; background-color:#f7f9fd; font-family:'Inter', sans-serif; color:#191c1f; -webkit-font-smoothing:antialiased;">
<table border="0" cellpadding="0" cellspacing="0" width="100%" style="background-color:#f7f9fd; padding:40px 0;">
  <tr>
    <td align="center">
      <table border="0" cellpadding="0" cellspacing="0" width="100%" style="max-width:600px; background-color:#ffffff; border:1px solid #e0e2e6; border-radius:12px; overflow:hidden; box-shadow:0 4px 25px rgba(0,0,0,0.06);">
        
        <!-- Header -->
        <tr>
          <td align="center" style="padding:24px; border-bottom:1px solid #e0e2e6; background-color:#ffffff;">
            <picture>
              <source srcset="https://nukkadtechsolutions.vercel.app/full-logo.svg" type="image/svg+xml">
              <img src="{logo_url}" width="220" height="auto" alt="Nukkad Tech Solutions" style="display:block; max-width:220px; height:auto;" />
            </picture>
          </td>
        </tr>
        
        <!-- Body Content -->
        <tr>
          <td style="padding:32px 24px;">
            <!-- Greeting -->
            <h2 style="font-family:'Sora', sans-serif; font-size:24px; font-weight:600; color:#111827; margin:0 0 24px 0;">Hi <b>{display_name}</b>,</h2>
            
            <!-- Hero Section -->
            <div style="margin-bottom:48px;">
              <h1 style="font-family:'Sora', sans-serif; font-size:32px; font-weight:600; color:#111827; margin:0 0 12px 0; line-height:1.3;">Your AI Strategy for Growth</h1>
              <p style="font-family:'Inter', sans-serif; font-size:16px; line-height:1.6; color:#4b5563; margin:0 0 24px 0;">
                {pitch_text}
              </p>
              <img src="{ai_phone_url}" alt="AI Strategy Visualization" width="100%" style="width:100%; height:auto; border-radius:8px; display:block; border:1px solid #e0e2e6;" />
            </div>
            
            <!-- Metrics Strip -->
            <table border="0" cellpadding="0" cellspacing="0" width="100%" style="background-color:#191c1f; border-radius:8px; margin-bottom:48px;">
              <tr>
                <td style="padding:24px; text-align:center;">
                  <p style="font-family:'Inter', sans-serif; font-size:14px; font-weight:600; color:#fff6f5; margin:0 0 4px 0; text-transform:uppercase; letter-spacing:0.05em;">Potential ROI</p>
                  <p style="font-family:'Sora', sans-serif; font-size:40px; font-weight:700; color:#dc2626; margin:0 0 4px 0;">70%</p>
                  <p style="font-family:'Inter', sans-serif; font-size:14px; color:#e0e2e6; margin:0;">{callout_text}</p>
                </td>
              </tr>
            </table>
            
            <!-- Solutions Grid Section -->
            <h3 style="font-family:'Sora', sans-serif; font-size:24px; font-weight:600; color:#111827; margin:0 0 24px 0; text-align:center;">Our Core Solutions</h3>
            
            <table border="0" cellpadding="0" cellspacing="0" width="100%" style="margin-bottom:32px;">
              <tr>
                <!-- Col 1 -->
                <td width="50%" valign="top" style="padding-right:12px; padding-bottom:24px;">
                  <div style="background-color:#ffffff; border:1px solid #e0e2e6; border-radius:8px; padding:24px; min-height:140px;">
                    <div style="font-size:24px; margin-bottom:12px;">📞</div>
                    <h4 style="font-family:'Inter', sans-serif; font-size:14px; font-weight:600; color:#111827; margin:0 0 4px 0;">Voice AI Agents</h4>
                    <p style="font-family:'Inter', sans-serif; font-size:14px; color:#4b5563; margin:0; line-height:1.4;">Autonomous inbound & outbound calling agents that handle sales and support 24/7.</p>
                  </div>
                </td>
                <!-- Col 2 -->
                <td width="50%" valign="top" style="padding-left:12px; padding-bottom:24px;">
                  <div style="background-color:#ffffff; border:1px solid #e0e2e6; border-radius:8px; padding:24px; min-height:140px;">
                    <div style="font-size:24px; margin-bottom:12px;">💬</div>
                    <h4 style="font-family:'Inter', sans-serif; font-size:14px; font-weight:600; color:#111827; margin:0 0 4px 0;">WhatsApp CRM</h4>
                    <p style="font-family:'Inter', sans-serif; font-size:14px; color:#4b5563; margin:0; line-height:1.4;">AI-powered WhatsApp bots that resolve inquiries, book meetings, and update CRMs.</p>
                  </div>
                </td>
              </tr>
              <tr>
                <!-- Col 3 -->
                <td width="50%" valign="top" style="padding-right:12px;">
                  <div style="background-color:#ffffff; border:1px solid #e0e2e6; border-radius:8px; padding:24px; min-height:140px;">
                    <div style="font-size:24px; margin-bottom:12px;">🤖</div>
                    <h4 style="font-family:'Inter', sans-serif; font-size:14px; font-weight:600; color:#111827; margin:0 0 4px 0;">Chat Agents</h4>
                    <p style="font-family:'Inter', sans-serif; font-size:14px; color:#4b5563; margin:0; line-height:1.4;">Intelligent website chatbots trained directly on your business docs.</p>
                  </div>
                </td>
                <!-- Col 4 -->
                <td width="50%" valign="top" style="padding-left:12px;">
                  <div style="background-color:#ffffff; border:1px solid #e0e2e6; border-radius:8px; padding:24px; min-height:140px;">
                    <div style="font-size:24px; margin-bottom:12px;">⚙️</div>
                    <h4 style="font-family:'Inter', sans-serif; font-size:14px; font-weight:600; color:#111827; margin:0 0 4px 0;">Workflow Auto</h4>
                    <p style="font-family:'Inter', sans-serif; font-size:14px; color:#4b5563; margin:0; line-height:1.4;">Automate business notifications, approvals, and data sync between siloed apps.</p>
                  </div>
                </td>
              </tr>
            </table>
            
            <!-- CTA Section -->
            <div style="text-align:center; margin-top:40px;">
              <a href="https://nukkadtechsolutions.vercel.app/" style="display:inline-block; background-color:#dc2626; color:#ffffff; border-radius:8px; padding:12px 24px; font-family:'Inter', sans-serif; font-size:14px; font-weight:600; text-decoration:none;">
                Book a Demo
              </a>
            </div>
          </td>
        </tr>
        
        <!-- Footer -->
        <tr>
          <td align="center" style="background-color:#2d3134; padding:48px 24px; text-align:center;">
            <div style="font-family:'Sora', sans-serif; font-size:20px; font-weight:700; color:#ffffff; margin-bottom:12px;">
              Nukkad Tech Solutions
            </div>
            <div style="font-family:'Inter', sans-serif; font-size:14px; color:#e0e2e6; opacity:0.8; margin-bottom:24px;">
              © 2026 Nukkad Tech Solutions. All rights reserved.
            </div>
            <div style="font-family:'Inter', sans-serif; font-size:12px;">
              <a href="#" style="color:#e0e2e6; text-decoration:none; margin:0 8px; opacity:0.8;">Unsubscribe</a> | 
              <a href="#" style="color:#e0e2e6; text-decoration:none; margin:0 8px; opacity:0.8;">Privacy Policy</a> | 
              <a href="mailto:ajay.nukkadtechsolutions@gmail.com" style="color:#e0e2e6; text-decoration:none; margin:0 8px; opacity:0.8;">Contact Us</a>
            </div>
          </td>
        </tr>
        
      </table>
    </td>
  </tr>
</table>
</body>
</html>"""


# ──────────────────────────────────────────────────
# Email sending functions
# ──────────────────────────────────────────────────
def send_email_via_smtp(to_email: str, subject: str, body: str, content_type: str = "plain") -> bool:
    """Sends email via Vercel SMTP proxy to bypass Render port restrictions."""
    if not config.SMTP_USER or not config.SMTP_PASSWORD:
        logger.error("SMTP credentials missing in configuration.")
        return False
        
    payload = {
        "to_email": to_email,
        "subject": subject,
        "body": body,
        "smtp_user": config.SMTP_USER,
        "smtp_password": config.SMTP_PASSWORD,
        "email_from": config.EMAIL_FROM or config.SMTP_USER,
        "content_type": content_type
    }
    
    url = getattr(config, "EMAIL_PROXY_URL", "https://email-service-five-orpin.vercel.app/api/send")
    logger.info(f"Forwarding email request to Vercel proxy: {url}")
    
    try:
        response = requests.post(url, json=payload, headers={"Content-Type": "application/json"}, timeout=15)
        if response.status_code == 200:
            res_data = response.json()
            if res_data.get("success"):
                logger.info(f"Email successfully sent to {to_email} via Vercel SMTP proxy.")
                return True
            else:
                logger.error(f"Vercel email proxy returned failure: {res_data.get('error')}")
                return False
        else:
            logger.error(f"Vercel email proxy failed with status {response.status_code}: {response.text}")
            return False
    except Exception as e:
        logger.error(f"Failed to communicate with Vercel email proxy: {e}")
        return False

def send_email_via_resend(to_email: str, subject: str, body: str, content_type: str = "plain") -> bool:
    """Sends email via Resend API."""
    if not config.RESEND_API_KEY:
        logger.error("Resend API key missing in configuration.")
        return False
        
    url = "https://api.resend.com/emails"
    headers = {
        "Authorization": f"Bearer {config.RESEND_API_KEY}",
        "Content-Type": "application/json"
    }
    
    company = getattr(config, "COMPANY", "nukkad").lower()
    if company == "bla_bli_blu":
        sender_name = "Bla Bli Blu"
    else:
        mode = getattr(config, "AGENT_MODE", "portfolio")
        sender_name = "Nukkad Tech Solutions" if mode == "portfolio" else "CourseWallah"
    
    payload = {
        "from": config.EMAIL_FROM or f"{sender_name} <onboarding@resend.dev>",
        "to": [to_email],
        "subject": subject,
    }
    
    if content_type == "html":
        payload["html"] = body
    else:
        payload["text"] = body
    
    try:
        response = requests.post(url, json=payload, headers=headers, timeout=10)
        if response.status_code in [200, 201]:
            logger.info(f"Email successfully sent to {to_email} via Resend.")
            return True
        else:
            logger.error(f"Resend failed with status {response.status_code}: {response.text}")
            return False
    except Exception as e:
        logger.error(f"Resend email sending failed: {e}")
        return False


# ──────────────────────────────────────────────────
# Main entry point (called by pipeline tool handler)
# ──────────────────────────────────────────────────
def send_template_email(phone: str, to_email: str, template_name: str = "syllabus") -> str:
    """
    Sends a personalized designer HTML portfolio email for Nukkad Tech Solutions to the user.
    Purged of all CourseWallah templates to guarantee only Nukkad Tech Solutions content is sent.
    """
    invalid_emails = ["lead@example.com", "example@example.com", "user@example.com", "test@example.com", ""]
    if not to_email or to_email.strip().lower() in invalid_emails or "@" not in to_email or "example" in to_email.lower():
        logger.warning(f"Email tool called with invalid/placeholder email: '{to_email}'. Returning early.")
        return "ERROR: No valid email address was provided. You must ask the user for their real email address during the call before sending an email. Do NOT retry this tool until you have a real email."
    
    logger.info(f"Building personalized HTML portfolio email for {to_email} (Phone: {phone})")
    
    lead_data = None
    try:
        lead_data = get_lead(phone)
        if lead_data:
            logger.info(f"Loaded lead context: name={lead_data.get('name')}, notes={lead_data.get('notes', '')[:60]}...")
    except Exception as e:
        logger.error(f"Failed to load lead data: {e}")
    
    personalization = _generate_personalized_pitch(lead_data)
    pitch_text = personalization["pitch"]
    callout_text = personalization["callout"]
    
    lead_name = lead_data.get("name", "") if lead_data else ""
    
    import config
    company = getattr(config, "COMPANY", "nukkad").lower()
    
    if company == "bla_bli_blu":
        html_body = _build_blabliblu_email_html(lead_name, pitch_text, callout_text)
        if "price" in template_name.lower() or "pricing" in template_name.lower():
            subject = f"Exclusive Pricing & Fragrance Combo Deals for {lead_name or 'You'} ⚡"
        else:
            subject = f"Your Custom Fragrance Recommendations from Bla Bli Blu ⚡"
    else:
        html_body = _build_portfolio_html(lead_name, pitch_text, callout_text)
        # Customize subject line based on template name request
        if "price" in template_name.lower() or "pricing" in template_name.lower():
            subject = f"Pricing & Automation Proposal for {lead_name or 'Your Business'} ⚡"
        else:
            subject = f"AI Automation Opportunity for {lead_name or 'Your Business'} ⚡"
        
    content_type = "html"
    body = html_body
    
    logger.info(f"Triggering Nukkad Tech Solutions email for {to_email} (Phone: {phone}) (subject: {subject})")
    
    success = False
    if getattr(config, "RESEND_API_KEY", None):
        success = send_email_via_resend(to_email, subject, body, content_type)
    else:
        success = send_email_via_smtp(to_email, subject, body, content_type)
        
    status = "sent" if success else "failed"
    
    try:
        log_email(phone=phone, subject=subject, body=body, status=status)
    except Exception as e:
        logger.error(f"Failed to log email in DB: {e}")
        
    if success:
        return f"Successfully sent the email to {to_email}."
    else:
        return f"Failed to send email to {to_email}. Please verify SMTP credentials."
