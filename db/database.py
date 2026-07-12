from datetime import datetime
from typing import List, Dict, Any, Optional
import pymongo
from pymongo import MongoClient
import sys

# Add path so config is importable
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import config

_client = None

def get_client() -> MongoClient:
    global _client
    if _client is None:
        _client = MongoClient(config.MONGO_URI)
    return _client

def get_db():
    client = get_client()
    return client[config.MONGO_DB_NAME]

def setup_indexes():
    """Create unique indexes and common search indexes."""
    db = get_db()
    
    # Lead indexes
    db.leads.create_index("phone", unique=True)
    db.leads.create_index("interest_level")
    
    # Conversation indexes
    db.conversations.create_index("call_id", unique=True)
    db.conversations.create_index("phone")
    
    # Callback indexes
    db.callbacks.create_index([("phone", 1), ("status", 1)])
    db.callbacks.create_index("scheduled_time")

def upsert_lead(phone: str, name: Optional[str] = None, interest_level: str = "cold", notes: str = "") -> Dict[str, Any]:
    db = get_db()
    
    # Retrieve existing lead to handle notes safely
    lead = db.leads.find_one({"phone": phone})
    
    # Handle notes aggregation as a string
    existing_notes = ""
    if lead and "notes" in lead:
        if isinstance(lead["notes"], list):
            existing_notes = "\n".join(str(n) for n in lead["notes"])
        else:
            existing_notes = str(lead["notes"])
            
    new_notes = notes
    if existing_notes and notes:
        new_notes = existing_notes + f"\n{notes}"
    elif existing_notes:
        new_notes = existing_notes

    update_doc: Dict[str, Any] = {
        "$set": {
            "interest_level": interest_level,
            "last_contacted": datetime.utcnow()
        }
    }
    
    if name:
        update_doc["$set"]["name"] = name
        
    if new_notes:
        update_doc["$set"]["notes"] = new_notes
        
    db.leads.update_one(
        {"phone": phone},
        update_doc,
        upsert=True
    )
    return db.leads.find_one({"phone": phone})

def get_lead(phone: str) -> Optional[Dict[str, Any]]:
    db = get_db()
    # Try exact match first
    lead = db.leads.find_one({"phone": phone})
    if lead:
        return lead
        
    # Check variations based on last 10 digits (common for Indian numbers)
    if len(phone) >= 10:
        last_10 = phone[-10:]
        variations = [last_10, f"0{last_10}", f"+91{last_10}"]
        for var in variations:
            if var != phone:
                lead = db.leads.find_one({"phone": var})
                if lead:
                    return lead
    return None

def add_conversation(
    call_id: str, 
    phone: str, 
    transcript: List[Dict[str, Any]], 
    duration_seconds: int, 
    mode: str, 
    direction: str,
    summary: Optional[str] = None,
    recording_url: Optional[str] = None
) -> str:
    db = get_db()
    
    # Transform transcript turns to append timestamp if not present
    formatted_transcript = []
    for turn in transcript:
        formatted_transcript.append({
            "sender": turn.get("sender"),
            "text": turn.get("text"),
            "timestamp": turn.get("timestamp", datetime.utcnow())
        })
        
    convo = {
        "call_id": call_id,
        "phone": phone,
        "transcript": formatted_transcript,
        "duration_seconds": duration_seconds,
        "mode": mode,
        "direction": direction,
        "timestamp": datetime.utcnow()
    }
    if summary:
        convo["summary"] = summary
    if recording_url:
        convo["recording_url"] = recording_url
        
    db.conversations.insert_one(convo)
    
    # Append summary and recording link to lead notes
    note_msg = ""
    if summary:
        note_msg += f"\n[AI Call Summary]:\n{summary}"
    if recording_url:
        note_msg += f"\n[Call Recording]: {recording_url}"
        
    if note_msg:
        # Fetch current lead
        lead = db.leads.find_one({"phone": phone})
        existing_notes = ""
        if lead and "notes" in lead:
            if isinstance(lead["notes"], list):
                existing_notes = "\n".join(str(n) for n in lead["notes"])
            else:
                existing_notes = str(lead["notes"])
                
        new_notes = existing_notes + note_msg if existing_notes else note_msg.strip()
        db.leads.update_one(
            {"phone": phone},
            {
                "$push": {"conversation_ids": call_id},
                "$set": {
                    "last_contacted": datetime.utcnow(),
                    "notes": new_notes
                }
            },
            upsert=True
        )
    else:
        # Link to lead
        db.leads.update_one(
            {"phone": phone},
            {
                "$push": {"conversation_ids": call_id},
                "$set": {"last_contacted": datetime.utcnow()}
            },
            upsert=True
        )
    return call_id

def schedule_callback(
    phone: str, 
    scheduled_time: datetime, 
    reason: str,
    name: Optional[str] = None,
    remarks: Optional[str] = None,
    doubts: Optional[str] = None,
    times_called: Optional[str] = None
) -> str:
    db = get_db()
    
    # 1. Automatically fetch name if not provided
    if not name:
        lead = db.leads.find_one({"phone": phone})
        if lead:
            name = lead.get("name", "")
            
    # 2. Automatically calculate times called if not provided
    if not times_called:
        call_count = db.conversations.count_documents({"phone": phone}) + 1
        if call_count == 1:
            times_called = "first"
        elif call_count == 2:
            times_called = "second"
        elif call_count == 3:
            times_called = "third"
        else:
            times_called = f"{call_count}th"
            
    # 3. Use reason as default remarks if remarks not provided
    if not remarks:
        remarks = reason
        
    callback_doc = {
        "phone": phone,
        "name": name or "",
        "scheduled_time": scheduled_time,
        "reason": reason,
        "remarks": remarks,
        "doubts": doubts or "",
        "times_called": times_called,
        "status": "pending",
        "created_at": datetime.utcnow()
    }
    result = db.callbacks.insert_one(callback_doc)
    
    # Log note on lead safely as a string
    note_msg = f"[System] Scheduled callback for {scheduled_time.strftime('%Y-%m-%d %H:%M UTC')} due to: {reason}. Remarks: {remarks}. Doubts: {doubts}. Times called: {times_called}"
    
    lead = db.leads.find_one({"phone": phone})
    existing_notes = ""
    if lead and "notes" in lead:
        if isinstance(lead["notes"], list):
            existing_notes = "\n".join(str(n) for n in lead["notes"])
        else:
            existing_notes = str(lead["notes"])
            
    new_notes = note_msg
    if existing_notes:
        new_notes = existing_notes + f"\n{note_msg}"
        
    db.leads.update_one(
        {"phone": phone},
        {"$set": {"last_contacted": datetime.utcnow(), "notes": new_notes}},
        upsert=True
    )
    
    return str(result.inserted_id)

def get_pending_callbacks() -> List[Dict[str, Any]]:
    db = get_db()
    return list(db.callbacks.find({"status": "pending"}).sort("scheduled_time", 1))

def log_email(phone: str, subject: str, body: str, status: str = "sent") -> None:
    db = get_db()
    email_doc = {
        "phone": phone,
        "subject": subject,
        "body": body,
        "sent_at": datetime.utcnow(),
        "status": status
    }
    db.emails.insert_one(email_doc)
    
    # Append to lead notes safely as a string
    note_msg = f"[System] Email sent: '{subject}'"
    
    lead = db.leads.find_one({"phone": phone})
    existing_notes = ""
    if lead and "notes" in lead:
        if isinstance(lead["notes"], list):
            existing_notes = "\n".join(str(n) for n in lead["notes"])
        else:
            existing_notes = str(lead["notes"])
            
    new_notes = note_msg
    if existing_notes:
        new_notes = existing_notes + f"\n{note_msg}"
        
    db.leads.update_one(
        {"phone": phone},
        {"$set": {"notes": new_notes, "last_contacted": datetime.utcnow()}},
        upsert=True
    )
