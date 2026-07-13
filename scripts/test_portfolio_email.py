"""
Test script: Send a personalized designer HTML portfolio email to tiwariajay033@gmail.com
Simulates a FIITJEE Bhopal coaching institute lead.
"""
import os
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dotenv import load_dotenv
load_dotenv()

import config
from tools.email_tool import _generate_personalized_pitch, _build_portfolio_html, send_email_via_smtp

# Simulate generic lead data
fake_lead = {
    "name": "Acme Corp",
    "phone": "+919399250600",
    "notes": "A logistics and supply chain company based in Bhopal. They are looking to automate customer service inquiries on WhatsApp, deploy an outbound AI calling agent to follow up on order status, and build a custom web portal for customer dashboards.",
    "interest_level": "hot"
}

print("🔧 Generating personalized pitch via Gemini...")
personalization = _generate_personalized_pitch(fake_lead)
print(f"✅ Pitch generated ({len(personalization['pitch'])} chars)")
print(f"✅ Callout generated ({len(personalization['callout'])} chars)")

print("\n🎨 Building HTML email template...")
html_body = _build_portfolio_html(
    lead_name="FIITJEE Bhopal",
    pitch_text=personalization["pitch"],
    callout_text=personalization["callout"]
)
print(f"✅ HTML template built ({len(html_body)} chars)")

# Save HTML locally for preview
preview_path = os.path.join(os.path.dirname(__file__), "email_preview.html")
with open(preview_path, "w") as f:
    f.write(html_body)
print(f"📄 Preview saved: {preview_path}")

# Send the email
print(f"\n📧 Sending email to tiwariajay033@gmail.com...")
subject = "AI Automation Opportunity for FIITJEE Bhopal ⚡"
success = send_email_via_smtp(
    to_email="tiwariajay033@gmail.com",
    subject=subject,
    body=html_body,
    content_type="html"
)

if success:
    print("✅ Email sent successfully! Check your Gmail inbox.")
else:
    print("❌ Email sending failed. Check SMTP credentials.")
