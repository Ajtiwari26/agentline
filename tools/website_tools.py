"""
Tools for the DeployMate website inbound voice agent (/ws/web).

- send_website_email: DeployMate-branded "AI deployment brief" email, sent over
  Gmail SMTP from ajay.deploymate@gmail.com.
- save_website_lead: stores the lead in the DeployMate site's MongoDB Atlas
  (db `deploymate`, collection `leads`) tagged "website inbound agent lead",
  matching the { kind, data, createdAt } shape the site's /api/leads uses.
"""

import os
import sys
import logging
import smtplib
from datetime import datetime, timezone
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

logger = logging.getLogger(__name__)

SITE_URL = "https://deploymates.vercel.app"

DEPLOYMATE_SMTP_USER = os.getenv("DEPLOYMATE_SMTP_USER", "ajay.deploymate@gmail.com")
DEPLOYMATE_SMTP_PASSWORD = os.getenv("DEPLOYMATE_SMTP_PASSWORD", "")
DEPLOYMATE_MONGO_URI = os.getenv("DEPLOYMATE_MONGO_URI", "")

_deploymate_client = None


def _get_deploymate_db():
    global _deploymate_client
    if not DEPLOYMATE_MONGO_URI:
        raise RuntimeError("DEPLOYMATE_MONGO_URI is not set")
    if _deploymate_client is None:
        from pymongo import MongoClient
        _deploymate_client = MongoClient(DEPLOYMATE_MONGO_URI, serverSelectionTimeoutMS=8000)
    return _deploymate_client["deploymate"]


# ──────────────────────────────────────────────────
# Lead storage
# ──────────────────────────────────────────────────
def save_website_lead(
    name: str = "",
    email: str = "",
    phone: str = "",
    company: str = "",
    requirement: str = "",
    interest_level: str = "warm",
    language: str = "hindi",
    session_id: str = "",
) -> str:
    """Insert or update the lead document for this call session."""
    interest_level = (interest_level or "warm").lower().strip()
    if interest_level not in ("hot", "warm", "cold"):
        interest_level = "warm"

    data = {
        "tag": "website inbound agent lead",
        "source": "website-inbound-voice-agent",
        "name": name or None,
        "email": email or None,
        "phone": phone or None,
        "company": company or None,
        "requirement": requirement or None,
        "interestLevel": interest_level,
        "language": language or None,
        "sessionId": session_id or None,
    }
    data = {k: v for k, v in data.items() if v is not None}

    db = _get_deploymate_db()
    if session_id:
        # One lead doc per call session — later tool calls enrich the same doc.
        db.leads.update_one(
            {"kind": "website inbound agent lead", "data.sessionId": session_id},
            {
                "$set": {**{f"data.{k}": v for k, v in data.items()}, "updatedAt": datetime.now(timezone.utc)},
                "$setOnInsert": {
                    "kind": "website inbound agent lead",
                    "createdAt": datetime.now(timezone.utc),
                    "userAgent": "agentline-web-voice",
                },
            },
            upsert=True,
        )
    else:
        db.leads.insert_one({
            "kind": "website inbound agent lead",
            "data": data,
            "createdAt": datetime.now(timezone.utc),
            "userAgent": "agentline-web-voice",
        })
    logger.info(f"Saved website inbound agent lead: {data}")
    return f"Lead saved successfully ({interest_level}): {name or 'unknown name'}"


def attach_transcript_to_lead(session_id: str, transcript: list, duration_seconds: int = 0) -> None:
    """Called at the end of a call: attach the transcript to the session's lead doc.

    If the agent never called save_lead during the call, this still creates a
    lead doc so no conversation is lost.
    """
    if not session_id:
        return
    db = _get_deploymate_db()
    db.leads.update_one(
        {"kind": "website inbound agent lead", "data.sessionId": session_id},
        {
            "$set": {
                "data.transcript": transcript,
                "data.durationSeconds": duration_seconds,
                "data.tag": "website inbound agent lead",
                "updatedAt": datetime.now(timezone.utc),
            },
            "$setOnInsert": {
                "kind": "website inbound agent lead",
                "createdAt": datetime.now(timezone.utc),
                "userAgent": "agentline-web-voice",
            },
        },
        upsert=True,
    )
    logger.info(f"Attached transcript ({len(transcript)} turns) to lead session {session_id}")


# ──────────────────────────────────────────────────
# DeployMate-branded email
# Design system: paper #FFFFFF / ink #0A0A0A / signal #E6391E,
# Space Grotesk display + Inter body + mono eyebrows, 1px hairlines,
# index-numbered rows, black takeover strips (see DeployMate design.md).
# Email-safe: tables + inline styles, no SVG/data URIs.
# ──────────────────────────────────────────────────
SERVICES = [
    ("01", "Voice AI Agents", "Inbound & outbound calling agents that answer, qualify and follow up 24×7 — in Hindi, English and 20+ languages. You just experienced one."),
    ("02", "WhatsApp AI CRM", "An AI agent on your official WhatsApp number that replies instantly at any hour, shares catalogues and books appointments."),
    ("03", "Websites, Apps & Chat Agents", "Complete design, development and hosting — with an AI chat agent trained on your business built in."),
    ("04", "Social & Workflow Automation", "Auto-scheduled posting, content pipelines, and automations that sync your leads, sheets and tools."),
]


def _build_email_html(name: str, personal_note: str, requirement: str) -> str:
    display_name = (name or "there").strip() or "there"
    today = datetime.now().strftime("%d %b %Y").upper()
    note_html = (personal_note or "").strip()
    requirement_row = ""
    if requirement:
        requirement_row = f"""
            <tr>
              <td style="padding:0 0 28px 0;">
                <table border="0" cellpadding="0" cellspacing="0" width="100%" style="border-left:3px solid #E6391E; background-color:#FAFAFA;">
                  <tr>
                    <td style="padding:16px 20px;">
                      <p style="font-family:'Fira Code',Menlo,Consolas,monospace; font-size:10px; letter-spacing:0.18em; text-transform:uppercase; color:#E6391E; margin:0 0 6px 0;">WHAT YOU ASKED FOR</p>
                      <p style="font-family:Inter,Helvetica,Arial,sans-serif; font-size:15px; line-height:1.6; color:#0A0A0A; margin:0;">{requirement}</p>
                    </td>
                  </tr>
                </table>
              </td>
            </tr>"""

    service_rows = ""
    for idx, title, desc in SERVICES:
        service_rows += f"""
              <tr>
                <td style="border-top:1px solid #0A0A0A; padding:18px 0 18px 0;">
                  <table border="0" cellpadding="0" cellspacing="0" width="100%">
                    <tr>
                      <td width="44" valign="top" style="font-family:'Fira Code',Menlo,Consolas,monospace; font-size:12px; color:#E6391E; padding-top:3px;">{idx}</td>
                      <td valign="top">
                        <p style="font-family:'Space Grotesk',Inter,Helvetica,Arial,sans-serif; font-size:17px; font-weight:600; color:#0A0A0A; margin:0 0 4px 0; letter-spacing:-0.01em;">{title}</p>
                        <p style="font-family:Inter,Helvetica,Arial,sans-serif; font-size:13.5px; line-height:1.6; color:#555555; margin:0;">{desc}</p>
                      </td>
                    </tr>
                  </table>
                </td>
              </tr>"""

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8"/>
<meta content="width=device-width, initial-scale=1.0" name="viewport"/>
<title>Your AI deployment brief — DeployMate</title>
<link href="https://fonts.googleapis.com" rel="preconnect"/>
<link crossorigin="" href="https://fonts.gstatic.com" rel="preconnect"/>
<link href="https://fonts.googleapis.com/css2?family=Space+Grotesk:wght@400;500;600;700&family=Inter:wght@400;500;600&family=Fira+Code:wght@400;500&display=swap" rel="stylesheet"/>
</head>
<body style="margin:0; padding:0; background-color:#F2F2F0; -webkit-font-smoothing:antialiased;">
<table border="0" cellpadding="0" cellspacing="0" width="100%" style="background-color:#F2F2F0; padding:36px 12px;">
  <tr>
    <td align="center">
      <table border="0" cellpadding="0" cellspacing="0" width="100%" style="max-width:620px; background-color:#FFFFFF; border:1px solid #0A0A0A;">

        <!-- Header: ink takeover -->
        <tr>
          <td style="background-color:#0A0A0A; padding:22px 28px;">
            <table border="0" cellpadding="0" cellspacing="0" width="100%">
              <tr>
                <td style="font-family:'Space Grotesk',Inter,Helvetica,Arial,sans-serif; font-size:20px; font-weight:700; letter-spacing:0.02em; color:#FFFFFF;">
                  DEPLOYMATE<span style="color:#E6391E;">&#174;</span>
                </td>
                <td align="right" style="font-family:'Fira Code',Menlo,Consolas,monospace; font-size:10px; letter-spacing:0.18em; color:#888888;">AI&nbsp;DEPLOYMENT&nbsp;STUDIO</td>
              </tr>
            </table>
          </td>
        </tr>
        <!-- Signal bar (progress-bar motif) -->
        <tr><td style="background-color:#E6391E; height:4px; line-height:4px; font-size:0;">&nbsp;</td></tr>

        <!-- Body -->
        <tr>
          <td style="padding:36px 28px 8px 28px;">
            <table border="0" cellpadding="0" cellspacing="0" width="100%">
              <tr>
                <td style="padding:0 0 14px 0;">
                  <p style="font-family:'Fira Code',Menlo,Consolas,monospace; font-size:10px; letter-spacing:0.2em; text-transform:uppercase; color:#E6391E; margin:0;">YOUR AI DEPLOYMENT BRIEF &nbsp;&#8226;&nbsp; {today}</p>
                </td>
              </tr>
              <tr>
                <td style="padding:0 0 18px 0;">
                  <h1 style="font-family:'Space Grotesk',Inter,Helvetica,Arial,sans-serif; font-size:30px; line-height:1.15; font-weight:600; letter-spacing:-0.02em; color:#0A0A0A; margin:0;">
                    Hi {display_name} &mdash;<br/>here&rsquo;s everything we talked about.
                  </h1>
                </td>
              </tr>
              <tr>
                <td style="padding:0 0 26px 0;">
                  <p style="font-family:Inter,Helvetica,Arial,sans-serif; font-size:15px; line-height:1.7; color:#333333; margin:0;">{note_html}</p>
                </td>
              </tr>
              {requirement_row}
            </table>
          </td>
        </tr>

        <!-- Services index -->
        <tr>
          <td style="padding:0 28px;">
            <table border="0" cellpadding="0" cellspacing="0" width="100%">
              <tr>
                <td style="padding:0 0 12px 0;">
                  <p style="font-family:'Fira Code',Menlo,Consolas,monospace; font-size:10px; letter-spacing:0.2em; text-transform:uppercase; color:#888888; margin:0;">WHAT WE BUILD (4)</p>
                </td>
              </tr>
              {service_rows}
              <tr><td style="border-top:1px solid #0A0A0A; font-size:0; line-height:0;">&nbsp;</td></tr>
            </table>
          </td>
        </tr>

        <!-- Stats strip: ink takeover -->
        <tr>
          <td style="padding:28px;">
            <table border="0" cellpadding="0" cellspacing="0" width="100%" style="background-color:#0A0A0A;">
              <tr>
                <td width="33%" align="center" style="padding:24px 8px;">
                  <p style="font-family:'Space Grotesk',Inter,Helvetica,Arial,sans-serif; font-size:26px; font-weight:700; color:#E6391E; margin:0 0 4px 0;">70%</p>
                  <p style="font-family:'Fira Code',Menlo,Consolas,monospace; font-size:9px; letter-spacing:0.16em; text-transform:uppercase; color:#BBBBBB; margin:0;">OPS COST SAVED</p>
                </td>
                <td width="34%" align="center" style="padding:24px 8px; border-left:1px solid #333333; border-right:1px solid #333333;">
                  <p style="font-family:'Space Grotesk',Inter,Helvetica,Arial,sans-serif; font-size:26px; font-weight:700; color:#FFFFFF; margin:0 0 4px 0;">24&#215;7</p>
                  <p style="font-family:'Fira Code',Menlo,Consolas,monospace; font-size:9px; letter-spacing:0.16em; text-transform:uppercase; color:#BBBBBB; margin:0;">AI EMPLOYEES</p>
                </td>
                <td width="33%" align="center" style="padding:24px 8px;">
                  <p style="font-family:'Space Grotesk',Inter,Helvetica,Arial,sans-serif; font-size:26px; font-weight:700; color:#E6391E; margin:0 0 4px 0;">&lt;1s</p>
                  <p style="font-family:'Fira Code',Menlo,Consolas,monospace; font-size:9px; letter-spacing:0.16em; text-transform:uppercase; color:#BBBBBB; margin:0;">LEAD RESPONSE</p>
                </td>
              </tr>
            </table>
          </td>
        </tr>

        <!-- Next steps -->
        <tr>
          <td style="padding:0 28px 8px 28px;">
            <p style="font-family:'Fira Code',Menlo,Consolas,monospace; font-size:10px; letter-spacing:0.2em; text-transform:uppercase; color:#888888; margin:0 0 12px 0;">NEXT STEPS</p>
            <p style="font-family:Inter,Helvetica,Arial,sans-serif; font-size:14px; line-height:1.8; color:#333333; margin:0 0 6px 0;"><span style="color:#E6391E; font-weight:600;">1.</span>&nbsp; Our founder personally reviews every call from the website line.</p>
            <p style="font-family:Inter,Helvetica,Arial,sans-serif; font-size:14px; line-height:1.8; color:#333333; margin:0 0 6px 0;"><span style="color:#E6391E; font-weight:600;">2.</span>&nbsp; We&rsquo;ll reach out within 24 hours with a plan tailored to your business.</p>
            <p style="font-family:Inter,Helvetica,Arial,sans-serif; font-size:14px; line-height:1.8; color:#333333; margin:0;"><span style="color:#E6391E; font-weight:600;">3.</span>&nbsp; Prefer sooner? Book a live demo below or just reply to this email.</p>
          </td>
        </tr>

        <!-- CTA -->
        <tr>
          <td align="center" style="padding:30px 28px 40px 28px;">
            <table border="0" cellpadding="0" cellspacing="0">
              <tr>
                <td align="center" style="background-color:#E6391E; border-radius:999px;">
                  <a href="{SITE_URL}" style="display:inline-block; padding:14px 34px; font-family:'Space Grotesk',Inter,Helvetica,Arial,sans-serif; font-size:14px; font-weight:600; color:#FFFFFF; text-decoration:none; letter-spacing:0.01em;">Book a live demo &#8594;</a>
                </td>
              </tr>
            </table>
            <p style="font-family:Inter,Helvetica,Arial,sans-serif; font-size:12px; color:#888888; margin:14px 0 0 0;">or simply reply to this email &mdash; a human reads every reply.</p>
          </td>
        </tr>

        <!-- Footer: ink takeover -->
        <tr>
          <td style="background-color:#0A0A0A; padding:30px 28px;">
            <table border="0" cellpadding="0" cellspacing="0" width="100%">
              <tr>
                <td style="font-family:'Space Grotesk',Inter,Helvetica,Arial,sans-serif; font-size:16px; font-weight:700; color:#FFFFFF; padding-bottom:8px;">
                  DEPLOYMATE<span style="color:#E6391E;">&#174;</span>
                </td>
              </tr>
              <tr>
                <td style="font-family:Inter,Helvetica,Arial,sans-serif; font-size:12px; line-height:1.7; color:#999999;">
                  AI voice agents &#8226; WhatsApp CRM &#8226; Websites &amp; apps &#8226; Automation<br/>
                  Bhopal, India &nbsp;&#8226;&nbsp; <a href="mailto:{DEPLOYMATE_SMTP_USER}" style="color:#FFFFFF; text-decoration:underline;">{DEPLOYMATE_SMTP_USER}</a> &nbsp;&#8226;&nbsp; <a href="{SITE_URL}" style="color:#FFFFFF; text-decoration:underline;">deploymates.vercel.app</a>
                </td>
              </tr>
              <tr>
                <td style="font-family:'Fira Code',Menlo,Consolas,monospace; font-size:9px; letter-spacing:0.16em; color:#555555; padding-top:16px;">
                  &#169; 2026 DEPLOYMATE &nbsp;&#8226;&nbsp; SENT BY OUR INBOUND VOICE AGENT, KAVYA
                </td>
              </tr>
            </table>
          </td>
        </tr>

      </table>
    </td>
  </tr>
</table>
</body>
</html>"""


def send_website_email(
    to_email: str,
    name: str = "",
    personal_note: str = "",
    requirement: str = "",
    language: str = "hindi",
) -> str:
    """Send the DeployMate deployment-brief email via Gmail SMTP."""
    if not to_email or "@" not in to_email:
        return f"Invalid email address: '{to_email}'. Ask the user to repeat it."
    if not DEPLOYMATE_SMTP_PASSWORD:
        return "Email service is not configured (missing SMTP password). Tell the user the team will email them manually."

    if not personal_note:
        personal_note = (
            "Thank you for calling DeployMate! It was great talking to you. "
            "Here is a quick summary of what we can build for your business."
        )

    subject = f"{name.strip()}, your AI deployment brief — DeployMate" if name.strip() else "Your AI deployment brief — DeployMate"
    html = _build_email_html(name, personal_note, requirement)

    # Render's free tier blocks outbound SMTP ports, so production sends go
    # through the Vercel SMTP proxy; direct SMTP remains as a fallback for
    # local runs or if the proxy is down.
    if _send_via_proxy(to_email, subject, html):
        logger.info(f"Website brief email sent to {to_email} via proxy")
        return f"Email sent successfully to {to_email}."

    _send_via_smtp(to_email, subject, html, name, personal_note)
    logger.info(f"Website brief email sent to {to_email} via direct SMTP")
    return f"Email sent successfully to {to_email}."


def _send_via_proxy(to_email: str, subject: str, html: str) -> bool:
    import requests
    proxy_url = os.getenv("EMAIL_PROXY_URL", "https://email-service-five-orpin.vercel.app/api/send")
    try:
        response = requests.post(
            proxy_url,
            json={
                "to_email": to_email,
                "subject": subject,
                "body": html,
                "smtp_user": DEPLOYMATE_SMTP_USER,
                "smtp_password": DEPLOYMATE_SMTP_PASSWORD,
                "email_from": f"Kavya from DeployMate <{DEPLOYMATE_SMTP_USER}>",
                "content_type": "html",
            },
            timeout=20,
        )
        if response.status_code == 200 and response.json().get("success"):
            return True
        logger.error(f"Email proxy returned failure ({response.status_code}): {response.text[:200]}")
    except Exception as e:
        logger.error(f"Email proxy unreachable: {e}")
    return False


def _send_via_smtp(to_email: str, subject: str, html: str, name: str, personal_note: str) -> None:
    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"] = f"Kavya from DeployMate <{DEPLOYMATE_SMTP_USER}>"
    msg["To"] = to_email
    msg["Reply-To"] = DEPLOYMATE_SMTP_USER

    plain = (
        f"Hi {name or 'there'},\n\n{personal_note}\n\n"
        "What we build:\n"
        + "\n".join(f"{i}. {t} — {d}" for i, t, d in SERVICES)
        + f"\n\nBook a live demo: {SITE_URL}\n\n— Kavya, DeployMate's inbound voice agent"
    )
    msg.attach(MIMEText(plain, "plain", "utf-8"))
    msg.attach(MIMEText(html, "html", "utf-8"))

    with smtplib.SMTP("smtp.gmail.com", 587, timeout=20) as server:
        server.starttls()
        server.login(DEPLOYMATE_SMTP_USER, DEPLOYMATE_SMTP_PASSWORD)
        server.sendmail(DEPLOYMATE_SMTP_USER, [to_email], msg.as_string())
