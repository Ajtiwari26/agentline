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
from db.database import log_email

logger = logging.getLogger(__name__)

# Templates for courses
TEMPLATES = {
    "syllabus": {
        "subject": "CourseWallah - AI Engineering Program & Details",
        "body": """Hello Future AI Engineer,

Thanks for talking to us today! As discussed, here are the course details:

1. Local LLMs Running & Applications: Learn to run open-source models (Llama-3, Qwen) offline on your hardware, build private agentic workflows, and skip API fees.
2. AI Models Training & Fine-Tuning: Learn custom fine-tuning and model training setups.

You can view our course catalog and syllabus details directly on our website:
👉 Course Catalog: https://www.coursewallah.com/courses

Or download our official mobile app to access all free content, previews, and live classes:
🤖 Google Play Store: https://play.google.com/store/apps/details?id=co.barney.npsvn
🍏 Apple iOS App Store: Search for 'MyInstitute' app and enter Org Code: vcunre

Let us know if you have any questions!

Best regards,
Ajay
Mentor, CourseWallah
"""
    },
    "pricing": {
        "subject": "CourseWallah - Course Pricing & Enrollment Portal",
        "body": """Hello Future AI Engineer,

Here are the pricing and enrollment options for our AI Engineering programs:

- Combined Program Fee: INR 14,999 (Inclusive of taxes)
- Easy Monthly EMI Options available (Starting at INR 1,500/month)
- 100% money-back guarantee if you complete the first 3 projects and don't find it valuable.

You can enroll directly through our student portal or courses page:
👉 Course Enrollment: https://www.coursewallah.com/courses
👉 Student Login Portal: https://students.coursewallah.com/login?orgCode=vcunre

If you prefer to study on mobile, you can download our app:
🤖 Google Play Store: https://play.google.com/store/apps/details?id=co.barney.npsvn
🍏 Apple iOS App Store: Search for 'MyInstitute' app and enter Org Code: vcunre

Our manager will be in touch with you shortly to answer any payment or batch-timing questions.

Best regards,
Ajay
Mentor, CourseWallah
"""
    },
    "portfolio": {
        "subject": "Nukkad Tech Solutions - AI & Tech Automation Portfolio",
        "body": """Hello,

Thanks for speaking with our AI voice assistant today! As discussed, here is the portfolio of Nukkad Tech Solutions:

Nukkad Tech Solutions provides complete end-to-end AI integration, custom software, app, and web development to help businesses minimize workload and automate operations.

Key Offerings & Projects:
1. AgentLine (Voice AI): Autonomous outbound & inbound call agents (just like the one that called you!) to handle sales, inquiries, and customer support.
2. AI WhatsApp CRM: 24/7 automated chat handlers that resolve inquiries, book meetings, and update databases even at 2 AM or 4 AM.
3. Social Media Automation: Automatically edit, optimize, and schedule YouTube Shorts & Instagram reels.
4. Custom Development: Web/app development and workflow automation tailored to your business needs without the overhead of hiring and training in-house teams.

If you are interested, we would love to schedule a live demo call with our founder, Ajay Tiwari.

Best regards,
Ajay Tiwari
Founder, Nukkad Tech Solutions
"""
    }
}

def send_email_via_smtp(to_email: str, subject: str, body: str) -> bool:
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
        "email_from": config.EMAIL_FROM or config.SMTP_USER
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

def send_email_via_resend(to_email: str, subject: str, body: str) -> bool:
    """Sends email via Resend API."""
    if not config.RESEND_API_KEY:
        logger.error("Resend API key missing in configuration.")
        return False
        
    url = "https://api.resend.com/emails"
    headers = {
        "Authorization": f"Bearer {config.RESEND_API_KEY}",
        "Content-Type": "application/json"
    }
    
    # Customize sender name based on AGENT_MODE
    mode = getattr(config, "AGENT_MODE", "portfolio")
    sender_name = "Nukkad Tech Solutions" if mode == "portfolio" else "CourseWallah"
    
    payload = {
        "from": config.EMAIL_FROM or f"{sender_name} <onboarding@resend.dev>",
        "to": [to_email],
        "subject": subject,
        "text": body
    }
    
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

def send_template_email(phone: str, to_email: str, template_name: str = "syllabus") -> str:
    """
    Sends a pre-defined email template to the user.
    Called by the AI Agent as a tool.
    """
    # Guard: Reject placeholder, empty, or obviously invalid email addresses immediately
    invalid_emails = ["lead@example.com", "example@example.com", "user@example.com", "test@example.com", ""]
    if not to_email or to_email.strip().lower() in invalid_emails or "@" not in to_email or "example" in to_email.lower():
        logger.warning(f"Email tool called with invalid/placeholder email: '{to_email}'. Returning early.")
        return "ERROR: No valid email address was provided. You must ask the user for their real email address during the call before sending an email. Do NOT retry this tool until you have a real email."
    
    # Determine the default template and override based on active mode
    mode = getattr(config, "AGENT_MODE", "portfolio")
    default_template = "portfolio" if mode == "portfolio" else "syllabus"
    
    # If standard greeting/agent requested 'syllabus' in portfolio mode, send portfolio
    if mode == "portfolio" and template_name == "syllabus":
        template_name = "portfolio"
        
    template = TEMPLATES.get(template_name, TEMPLATES[default_template])
    subject = template["subject"]
    body = template["body"]
    
    logger.info(f"Triggering email tool for {to_email} (Phone: {phone}) using template: {template_name}")
    
    success = False
    if config.RESEND_API_KEY:
        success = send_email_via_resend(to_email, subject, body)
    else:
        success = send_email_via_smtp(to_email, subject, body)
        
    status = "sent" if success else "failed"
    
    # Always log email in the DB
    try:
        log_email(phone=phone, subject=subject, body=body, status=status)
    except Exception as e:
        logger.error(f"Failed to log email in DB: {e}")
        
    if success:
        return f"Successfully sent the {template_name} email to {to_email}."
    else:
        return f"Failed to send email to {to_email}. Please verify SMTP credentials."
