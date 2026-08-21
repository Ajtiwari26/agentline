import os
import sys
import requests
from dotenv import load_dotenv

# Load .env file
load_dotenv()

def trigger_plivo_call(target_phone: str, server_url: str = None, caller_id: str = None):
    """
    Triggers an outbound call using Plivo's REST API.
    When the user answers, Plivo fetches the answer_url which streams audio bi-directionally.
    """
    auth_id = os.getenv("PLIVO_AUTH_ID")
    auth_token = os.getenv("PLIVO_AUTH_TOKEN")
    from_number = caller_id or os.getenv("PLIVO_PHONE_NUMBER", "")
    
    # Format target phone with country code if not present (default to India +91)
    cleaned_target = target_phone.strip().replace(" ", "").replace("-", "")
    if not cleaned_target.startswith("+"):
        if cleaned_target.startswith("0"):
            cleaned_target = "+91" + cleaned_target[1:]
        elif len(cleaned_target) == 10:
            cleaned_target = "+91" + cleaned_target
        else:
            cleaned_target = "+" + cleaned_target

    if not auth_id or not auth_token:
        print("Error: Missing PLIVO_AUTH_ID or PLIVO_AUTH_TOKEN in .env file.")
        sys.exit(1)

    if not from_number:
        print("Warning: PLIVO_PHONE_NUMBER not set in .env. Plivo requires a valid 'from' number or Caller ID.")
        print("Please configure PLIVO_PHONE_NUMBER in .env.")

    # Base URL for backend server (defaults to Render deployment or override)
    base_url = server_url or os.getenv("BACKEND_URL", "https://agentline-backend.onrender.com")
    base_url = base_url.rstrip("/")
    answer_url = f"{base_url}/plivo/answer?direction=outbound&phone={cleaned_target}"

    url = f"https://api.plivo.com/v1/Account/{auth_id}/Call/"
    payload = {
        "from": from_number,
        "to": cleaned_target,
        "answer_url": answer_url,
        "answer_method": "POST"
    }

    print(f"Triggering Plivo outbound call to {cleaned_target} from {from_number}...")
    print(f"Answer URL: {answer_url}")
    
    response = requests.post(url, auth=(auth_id, auth_token), json=payload)

    if response.status_code in [200, 201]:
        res_data = response.json()
        request_uuid = res_data.get("request_uuid") or res_data.get("call_uuid")
        print(f"Success! Call initiated. Request UUID: {request_uuid}")
        print(f"Response: {res_data}")
        return request_uuid
    else:
        print(f"Failed to initiate call: {response.status_code} - {response.text}")
        return None

if __name__ == "__main__":
    target = "9399250600"
    if len(sys.argv) > 1:
        target = sys.argv[1].strip()
    trigger_plivo_call(target)
