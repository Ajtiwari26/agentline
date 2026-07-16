import os
import sys
import time
import requests
import pymongo
from pymongo import MongoClient

API_KEY = "c553f57ba6b95deea972be66b48b141eb266830dc9abdf68"
API_TOKEN = "a8bdae63c7eb4b50ebe7ac4cc0ef178827c36755d98f5209"
ACCOUNT_SID = "nukkadfoods1"
CALLER_ID = "07314625737"
FLOW_ID = "1290053"

def trigger_outbound_call(target_phone, company_name):
    url = f"https://api.exotel.com/v1/Accounts/{ACCOUNT_SID}/Calls/connect.json"
    flow_url = f"http://my.exotel.com/{ACCOUNT_SID}/exoml/start_voice/{FLOW_ID}"
    
    payload = {
        "From": target_phone,
        "CallerId": CALLER_ID,
        "Url": flow_url,
        "CallType": "trans"
    }
    
    print(f"Triggering outbound call to {company_name} ({target_phone})...")
    response = requests.post(url, auth=(API_KEY, API_TOKEN), data=payload)
    
    if response.status_code in [200, 201]:
        res_data = response.json()
        call_sid = res_data.get("Call", {}).get("Sid")
        print(f"Success! Call triggered. SID: {call_sid}")
        return call_sid
    else:
        print(f"Failed to trigger call: {response.status_code} - {response.text}")
        return None

def main():
    mongo_uri = "mongodb+srv://igsl:igsl@igsl.pvetwys.mongodb.net/?appName=igsl"
    client = MongoClient(mongo_uri)
    db = client["agentline"]
    leads_collection = db["leads"]
    
    # Query leads in Sector 2
    query = {"notes": {"$regex": "Sector 2"}}
    sector2_leads = list(leads_collection.find(query))
    
    print(f"Found {len(sector2_leads)} leads in Sector 2 (Education & Coaching):")
    for i, lead in enumerate(sector2_leads):
        print(f"{i+1}. {lead.get('name')} - {lead.get('phone')}")
        
    print("\nStarting outbound calling campaign for Sector 2...")
    
    triggered_count = 0
    for lead in sector2_leads:
        phone = lead.get("phone")
        name = lead.get("name")
        
        if not phone or not name:
            continue
            
        # Trigger the call
        call_sid = trigger_outbound_call(phone, name)
        if call_sid:
            triggered_count += 1
            
        # Wait 20 seconds between triggering calls to avoid flooding
        if triggered_count < len(sector2_leads):
            print("Waiting 20 seconds before triggering the next call...")
            time.sleep(20)
            
    print(f"\nCampaign complete! Successfully triggered {triggered_count} outbound calls.")

if __name__ == "__main__":
    main()
