import os
from dotenv import load_dotenv

# Load .env file
load_dotenv()

# LLM Config
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")
COMPANY = os.getenv("COMPANY", "nukkad").lower()
GEMINI_LIVE_VOICE = os.getenv("GEMINI_LIVE_VOICE", "Aoede")
AGENT_NAME = os.getenv("AGENT_NAME", "Kavya")

# Map COMPANY directly to AGENT_MODE
if COMPANY == "bla_bli_blu":
    AGENT_MODE = "bla_bli_blu"
elif COMPANY == "coursewallah":
    AGENT_MODE = "coursewallah"
else:
    AGENT_MODE = "portfolio"  # Default to portfolio mode (Nukkad)


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

def get_gemini_client():
    """Initializes and returns a Google GenAI Client.
    
    Tries Vertex AI if GCP credentials (via GOOGLE_APPLICATION_CREDENTIALS or
    GCP_SERVICE_ACCOUNT_JSON) are present. Otherwise, falls back to AI Studio key.
    
    Returns:
        tuple: (client, is_vertex)
    """
    from google import genai
    from google.oauth2 import service_account
    import json
    
    sa_json_str = os.getenv("GCP_SERVICE_ACCOUNT_JSON", "")
    sa_key_path = os.getenv("GOOGLE_APPLICATION_CREDENTIALS", "")
    project_id = os.getenv("GCP_PROJECT", "igsl-67e70")
    location = os.getenv("GCP_LOCATION", "us-central1")
    
    credentials = None
    is_vertex = False
    scopes = ["https://www.googleapis.com/auth/cloud-platform"]
    
    if sa_json_str:
        try:
            sa_info = json.loads(sa_json_str)
            credentials = service_account.Credentials.from_service_account_info(sa_info, scopes=scopes)
            is_vertex = True
        except Exception:
            pass
            
    if not is_vertex and sa_key_path and os.path.exists(sa_key_path):
        try:
            credentials = service_account.Credentials.from_service_account_file(sa_key_path, scopes=scopes)
            is_vertex = True
        except Exception:
            pass
            
    if is_vertex and credentials:
        client = genai.Client(
            vertexai=True,
            project=project_id,
            location=location,
            credentials=credentials
        )
        return client, True
    else:
        client = genai.Client(api_key=GEMINI_API_KEY)
        return client, False

