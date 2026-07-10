import urllib.request
import csv
import io
import os
import re

url = "https://docs.google.com/spreadsheets/d/1U_4V3eM4j-7L5Y8CXvOELf_lhgp-Rhxnxb2PTZ1bglo/export?format=csv"
output_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "leads_bhopal.csv")

def clean_phone(phone_str):
    if not phone_str:
        return ""
    # Remove spaces, parentheses, hyphens
    cleaned = re.sub(r'[\s\(\)\-\[\]]', '', phone_str)
    # If it's a 10 digit number and doesn't start with country code, prefix +91
    if len(cleaned) == 10 and cleaned.isdigit():
        cleaned = "+91" + cleaned
    elif len(cleaned) == 12 and cleaned.startswith("91") and cleaned.isdigit():
        cleaned = "+" + cleaned
    return cleaned

try:
    print(f"Downloading leads from Google Sheet: {url}")
    response = urllib.request.urlopen(url)
    csv_data = response.read().decode('utf-8')
    reader = csv.reader(io.StringIO(csv_data))
    
    leads = []
    current_sector = ""
    
    for i, row in enumerate(reader):
        if not row:
            continue
        
        # Check if this is a sector header (e.g. Row 0 or similar)
        if len(row) > 0 and "Sector" in row[0]:
            current_sector = row[0].strip()
            print(f"Found Sector: {current_sector}")
            continue
            
        if len(row) > 1:
            name = row[0].strip()
            phone_raw = row[1].strip()
            email = row[2].strip() if len(row) > 2 else ""
            role = row[3].strip() if len(row) > 3 else ""
            address = row[4].strip() if len(row) > 4 else ""
            overview = row[5].strip() if len(row) > 5 else ""
            trigger = row[6].strip() if len(row) > 6 else ""
            
            # Skip header row or empty phone
            if name == "Company Name" or not phone_raw or phone_raw.lower() == "contact number":
                continue
                
            phone = clean_phone(phone_raw)
            if phone:
                leads.append({
                    "name": name,
                    "phone": phone,
                    "email": email,
                    "role": role,
                    "address": address,
                    "overview": overview,
                    "trigger": trigger,
                    "sector": current_sector
                })
                
    print(f"Total leads parsed: {len(leads)}")
    
    # Save to CSV
    with open(output_path, "w", newline="", encoding="utf-8") as f:
        fieldnames = ["name", "phone", "email", "role", "address", "overview", "trigger", "sector"]
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for lead in leads:
            writer.writerow(lead)
            
    print(f"Leads successfully saved to: {output_path}")
    
    # Print the first 3 leads for verification
    print("\nSample Leads:")
    for j, lead in enumerate(leads[:3]):
        print(f"Lead {j+1}: {lead['name']} ({lead['phone']}) - Sector: {lead['sector']}")
        
except Exception as e:
    print(f"Error downloading or parsing leads: {e}")
