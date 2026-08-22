import os
import sys
import plivo
from dotenv import load_dotenv

load_dotenv()

auth_id = os.getenv("PLIVO_AUTH_ID")
auth_token = os.getenv("PLIVO_AUTH_TOKEN")
my_number = os.getenv("PLIVO_PHONE_NUMBER", "918031907525")
clean_number = my_number.replace("+", "").replace(" ", "")

server_url = sys.argv[1] if len(sys.argv) > 1 else os.getenv("BACKEND_URL", "https://agentline-backend.onrender.com")
server_url = server_url.rstrip("/")
answer_url = f"{server_url}/plivo/answer?direction=inbound"

client = plivo.RestClient(auth_id=auth_id, auth_token=auth_token)

print(f"Setting up Inbound Voice for Plivo Number: {clean_number}")
print(f"Target Answer URL: {answer_url}")

# 1. Look for existing 'AgentLine_Voice_AI' application or create a new one
app_name = "AgentLine_Voice_AI"
target_app_id = None

try:
    apps = client.applications.list()
    for app in apps:
        if app.app_name == app_name:
            target_app_id = app.app_id
            print(f"Found existing application '{app_name}' with ID: {target_app_id}")
            break
except Exception as e:
    print(f"Error searching applications: {e}")

if target_app_id:
    # Update existing application
    print(f"Updating Answer URL for application {target_app_id}...")
    update_res = client.applications.update(
        app_id=target_app_id,
        answer_url=answer_url,
        answer_method="POST",
        hangup_url=f"{server_url}/plivo/hangup",
        hangup_method="POST"
    )
    print(f"Application update response: {update_res}")
else:
    # Create new application
    print(f"Creating new Plivo Application '{app_name}'...")
    create_res = client.applications.create(
        app_name=app_name,
        answer_url=answer_url,
        answer_method="POST",
        hangup_url=f"{server_url}/plivo/hangup",
        hangup_method="POST",
        default_endpoint_app=False
    )
    target_app_id = create_res.app_id
    print(f"Created Application with ID: {target_app_id}")

# 2. Link application to our phone number
print(f"Linking Application {target_app_id} to Number {clean_number}...")
try:
    link_res = client.numbers.update(
        number=clean_number,
        app_id=target_app_id
    )
    print(f"Success! Number {clean_number} is now linked to Application {target_app_id}")
    print(f"Response: {link_res}")
except Exception as e:
    print(f"Error linking number to application: {e}")
