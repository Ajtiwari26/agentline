import os
import sys
import json
import subprocess
import requests
import yaml
from dotenv import load_dotenv

load_dotenv()

SERVICE_ID = "srv-d6hjs5ea2pns738jlmkg"

def get_render_api_key():
    cli_cfg = os.path.expanduser("~/.render/cli.yaml")
    if os.path.exists(cli_cfg):
        with open(cli_cfg, "r") as f:
            data = yaml.safe_load(f)
            return data.get("api", {}).get("key", "")
    return os.getenv("RENDER_API_KEY", "")

RENDER_API_KEY = get_render_api_key()

def update_service_via_api():
    print(f"=== Updating Service Config via Render REST API for {SERVICE_ID} ===")
    url = f"https://api.render.com/v1/services/{SERVICE_ID}"
    headers = {
        "Authorization": f"Bearer {RENDER_API_KEY}",
        "Content-Type": "application/json"
    }
    
    payload = {
        "name": "agentline-backend",
        "repo": "https://github.com/Ajtiwari26/agentline",
        "branch": "main",
        "autoDeploy": "yes",
        "serviceDetails": {
            "env": "docker",
            "healthCheckPath": "/health"
        }
    }
    
    resp = requests.patch(url, headers=headers, json=payload)
    print(f"Service PATCH HTTP Status: {resp.status_code}")
    print("Response Body:", resp.text)
    return resp.status_code in [200, 201]

def set_env_vars():
    print(f"=== Setting Environment Variables for {SERVICE_ID} ===")
    sa_file = "/Users/ajaytiwari/agentline_sa_key.json"
    sa_json_str = json.dumps(json.load(open(sa_file)))
    
    env_vars = [
        {"key": "COMPANY", "value": "deploymate"},
        {"key": "GEMINI_LIVE_VOICE", "value": "Aoede"},
        {"key": "AGENT_NAME", "value": "Kavya"},
        {"key": "SARVAM_SPEAKER", "value": "kavya"},
        {"key": "GCP_PROJECT", "value": "igsl-67e70"},
        {"key": "GCP_LOCATION", "value": "us-central1"},
        {"key": "GCP_SERVICE_ACCOUNT_JSON", "value": sa_json_str},
        {"key": "GEMINI_API_KEY", "value": os.getenv("GEMINI_API_KEY", "")},
        {"key": "EXOTEL_API_KEY", "value": os.getenv("EXOTEL_API_KEY", "")},
        {"key": "EXOTEL_API_TOKEN", "value": os.getenv("EXOTEL_API_TOKEN", "")},
        {"key": "EXOTEL_ACCOUNT_SID", "value": os.getenv("EXOTEL_ACCOUNT_SID", "")},
        {"key": "EXOTEL_SUBDOMAIN", "value": os.getenv("EXOTEL_SUBDOMAIN", "")},
        {"key": "EXOTEL_VIRTUAL_NUMBER", "value": os.getenv("EXOTEL_VIRTUAL_NUMBER", "")},
        {"key": "SARVAM_API_KEY", "value": os.getenv("SARVAM_API_KEY", "")},
        {"key": "MONGO_URI", "value": os.getenv("MONGO_URI", "")},
        {"key": "SMTP_USER", "value": os.getenv("SMTP_USER", "")},
        {"key": "SMTP_PASSWORD", "value": os.getenv("SMTP_PASSWORD", "")},
        {"key": "EMAIL_FROM", "value": os.getenv("EMAIL_FROM", "")}
    ]
    
    url = f"https://api.render.com/v1/services/{SERVICE_ID}/env-vars"
    headers = {
        "Authorization": f"Bearer {RENDER_API_KEY}",
        "Content-Type": "application/json"
    }
    
    resp = requests.put(url, headers=headers, json=env_vars)
    print(f"Env Vars Update HTTP Status: {resp.status_code}")
    if resp.status_code in [200, 201]:
        print("Successfully updated environment variables!")
        return True
    else:
        print(f"Failed to update env vars: {resp.text}")
        return False

def trigger_deploy():
    print(f"=== Triggering Deployment for {SERVICE_ID} ===")
    url = f"https://api.render.com/v1/services/{SERVICE_ID}/deploys"
    headers = {
        "Authorization": f"Bearer {RENDER_API_KEY}",
        "Content-Type": "application/json"
    }
    resp = requests.post(url, headers=headers, json={})
    print(f"Deploy HTTP Status: {resp.status_code}")
    print("Deploy Response:", resp.text)
    return resp.status_code in [200, 201]

if __name__ == "__main__":
    if update_service_via_api():
        set_env_vars()
        trigger_deploy()
