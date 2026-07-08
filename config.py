import os
from dotenv import load_dotenv

# Load .env file
load_dotenv()

# LLM Config
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")

# Sarvam AI Config
SARVAM_API_KEY = os.getenv("SARVAM_API_KEY", "")

# Database Config
MONGO_URI = os.getenv("MONGO_URI", "mongodb://localhost:27017/")
MONGO_DB_NAME = os.getenv("MONGO_DB_NAME", "agentline")

# Email Config
SMTP_HOST = os.getenv("SMTP_HOST", "smtp.gmail.com")
SMTP_PORT = int(os.getenv("SMTP_PORT", "587"))
SMTP_USER = os.getenv("SMTP_USER", "")
SMTP_PASSWORD = os.getenv("SMTP_PASSWORD", "")
EMAIL_FROM = os.getenv("EMAIL_FROM", "")
RESEND_API_KEY = os.getenv("RESEND_API_KEY", "")

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
