import os
import sys
import json
import requests
import yaml
from dotenv import load_dotenv

load_dotenv()

def get_render_api_key():
    cli_cfg = os.path.expanduser("~/.render/cli.yaml")
    if os.path.exists(cli_cfg):
        with open(cli_cfg, "r") as f:
            data = yaml.safe_load(f)
            return data.get("api", {}).get("key", "")
    return os.getenv("RENDER_API_KEY", "")

RENDER_API_KEY = get_render_api_key()

def sync_env_vars():
    headers = {
        "Authorization": f"Bearer {RENDER_API_KEY}",
        "Content-Type": "application/json"
    }
    
    # 1. Fetch active services
    res = requests.get("https://api.render.com/v1/services", headers=headers)
    if res.status_code != 200:
        print(f"Failed to fetch services: {res.status_code} {res.text}")
        return False
        
    services = res.json()
    if not services:
        print("No services found in Render workspace. Create web service on dashboard first.")
        return False
        
    target_service = None
    for item in services:
        srv = item.get("service", {})
        if "agentline" in srv.get("name", "").lower() or srv.get("type") == "web_service":
            target_service = srv
            break
            
    if not target_service:
        target_service = services[0].get("service", {})
        
    service_id = target_service.get("id")
    service_name = target_service.get("name")
    print(f"Found Target Render Service: {service_name} ({service_id})")
    
    sa_file = "/Users/ajaytiwari/agentline_sa_key.json"
    sa_json_str = json.dumps(json.load(open(sa_file)))
    
    env_vars = [
        {"key": "COMPANY", "value": "deploymate"},
        {"key": "GEMINI_LIVE_VOICE", "value": "Aoede"},
        {"key": "AGENT_NAME", "value": "Kavya"},
        {"key": "GCP_PROJECT", "value": "igsl-67e70"},
        {"key": "GCP_LOCATION", "value": "us-central1"},
        {"key": "GCP_SERVICE_ACCOUNT_JSON", "value": sa_json_str},
        {"key": "GEMINI_API_KEY", "value": os.getenv("GEMINI_API_KEY", "")},
        {"key": "PLIVO_AUTH_ID", "value": os.getenv("PLIVO_AUTH_ID", "")},
        {"key": "PLIVO_AUTH_TOKEN", "value": os.getenv("PLIVO_AUTH_TOKEN", "")},
        {"key": "PLIVO_PHONE_NUMBER", "value": os.getenv("PLIVO_PHONE_NUMBER", "")},
        {"key": "MONGO_URI", "value": os.getenv("MONGO_URI", "")},
        {"key": "SMTP_USER", "value": os.getenv("SMTP_USER", "ajay.nukkadtechsolutions@gmail.com")},
        {"key": "SMTP_PASSWORD", "value": os.getenv("SMTP_PASSWORD", "dmck zhjp xnsb rcji")},
        {"key": "EMAIL_FROM", "value": os.getenv("EMAIL_FROM", "ajay.nukkadtechsolutions@gmail.com")}
    ]
    
    url = f"https://api.render.com/v1/services/{service_id}/env-vars"
    resp = requests.put(url, headers=headers, json=env_vars)
    print(f"Env Vars Sync HTTP Status: {resp.status_code}")
    if resp.status_code in [200, 201]:
        print(f"SUCCESS! All environment variables synced to {service_name} ({service_id})")
        # Trigger deploy
        deploy_url = f"https://api.render.com/v1/services/{service_id}/deploys"
        d_res = requests.post(deploy_url, headers=headers, json={"clearCache": "clear"})
        print(f"Deploy Trigger HTTP Status: {d_res.status_code}")
        return True
    else:
        print(f"Failed to sync env vars: {resp.text}")
        return False

if __name__ == "__main__":
    sync_env_vars()
