import os
from dotenv import load_dotenv

# Load .env file
load_dotenv()

# LLM Config
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")
COURSEWALLAH = os.getenv("COURSEWALLAH", "false").lower() == "true"
NUKKAD = os.getenv("NUKKAD", "false").lower() == "true"
COMPANY = os.getenv("COMPANY", "nukkad").lower()

if COMPANY == "bla_bli_blu":
    AGENT_MODE = "bla_bli_blu"
elif NUKKAD:
    AGENT_MODE = "portfolio"
else:
    AGENT_MODE = "coursewallah"


GEMINI_LIVE_VOICE = os.getenv("GEMINI_LIVE_VOICE", "Aoede")
AGENT_NAME = os.getenv("AGENT_NAME", "Kavya")

# Sarvam AI Config
SARVAM_API_KEY = os.getenv("SARVAM_API_KEY", "")
SARVAM_SPEAKER = os.getenv("SARVAM_SPEAKER", "shubh")

# Database Config
MONGO_URI = os.getenv("MONGO_URI", os.getenv("MONGODB_URI", "mongodb://localhost:27017/"))
MONGO_DB_NAME = os.getenv("MONGO_DB_NAME", "agentline")

# Email Config
SMTP_HOST = os.getenv("SMTP_HOST", "smtp.gmail.com")
SMTP_PORT = int(os.getenv("SMTP_PORT", "587"))
SMTP_USER = os.getenv("SMTP_USER", "")
SMTP_PASSWORD = os.getenv("SMTP_PASSWORD", "")
EMAIL_FROM = os.getenv("EMAIL_FROM", "")
RESEND_API_KEY = os.getenv("RESEND_API_KEY", "")
EMAIL_PROXY_URL = os.getenv("EMAIL_PROXY_URL", "https://email-service-five-orpin.vercel.app/api/send")

# Exotel Config
EXOTEL_API_KEY = os.getenv("EXOTEL_API_KEY", "")
EXOTEL_API_TOKEN = os.getenv("EXOTEL_API_TOKEN", "")
EXOTEL_SUBDOMAIN = os.getenv("EXOTEL_SUBDOMAIN", "")
EXOTEL_VIRTUAL_NUMBER = os.getenv("EXOTEL_VIRTUAL_NUMBER", "")

def validate_config():
    """Validates that crucial environment variables are present."""
    missing = []
    if not GEMINI_API_KEY:
        missing.append("GEMINI_API_KEY")
    if not SARVAM_API_KEY:
        missing.append("SARVAM_API_KEY")
    if missing:
        print(f"WARNING: Missing environment variables: {', '.join(missing)}")
        return False
    return True
