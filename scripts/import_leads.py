import csv
import os
import pymongo
from pymongo import MongoClient
from dotenv import load_dotenv

load_dotenv()

def run_import():
    # 1. Connect to MongoDB
    mongo_uri = os.getenv("MONGO_URI", os.getenv("MONGODB_URI", "mongodb://localhost:27017/"))
    print("Connecting to MongoDB...")

    client = MongoClient(mongo_uri)
    db = client["agentline"]
    leads_collection = db["leads"]
    
    # 2. Path to leads CSV
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    csv_path = os.path.join(base_dir, "leads_bhopal.csv")
    
    if not os.path.exists(csv_path):
        print(f"Error: leads_bhopal.csv not found at {csv_path}")
        return
        
    print(f"Reading leads from {csv_path}...")
    imported_count = 0
    
    with open(csv_path, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            name = row.get("name", "").strip()
            phone = row.get("phone", "").strip()
            email = row.get("email", "").strip()
            role = row.get("role", "").strip()
            address = row.get("address", "").strip()
            overview = row.get("overview", "").strip()
            trigger = row.get("trigger", "").strip()
            sector = row.get("sector", "").strip()
            
            if not phone or not name:
                continue
                
            # Compile structured notes
            notes = (
                f"Role: {role}\n"
                f"Sector: {sector}\n"
                f"Address: {address}\n"
                f"Overview: {overview}\n"
                f"Trigger: {trigger}"
            )
            
            # Upsert into MongoDB
            leads_collection.update_one(
                {"phone": phone},
                {
                    "$set": {
                        "name": name,
                        "email": email,
                        "notes": notes,
                        "interest_level": "cold"
                    }
                },
                upsert=True
            )
            imported_count += 1
            
    print(f"Successfully imported/updated {imported_count} leads from CSV!")
    
    # 3. Configure lead context for Ajay Tiwari (+919399250600) as Coaching Owner in Bhopal
    personal_phones = ["+919399250600", "09399250600", "9399250600"]
    coaching_notes = (
        "Company: Ajay Tutorials (Bhopal Coaching Center)\n"
        "Role: Coaching Owner & Director\n"
        "Sector: Coaching & Test Prep Institutes (Bhopal)\n"
        "Address: Zone-II, MP Nagar, Bhopal\n"
        "Overview: Premier competitive exam & board foundation coaching institute in Bhopal.\n"
        "Trigger/Pitch Context: Pitch DeployMate AI Voice Agents for: "
        "1) Instant 30-sec follow-up on student admission inquiries, "
        "2) Automated parent-teacher counseling session booking, "
        "3) WhatsApp bot for test score, rank cards & syllabus delivery, "
        "4) Polite automated voice reminders for fee installments."
    )
    for ph in personal_phones:
        leads_collection.update_one(
            {"phone": ph},
            {
                "$set": {
                    "name": "Ajay Tiwari (Ajay Tutorials)",
                    "email": "tiwariajay033@gmail.com",
                    "notes": coaching_notes,
                    "interest_level": "hot"
                }
            },
            upsert=True
        )
    print("Successfully configured coaching institute lead profile (Ajay Tutorials) in DB!")

if __name__ == "__main__":
    run_import()
