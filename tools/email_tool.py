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
def _build_portfolio_html(lead_name: str, pitch_text: str, callout_text: str) -> str:
    greeting = f"Hi <b>{lead_name}</b>," if lead_name else "Hi there,"
    logo_url = f"{EMAIL_ASSETS_URL}/logo.png"
    ai_phone_url = f"{EMAIL_ASSETS_URL}/ai-phone.png"
    founder_url = f"{EMAIL_ASSETS_URL}/founder.jpg"

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Nukkad Tech Solutions</title>
</head>
<body style="margin:0; padding:0; background-color:#f3f4f6; font-family:'Segoe UI',Roboto,'Helvetica Neue',Arial,sans-serif; -webkit-font-smoothing:antialiased;">

<table width="100%" cellpadding="0" cellspacing="0" border="0" style="background-color:#f3f4f6; padding:20px 0;">
<tr><td align="center">
<table width="620" cellpadding="0" cellspacing="0" border="0" style="max-width:620px; width:100%; background-color:#ffffff; border-radius:16px; overflow:hidden; box-shadow:0 4px 25px rgba(0,0,0,0.06);">

  <!-- ═══════════════════════════════════════════════
       HEADER: Logo
       ═══════════════════════════════════════════════ -->
  <tr><td style="padding:25px 30px 0 30px; background-color:#ffffff;">
    <img src="{logo_url}" width="220" height="auto" alt="Nukkad Tech Solutions" style="display:block; max-width:220px; height:auto;" />
  </td></tr>

  <!-- ═══════════════════════════════════════════════
       HERO: Greeting + AI Phone Image
       ═══════════════════════════════════════════════ -->
  <tr><td style="padding:20px 30px; background-color:#ffffff;">
    <table width="100%" cellpadding="0" cellspacing="0" border="0">
    <tr>
      <td width="55%" valign="top" style="padding-right:15px;">
        <p style="margin:0 0 4px 0; font-size:12px; color:#DC2626; font-weight:700; letter-spacing:0.5px;">⚡ AI-Powered Automation &bull; Custom Development &bull; Digital Growth</p>
        <p style="font-size:20px; font-weight:800; color:#111827; margin:12px 0 14px 0; line-height:1.3;">{greeting}</p>
        <p style="font-size:14px; line-height:1.7; color:#374151; margin:0 0 16px 0;">{pitch_text}</p>
      </td>
      <td width="45%" valign="middle" align="center">
        <img src="{ai_phone_url}" width="240" height="auto" alt="AI Automation" style="display:block; max-width:240px; height:auto;" />
      </td>
    </tr>
    </table>

    <!-- Callout Box -->
    <table width="100%" cellpadding="0" cellspacing="0" border="0" style="margin-top:5px;">
    <tr><td style="border-left:4px solid #DC2626; background-color:#FEF2F2; padding:14px 16px; border-radius:0 6px 6px 0;">
      <p style="margin:0; font-size:13.5px; line-height:1.6; color:#1F2937;">👉 {callout_text}</p>
    </td></tr>
    </table>
  </td></tr>

  <!-- ═══════════════════════════════════════════════
       PIPELINE: Your AI Opportunity
       ═══════════════════════════════════════════════ -->
  <tr><td style="padding:30px 30px; background-color:#fafafa; border-top:1px solid #f0f0f0; border-bottom:1px solid #f0f0f0;">
    <table width="100%" cellpadding="0" cellspacing="0" border="0">
    <tr><td style="padding-bottom:8px;">
      <h2 style="font-size:17px; font-weight:800; color:#111827; margin:0; text-align:center;">Your AI Opportunity for <span style="color:#DC2626;">{lead_name or "Your Business"}</span></h2>
      <p style="font-size:12px; color:#6B7280; margin:4px 0 20px 0; text-align:center;">Here's how we can transform your operations with AI Automation</p>
    </td></tr>
    <tr><td>
      <table width="100%" cellpadding="0" cellspacing="0" border="0">
      <tr>
        <!-- Step 1 -->
        <td width="18%" align="center" valign="top" style="padding:0 2px;">
          <div style="width:42px; height:42px; border-radius:50%; background-color:#DC2626; text-align:center; line-height:42px; font-size:20px; margin:0 auto 8px auto;">👥</div>
          <p style="margin:0; font-size:10px; font-weight:800; color:#111827; line-height:1.3;">Business Lead Follow-ups</p>
          <p style="margin:3px 0 0 0; font-size:9px; color:#6B7280; line-height:1.3;">Auto follow-up with business leads via calls &amp; messages</p>
        </td>
        <!-- Arrow -->
        <td width="4%" align="center" valign="top" style="padding-top:12px; font-size:14px; color:#D1D5DB;">➜</td>
        <!-- Step 2 -->
        <td width="18%" align="center" valign="top" style="padding:0 2px;">
          <div style="width:42px; height:42px; border-radius:50%; background-color:#DC2626; text-align:center; line-height:42px; font-size:20px; margin:0 auto 8px auto;">💬</div>
          <p style="margin:0; font-size:10px; font-weight:800; color:#111827; line-height:1.3;">WhatsApp &amp; Email Auto</p>
          <p style="margin:3px 0 0 0; font-size:9px; color:#6B7280; line-height:1.3;">Instantly send proposals and business details via WhatsApp/Email</p>
        </td>
        <!-- Arrow -->
        <td width="4%" align="center" valign="top" style="padding-top:12px; font-size:14px; color:#D1D5DB;">➜</td>
        <!-- Step 3 -->
        <td width="18%" align="center" valign="top" style="padding:0 2px;">
          <div style="width:42px; height:42px; border-radius:50%; background-color:#DC2626; text-align:center; line-height:42px; font-size:20px; margin:0 auto 8px auto;">📞</div>
          <p style="margin:0; font-size:10px; font-weight:800; color:#111827; line-height:1.3;">Voice AI Calling Agents</p>
          <p style="margin:3px 0 0 0; font-size:9px; color:#6B7280; line-height:1.3;">AI agents call leads &amp; book appointments</p>
        </td>
        <!-- Arrow -->
        <td width="4%" align="center" valign="top" style="padding-top:12px; font-size:14px; color:#D1D5DB;">➜</td>
        <!-- Step 4 -->
        <td width="18%" align="center" valign="top" style="padding:0 2px;">
          <div style="width:42px; height:42px; border-radius:50%; background-color:#DC2626; text-align:center; line-height:42px; font-size:20px; margin:0 auto 8px auto;">📅</div>
          <p style="margin:0; font-size:10px; font-weight:800; color:#111827; line-height:1.3;">Schedule Appointments</p>
          <p style="margin:3px 0 0 0; font-size:9px; color:#6B7280; line-height:1.3;">Book callback &amp; strategy sessions</p>
        </td>
        <!-- Arrow -->
        <td width="4%" align="center" valign="top" style="padding-top:12px; font-size:14px; color:#D1D5DB;">➜</td>
        <!-- Step 5 -->
        <td width="18%" align="center" valign="top" style="padding:0 2px;">
          <div style="width:42px; height:42px; border-radius:50%; background-color:#DC2626; text-align:center; line-height:42px; font-size:20px; margin:0 auto 8px auto;">📈</div>
          <p style="margin:0; font-size:10px; font-weight:800; color:#111827; line-height:1.3;">CRM &amp; Analytics</p>
          <p style="margin:3px 0 0 0; font-size:9px; color:#6B7280; line-height:1.3;">Track every lead &amp; conversion in real-time</p>
        </td>
      </tr>
      </table>
    </td></tr>
    </table>
  </td></tr>

  <!-- ═══════════════════════════════════════════════
       SERVICES: What We Can Build For You
       ═══════════════════════════════════════════════ -->
  <tr><td style="padding:30px 30px; background-color:#ffffff;">
    <h2 style="font-size:16px; font-weight:800; color:#111827; margin:0 0 22px 0; text-align:center; letter-spacing:0.5px;">
      ── WHAT WE CAN BUILD FOR <span style="color:#DC2626;">YOU</span> ──
    </h2>

    <!-- Row 1: 4 cards -->
    <table width="100%" cellpadding="0" cellspacing="0" border="0" style="margin-bottom:12px;">
    <tr>
      <td width="25%" valign="top" style="padding:0 4px;">
        <table width="100%" cellpadding="0" cellspacing="0" border="0" style="border:1px solid #E5E7EB; border-radius:10px; text-align:center;">
        <tr><td style="padding:16px 8px;">
          <div style="width:38px; height:38px; border-radius:50%; background-color:#FEF2F2; margin:0 auto 10px auto; text-align:center; line-height:38px; font-size:20px;">🎙️</div>
          <p style="margin:0 0 5px 0; font-size:11.5px; font-weight:800; color:#111827;">Voice AI Agents</p>
          <p style="margin:0; font-size:9.5px; line-height:1.4; color:#6B7280;">Autonomous inbound &amp; outbound call agents that handle sales, support, and follow-ups 24/7 — just like the one you spoke with!</p>
        </td></tr>
        </table>
      </td>
      <td width="25%" valign="top" style="padding:0 4px;">
        <table width="100%" cellpadding="0" cellspacing="0" border="0" style="border:1px solid #E5E7EB; border-radius:10px; text-align:center;">
        <tr><td style="padding:16px 8px;">
          <div style="width:38px; height:38px; border-radius:50%; background-color:#FEF2F2; margin:0 auto 10px auto; text-align:center; line-height:38px; font-size:20px;">💬</div>
          <p style="margin:0 0 5px 0; font-size:11.5px; font-weight:800; color:#111827;">WhatsApp CRM</p>
          <p style="margin:0; font-size:9.5px; line-height:1.4; color:#6B7280;">AI-powered WhatsApp bots that resolve inquiries, book meetings, and update your CRM — even at 2 AM.</p>
        </td></tr>
        </table>
      </td>
      <td width="25%" valign="top" style="padding:0 4px;">
        <table width="100%" cellpadding="0" cellspacing="0" border="0" style="border:1px solid #E5E7EB; border-radius:10px; text-align:center;">
        <tr><td style="padding:16px 8px;">
          <div style="width:38px; height:38px; border-radius:50%; background-color:#FEF2F2; margin:0 auto 10px auto; text-align:center; line-height:38px; font-size:20px;">🤖</div>
          <p style="margin:0 0 5px 0; font-size:11.5px; font-weight:800; color:#111827;">Chat Agents</p>
          <p style="margin:0; font-size:9.5px; line-height:1.4; color:#6B7280;">Intelligent AI chatbots for your website, Instagram, Messenger &amp; more. Engage, qualify &amp; convert automatically.</p>
        </td></tr>
        </table>
      </td>
      <td width="25%" valign="top" style="padding:0 4px;">
        <table width="100%" cellpadding="0" cellspacing="0" border="0" style="border:1px solid #E5E7EB; border-radius:10px; text-align:center;">
        <tr><td style="padding:16px 8px;">
          <div style="width:38px; height:38px; border-radius:50%; background-color:#FEF2F2; margin:0 auto 10px auto; text-align:center; line-height:38px; font-size:20px;">🗣️</div>
          <p style="margin:0 0 5px 0; font-size:11.5px; font-weight:800; color:#111827;">Voice Agents</p>
          <p style="margin:0; font-size:9.5px; line-height:1.4; color:#6B7280;">Human-like AI voice agents for customer support, sales, surveys, reminders &amp; more — 100% automated.</p>
        </td></tr>
        </table>
      </td>
    </tr>
    </table>

    <!-- Row 2: 5 cards -->
    <table width="100%" cellpadding="0" cellspacing="0" border="0">
    <tr>
      <td width="20%" valign="top" style="padding:0 3px;">
        <table width="100%" cellpadding="0" cellspacing="0" border="0" style="border:1px solid #E5E7EB; border-radius:10px; text-align:center;">
        <tr><td style="padding:12px 5px;">
          <div style="width:32px; height:32px; border-radius:50%; background-color:#FEF2F2; margin:0 auto 8px auto; text-align:center; line-height:32px; font-size:16px;">📱</div>
          <p style="margin:0 0 4px 0; font-size:10px; font-weight:800; color:#111827;">WhatsApp Auto</p>
          <p style="margin:0; font-size:8.5px; line-height:1.3; color:#6B7280;">Auto-replies, broadcasts, templates, reminders, payments &amp; CRM — all on autopilot.</p>
        </td></tr>
        </table>
      </td>
      <td width="20%" valign="top" style="padding:0 3px;">
        <table width="100%" cellpadding="0" cellspacing="0" border="0" style="border:1px solid #E5E7EB; border-radius:10px; text-align:center;">
        <tr><td style="padding:12px 5px;">
          <div style="width:32px; height:32px; border-radius:50%; background-color:#FEF2F2; margin:0 auto 8px auto; text-align:center; line-height:32px; font-size:16px;">👥</div>
          <p style="margin:0 0 4px 0; font-size:10px; font-weight:800; color:#111827;">AI Sales Team</p>
          <p style="margin:0; font-size:8.5px; line-height:1.3; color:#6B7280;">AI SDRs that find leads, qualify, follow up &amp; book meetings for your sales team.</p>
        </td></tr>
        </table>
      </td>
      <td width="20%" valign="top" style="padding:0 3px;">
        <table width="100%" cellpadding="0" cellspacing="0" border="0" style="border:1px solid #E5E7EB; border-radius:10px; text-align:center;">
        <tr><td style="padding:12px 5px;">
          <div style="width:32px; height:32px; border-radius:50%; background-color:#FEF2F2; margin:0 auto 8px auto; text-align:center; line-height:32px; font-size:16px;">🏢</div>
          <p style="margin:0 0 4px 0; font-size:10px; font-weight:800; color:#111827;">AI Receptionist</p>
          <p style="margin:0; font-size:8.5px; line-height:1.3; color:#6B7280;">Digital receptionist that handles incoming calls, answers FAQs, routes calls &amp; books appointments.</p>
        </td></tr>
        </table>
      </td>
      <td width="20%" valign="top" style="padding:0 3px;">
        <table width="100%" cellpadding="0" cellspacing="0" border="0" style="border:1px solid #E5E7EB; border-radius:10px; text-align:center;">
        <tr><td style="padding:12px 5px;">
          <div style="width:32px; height:32px; border-radius:50%; background-color:#FEF2F2; margin:0 auto 8px auto; text-align:center; line-height:32px; font-size:16px;">⚙️</div>
          <p style="margin:0 0 4px 0; font-size:10px; font-weight:800; color:#111827;">Workflow Auto</p>
          <p style="margin:0; font-size:8.5px; line-height:1.3; color:#6B7280;">Automate your business workflows, approvals, notifications, CRM, HR, finance &amp; more with AI.</p>
        </td></tr>
        </table>
      </td>
      <td width="20%" valign="top" style="padding:0 3px;">
        <table width="100%" cellpadding="0" cellspacing="0" border="0" style="border:1px solid #E5E7EB; border-radius:10px; text-align:center;">
        <tr><td style="padding:12px 5px;">
          <div style="width:32px; height:32px; border-radius:50%; background-color:#FEF2F2; margin:0 auto 8px auto; text-align:center; line-height:32px; font-size:16px;">💻</div>
          <p style="margin:0 0 4px 0; font-size:10px; font-weight:800; color:#111827;">Custom Dev</p>
          <p style="margin:0; font-size:8.5px; line-height:1.3; color:#6B7280;">Web apps, mobile apps, dashboards &amp; APIs — custom-built for your business at a fraction of in-house cost.</p>
        </td></tr>
        </table>
      </td>
    </tr>
    </table>
  </td></tr>

  <!-- ═══════════════════════════════════════════════
       METRICS: Why Businesses Choose Us
       ═══════════════════════════════════════════════ -->
  <tr><td style="padding:30px 25px; background-color:#111827;">
    <h2 style="font-size:14px; font-weight:800; text-align:center; color:#ffffff; margin:0 0 22px 0; letter-spacing:0.8px; text-transform:uppercase;">
      WHY BUSINESSES CHOOSE <span style="color:#E11D48;">NUKKAD TECH SOLUTIONS</span>
    </h2>
    <table width="100%" cellpadding="0" cellspacing="0" border="0">
    <tr>
      <td width="16.6%" align="center" valign="top" style="padding:0 3px;">
        <div style="width:40px; height:40px; border-radius:50%; border:2px solid #E11D48; margin:0 auto 8px auto; text-align:center; line-height:40px; font-size:18px;">💰</div>
        <p style="margin:0 0 3px 0; font-size:10px; font-weight:800; color:#ffffff;">Save up to 70%</p>
        <p style="margin:0; font-size:8px; color:#9CA3AF; line-height:1.3;">operational costs</p>
      </td>
      <td width="16.6%" align="center" valign="top" style="padding:0 3px;">
        <div style="width:40px; height:40px; border-radius:50%; border:2px solid #E11D48; margin:0 auto 8px auto; text-align:center; line-height:40px; font-size:18px;">🕐</div>
        <p style="margin:0 0 3px 0; font-size:10px; font-weight:800; color:#ffffff;">24x7 AI</p>
        <p style="margin:0; font-size:8px; color:#9CA3AF; line-height:1.3;">employees working non-stop</p>
      </td>
      <td width="16.6%" align="center" valign="top" style="padding:0 3px;">
        <div style="width:40px; height:40px; border-radius:50%; border:2px solid #E11D48; margin:0 auto 8px auto; text-align:center; line-height:40px; font-size:18px;">⚡</div>
        <p style="margin:0 0 3px 0; font-size:10px; font-weight:800; color:#ffffff;">Instant Response</p>
        <p style="margin:0; font-size:8px; color:#9CA3AF; line-height:1.3;">to every lead &amp; customer</p>
      </td>
      <td width="16.6%" align="center" valign="top" style="padding:0 3px;">
        <div style="width:40px; height:40px; border-radius:50%; border:2px solid #E11D48; margin:0 auto 8px auto; text-align:center; line-height:40px; font-size:18px;">📊</div>
        <p style="margin:0 0 3px 0; font-size:10px; font-weight:800; color:#ffffff;">Higher Conversion</p>
        <p style="margin:0; font-size:8px; color:#9CA3AF; line-height:1.3;">with AI-powered engagement</p>
      </td>
      <td width="16.6%" align="center" valign="top" style="padding:0 3px;">
        <div style="width:40px; height:40px; border-radius:50%; border:2px solid #E11D48; margin:0 auto 8px auto; text-align:center; line-height:40px; font-size:18px;">🤝</div>
        <p style="margin:0 0 3px 0; font-size:10px; font-weight:800; color:#ffffff;">Human Handoff</p>
        <p style="margin:0; font-size:8px; color:#9CA3AF; line-height:1.3;">when needed, seamlessly</p>
      </td>
      <td width="16.6%" align="center" valign="top" style="padding:0 3px;">
        <div style="width:40px; height:40px; border-radius:50%; border:2px solid #E11D48; margin:0 auto 8px auto; text-align:center; line-height:40px; font-size:18px;">📈</div>
        <p style="margin:0 0 3px 0; font-size:10px; font-weight:800; color:#ffffff;">Real-time Analytics</p>
        <p style="margin:0; font-size:8px; color:#9CA3AF; line-height:1.3;">and performance tracking</p>
      </td>
    </tr>
    </table>
  </td></tr>

  <!-- ═══════════════════════════════════════════════
       CTA BANNER
       ═══════════════════════════════════════════════ -->
  <tr><td style="padding:35px 30px; background-color:#DC2626; text-align:center;">
    <div style="font-size:28px; margin-bottom:12px;">📅</div>
    <h3 style="margin:0 0 8px 0; font-size:22px; font-weight:900; color:#ffffff;">Ready to Build Your AI Workforce?</h3>
    <p style="margin:0 0 22px 0; font-size:14px; color:rgba(255,255,255,0.9); line-height:1.5;">
      Let's discuss how we can automate &amp; grow <b>{lead_name or "your business"}</b> together.
    </p>
    <a href="mailto:tiwariajay033@gmail.com?subject=Demo%20Request%20-%20Nukkad%20Tech%20Solutions"
       style="display:inline-block; background-color:#ffffff; color:#DC2626; text-decoration:none; font-size:13px; font-weight:900; padding:14px 36px; border-radius:8px; letter-spacing:0.8px; text-transform:uppercase;">
      SCHEDULE A LIVE DEMO &nbsp;→
    </a>
  </td></tr>

  <!-- ═══════════════════════════════════════════════
       FOOTER: Signature
       ═══════════════════════════════════════════════ -->
  <tr><td style="padding:22px 30px; background-color:#ffffff; border-top:1px solid #E5E7EB;">
    <table width="100%" cellpadding="0" cellspacing="0" border="0">
    <tr>
      <!-- Founder photo + name -->
      <td width="40%" valign="middle">
        <table cellpadding="0" cellspacing="0" border="0">
        <tr>
          <td valign="middle" style="padding-right:12px;">
            <img src="{founder_url}" width="50" height="50" alt="Ajay Tiwari" style="display:block; width:50px; height:50px; border-radius:50%; border:2px solid #E11D48; object-fit:cover;" />
          </td>
          <td valign="middle">
            <p style="margin:0 0 2px 0; font-size:14px; font-weight:800; color:#111827;">Ajay Tiwari</p>
            <p style="margin:0 0 1px 0; font-size:11px; font-weight:600; color:#E11D48;">Founder</p>
            <p style="margin:0; font-size:11px; font-weight:700; color:#4B5563;">Nukkad Tech Solutions</p>
          </td>
        </tr>
        </table>
      </td>
      <!-- Contact info -->
      <td width="35%" valign="middle">
        <p style="margin:0 0 3px 0; font-size:11px; color:#4B5563; font-weight:600;">✉️ ajay.nukkadtechsolutions@gmail.com</p>
        <p style="margin:0 0 3px 0; font-size:11px; color:#4B5563; font-weight:600;">📞 +91 93992 50600</p>
        <p style="margin:0; font-size:11px; color:#4B5563; font-weight:600;">🌐 nukkadtechsolutions.vercel.app</p>
      </td>
      <!-- Social -->
      <td width="25%" valign="middle" align="right">
        <p style="margin:0 0 6px 0; font-size:11px; font-weight:800; color:#111827;">Let's Connect</p>
        <a href="https://www.linkedin.com" style="display:inline-block; width:24px; height:24px; border-radius:50%; border:1px solid #D1D5DB; text-align:center; line-height:24px; text-decoration:none; font-size:10px; font-weight:bold; color:#4B5563; margin:0 2px;">in</a>
        <a href="https://www.instagram.com" style="display:inline-block; width:24px; height:24px; border-radius:50%; border:1px solid #D1D5DB; text-align:center; line-height:24px; text-decoration:none; font-size:10px; font-weight:bold; color:#4B5563; margin:0 2px;">ig</a>
        <a href="https://www.youtube.com" style="display:inline-block; width:24px; height:24px; border-radius:50%; border:1px solid #D1D5DB; text-align:center; line-height:24px; text-decoration:none; font-size:10px; font-weight:bold; color:#4B5563; margin:0 2px;">yt</a>
        <a href="https://wa.me/919399250600" style="display:inline-block; width:24px; height:24px; border-radius:50%; border:1px solid #D1D5DB; text-align:center; line-height:24px; text-decoration:none; font-size:10px; font-weight:bold; color:#4B5563; margin:0 2px;">wa</a>
      </td>
    </tr>
    </table>
  </td></tr>

  <!-- Copyright -->
  <tr><td style="background-color:#111827; padding:14px 30px; text-align:center; font-size:11px; color:#9CA3AF; font-weight:500;">
    &copy; 2025 <span style="color:#E11D48; font-weight:700;">Nukkad Tech Solutions</span>. All rights reserved.
  </td></tr>

</table>
</td></tr>
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
