import os
import sys
import requests
from dotenv import load_dotenv

# Load .env file
load_dotenv()

def trigger_call(target_phone):
    api_key = os.getenv("EXOTEL_API_KEY")
    api_token = os.getenv("EXOTEL_API_TOKEN")
    account_sid = os.getenv("EXOTEL_ACCOUNT_SID")
    caller_id = os.getenv("EXOTEL_VIRTUAL_NUMBER", "09513886363")
    flow_id = "1290053"  # Flow ID for voice agent

    if not api_key or not api_token or not account_sid:
        print("Error: Missing Exotel credentials in .env file.")
        sys.exit(1)

    url = f"https://api.exotel.com/v1/Accounts/{account_sid}/Calls/connect.json"
    flow_url = f"http://my.exotel.com/{account_sid}/exoml/start_voice/{flow_id}"

    payload = {
        "From": target_phone,
        "CallerId": caller_id,
        "Url": flow_url,
        "CallType": "trans"
    }

    print(f"Triggering Exotel outbound call to {target_phone} from {caller_id}...")
    response = requests.post(url, auth=(api_key, api_token), data=payload)

    if response.status_code in [200, 201]:
        res_data = response.json()
        call_sid = res_data.get("Call", {}).get("Sid")
        print(f"Success! Call triggered. SID: {call_sid}")
        return call_sid
    else:
        print(f"Failed to trigger call: {response.status_code} - {response.text}")
        return None

if __name__ == "__main__":
    target = "9399250600"
    if len(sys.argv) > 1:
        target = sys.argv[1].strip()
    trigger_call(target)
