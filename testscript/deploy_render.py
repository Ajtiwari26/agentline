import os
import sys
import subprocess
import json
from dotenv import load_dotenv

load_dotenv()

def deploy_to_render():
    sa_file = "/Users/ajaytiwari/agentline_sa_key.json"
    sa_json = json.dumps(json.load(open(sa_file)))
    
    cmd = [
        "/opt/homebrew/bin/render", "services", "create",
        "--name", "agentline-backend",
        "--type", "web_service",
        "--repo", "https://github.com/Ajtiwari26/agentline.git",
        "--branch", "main",
        "--runtime", "python",
        "--build-command", "pip install -r requirements.txt",
        "--start-command", "uvicorn cloud.server:app --host 0.0.0.0 --port $PORT",
        "--health-check-path", "/health",
        "--env-var", "COMPANY=deploymate",
        "--env-var", "GEMINI_LIVE_VOICE=Aoede",
        "--env-var", "AGENT_NAME=Kavya",
        "--env-var", "SARVAM_SPEAKER=kavya",
        "--env-var", "GCP_PROJECT=igsl-67e70",
        "--env-var", "GCP_LOCATION=us-central1",
        "--env-var", f"GCP_SERVICE_ACCOUNT_JSON={sa_json}",
        "--env-var", f"GEMINI_API_KEY={os.getenv('GEMINI_API_KEY', '')}",
        "--env-var", f"EXOTEL_API_KEY={os.getenv('EXOTEL_API_KEY', '')}",
        "--env-var", f"EXOTEL_API_TOKEN={os.getenv('EXOTEL_API_TOKEN', '')}",
        "--env-var", f"EXOTEL_ACCOUNT_SID={os.getenv('EXOTEL_ACCOUNT_SID', '')}",
        "--env-var", f"EXOTEL_SUBDOMAIN={os.getenv('EXOTEL_SUBDOMAIN', '')}",
        "--env-var", f"EXOTEL_VIRTUAL_NUMBER={os.getenv('EXOTEL_VIRTUAL_NUMBER', '')}",
        "--env-var", f"SARVAM_API_KEY={os.getenv('SARVAM_API_KEY', '')}",
        "--env-var", f"MONGO_URI={os.getenv('MONGO_URI', '')}",
        "--env-var", "SMTP_USER=ajay.nukkadtechsolutions@gmail.com",
        "--env-var", "SMTP_PASSWORD=dmck zhjp xnsb rcji",
        "--env-var", "EMAIL_FROM=ajay.nukkadtechsolutions@gmail.com",
        "--output", "json"
    ]
    
    print("Executing Render CLI service creation...")
    result = subprocess.run(cmd, capture_output=True, text=True)
    print("STDOUT:", result.stdout)
    print("STDERR:", result.stderr)
    return result.returncode == 0

if __name__ == "__main__":
    deploy_to_render()
