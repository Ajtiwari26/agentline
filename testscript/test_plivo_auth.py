import os
import sys
import requests
from dotenv import load_dotenv

# Load env variables
load_dotenv()

auth_id = os.getenv("PLIVO_AUTH_ID")
auth_token = os.getenv("PLIVO_AUTH_TOKEN")

print(f"Testing Plivo Credentials: Auth ID = {auth_id}")

if not auth_id or not auth_token:
    print("Error: PLIVO_AUTH_ID or PLIVO_AUTH_TOKEN missing.")
    sys.exit(1)

# 1. Fetch Account Details
url = f"https://api.plivo.com/v1/Account/{auth_id}/"
resp = requests.get(url, auth=(auth_id, auth_token))

print(f"Account Details Response Status: {resp.status_code}")
if resp.status_code == 200:
    data = resp.json()
    print("Account Details:")
    print(f"  Name: {data.get('name')}")
    print(f"  Cash Credits: {data.get('cash_credits')}")
    print(f"  Account Type: {data.get('account_type')}")
    print(f"  State: {data.get('state')}")
else:
    print(f"Error fetching account details: {resp.text}")

# 2. Fetch Active Numbers
num_url = f"https://api.plivo.com/v1/Account/{auth_id}/Number/"
num_resp = requests.get(num_url, auth=(auth_id, auth_token))
print(f"\nNumbers Response Status: {num_resp.status_code}")
if num_resp.status_code == 200:
    numbers = num_resp.json().get("objects", [])
    print(f"Found {len(numbers)} active phone number(s):")
    for n in numbers:
        print(f"  - Number: {n.get('number')}, Type: {n.get('type')}, Alias: {n.get('alias')}")
else:
    print(f"Error fetching numbers: {num_resp.text}")
