import os
import plivo
from dotenv import load_dotenv

load_dotenv()

auth_id = os.getenv("PLIVO_AUTH_ID")
auth_token = os.getenv("PLIVO_AUTH_TOKEN")

client = plivo.RestClient(auth_id=auth_id, auth_token=auth_token)

print("Fetching latest calls from Plivo...")
try:
    calls = client.calls.list(limit=5)
    for c in calls:
        call_obj = client.calls.get(c.call_uuid)
        print(f"Call UUID: {c.call_uuid}")
        print(f"From: {c.from_number} -> To: {c.to_number}")
        print(f"Status: {getattr(c, 'call_state', getattr(c, 'status', 'unknown'))}")
        print(f"Hangup Cause: {getattr(call_obj, 'hangup_cause_name', getattr(call_obj, 'hangup_cause', 'unknown'))}")
        print(f"Duration: {getattr(call_obj, 'duration', 0)}s, Billed: {getattr(call_obj, 'billed_duration', 0)}s")
        print(f"Total Amount: {getattr(call_obj, 'total_amount', 0)}")
        print("-" * 50)
except Exception as e:
    print(f"Error fetching calls: {e}")
