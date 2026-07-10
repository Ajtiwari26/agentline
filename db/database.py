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
    update_doc: Dict[str, Any] = {
        "$set": {
            "interest_level": interest_level,
            "last_contacted": datetime.utcnow()
        }
    }
    
    if name:
        update_doc["$set"]["name"] = name
        
    if notes:
        # Append notes if already exists, otherwise set
        update_doc["$set"]["notes"] = notes
        
    db.leads.update_one(
        {"phone": phone},
        update_doc,
        upsert=True
    )
    return db.leads.find_one({"phone": phone})

def get_lead(phone: str) -> Optional[Dict[str, Any]]:
    db = get_db()
    return db.leads.find_one({"phone": phone})

def add_conversation(call_id: str, phone: str, transcript: List[Dict[str, Any]], duration_seconds: int, mode: str, direction: str) -> str:
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
    
    db.conversations.insert_one(convo)
    
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
    
    # Log note on lead
    note_msg = f"\n[System] Scheduled callback for {scheduled_time.strftime('%Y-%m-%d %H:%M UTC')} due to: {reason}. Remarks: {remarks}. Doubts: {doubts}. Times called: {times_called}"
    db.leads.update_one(
        {"phone": phone},
        {"$set": {"last_contacted": datetime.utcnow()}, "$push": {"notes": note_msg}},
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
    
    # Append to lead notes
    note_msg = f"\n[System] Email sent: '{subject}'"
    db.leads.update_one(
        {"phone": phone},
        {"$push": {"notes": note_msg}},
        upsert=True
    )
