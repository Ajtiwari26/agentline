import os
import plivo
from dotenv import load_dotenv

load_dotenv()

auth_id = os.getenv("PLIVO_AUTH_ID")
auth_token = os.getenv("PLIVO_AUTH_TOKEN")
my_number = os.getenv("PLIVO_PHONE_NUMBER")

client = plivo.RestClient(auth_id=auth_id, auth_token=auth_token)

print(f"Checking Plivo account: {auth_id}")
print(f"Target Number: {my_number}\n")

print("--- 1. Account Numbers ---")
try:
    numbers = client.numbers.list()
    for num in numbers:
        print(f"Number: {getattr(num, 'number', None)}, Alias: {getattr(num, 'alias', None)}, Application: {getattr(num, 'application', None)}")
except Exception as e:
    print(f"Error fetching numbers: {e}")

print("\n--- 2. Applications ---")
try:
    apps = client.applications.list()
    for app in apps:
        print(f"App Name: {app.app_name}, App ID: {app.app_id}, Answer URL: {app.answer_url}")
except Exception as e:
    print(f"Error fetching applications: {e}")
