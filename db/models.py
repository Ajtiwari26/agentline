from datetime import datetime
from typing import List, Dict, Optional
from pydantic import BaseModel, Field

class Lead(BaseModel):
    phone: str = Field(..., description="10-digit phone number with country code")
    name: Optional[str] = None
    interest_level: str = "cold"  # hot, warm, cold
    notes: Optional[str] = ""
    last_contacted: datetime = Field(default_factory=datetime.utcnow)
    conversation_ids: List[str] = Field(default_factory=list)

class TranscriptTurn(BaseModel):
    sender: str  # "agent", "user", "system"
    text: str
    timestamp: datetime = Field(default_factory=datetime.utcnow)

class Conversation(BaseModel):
    call_id: str
    phone: str
    transcript: List[TranscriptTurn] = Field(default_factory=list)
    duration_seconds: int = 0
    mode: str = "local"  # local, cloud
    direction: str = "inbound"  # inbound, outbound
    timestamp: datetime = Field(default_factory=datetime.utcnow)

class ScheduledCallback(BaseModel):
    phone: str
    scheduled_time: datetime
    reason: str
    status: str = "pending"  # pending, completed, cancelled
    created_at: datetime = Field(default_factory=datetime.utcnow)

class EmailLog(BaseModel):
    phone: str
    subject: str
    body: str
    sent_at: datetime = Field(default_factory=datetime.utcnow)
    status: str = "sent"  # sent, failed
