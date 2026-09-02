import os
from dotenv import load_dotenv

# Load .env file
load_dotenv()

# LLM Config
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")
COMPANY = os.getenv("COMPANY", "deploymate").lower()
GEMINI_LIVE_VOICE = os.getenv("GEMINI_LIVE_VOICE", "Aoede")
AGENT_NAME = os.getenv("AGENT_NAME", "Kavya")
AGENTLINE_MODEL = os.getenv("AGENTLINE_MODEL", "gemini-3.1-flash-live-preview")
GEMINI_LIVE_MODEL = os.getenv("GEMINI_LIVE_MODEL", "gemini-3.1-flash-live-preview")


# Map COMPANY directly to AGENT_MODE
if COMPANY == "bla_bli_blu":
    AGENT_MODE = "bla_bli_blu"
elif COMPANY == "coursewallah":
    AGENT_MODE = "coursewallah"
else:
    AGENT_MODE = "portfolio"  # Default to portfolio mode (DeployMate)


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

# Plivo Telephony Config
PLIVO_AUTH_ID = os.getenv("PLIVO_AUTH_ID", "")
PLIVO_AUTH_TOKEN = os.getenv("PLIVO_AUTH_TOKEN", "")
PLIVO_PHONE_NUMBER = os.getenv("PLIVO_PHONE_NUMBER", "")


def validate_config():
    """Validates that crucial environment variables are present."""
    missing = []
    if not GEMINI_API_KEY:
        missing.append("GEMINI_API_KEY")
    if not PLIVO_AUTH_ID or not PLIVO_AUTH_TOKEN:
        missing.append("PLIVO_AUTH_ID / PLIVO_AUTH_TOKEN")
    if missing:
        print(f"WARNING: Missing environment variables: {', '.join(missing)}")
        return False
    return True


def get_gemini_client():
    """Initializes and returns a Google GenAI Client using the direct Gemini API Key.

    Returns:
        tuple: (client, is_vertex)
    """
    from google import genai

    # Explicitly unset any GCP/Vertex AI credentials that would override the API key.
    # The google-genai SDK auto-detects these and switches to Vertex AI mode,
    # which breaks Live API calls if the GCP project doesn't have the model enabled.
    for env_var in [
        "GOOGLE_APPLICATION_CREDENTIALS",
        "GCP_SERVICE_ACCOUNT_JSON",
        "GCP_PROJECT",
        "GCP_LOCATION",
        "GOOGLE_CLOUD_PROJECT",
        "GOOGLE_CLOUD_LOCATION",
    ]:
        os.environ.pop(env_var, None)

    client = genai.Client(api_key=GEMINI_API_KEY)
    return client, False
