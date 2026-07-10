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
🤖 Google Play Store: https://play.google.com/store/apps/details?id=co.barney.vcunre
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
🤖 Google Play Store: https://play.google.com/store/apps/details?id=co.barney.vcunre
🍏 Apple iOS App Store: Search for 'MyInstitute' app and enter Org Code: vcunre

Our manager will be in touch with you shortly to answer any payment or batch-timing questions.

Best regards,
Ajay
Mentor, CourseWallah
"""
    }
}

def send_email_via_smtp(to_email: str, subject: str, body: str) -> bool:
    """Sends email via standard SMTP."""
    if not config.SMTP_USER or not config.SMTP_PASSWORD:
        logger.error("SMTP credentials missing in configuration.")
        return False
        
    msg = MIMEMultipart()
    msg['From'] = config.EMAIL_FROM or config.SMTP_USER
    msg['To'] = to_email
    msg['Subject'] = subject
    
    msg.attach(MIMEText(body, 'plain'))
    
    try:
        server = smtplib.SMTP(config.SMTP_HOST, config.SMTP_PORT)
        server.starttls()
        server.login(config.SMTP_USER, config.SMTP_PASSWORD)
        server.sendmail(msg['From'], to_email, msg.as_string())
        server.quit()
        logger.info(f"Email successfully sent to {to_email} via SMTP.")
        return True
    except Exception as e:
        logger.error(f"SMTP email sending failed: {e}")
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
    payload = {
        "from": config.EMAIL_FROM or "CourseWallah <onboarding@resend.dev>",
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
    template = TEMPLATES.get(template_name, TEMPLATES["syllabus"])
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
