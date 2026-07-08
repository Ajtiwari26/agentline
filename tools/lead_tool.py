import os
import sys
import logging

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from db.database import upsert_lead

logger = logging.getLogger(__name__)

def update_lead_status(phone: str, interest_level: str, notes: str, name: str = "") -> str:
    """
    Updates the lead's status and notes in the database.
    Called by the AI Agent when a customer displays interest, asks for callbacks, or has objections.
    """
    logger.info(f"Triggering lead tool. Phone: {phone}, interest: {interest_level}, name: {name}, notes: {notes}")
    
    interest_level = interest_level.lower().strip()
    if interest_level not in ("hot", "warm", "cold"):
        interest_level = "warm" # Default fallback
        
    try:
        upsert_lead(
            phone=phone,
            name=name if name else None,
            interest_level=interest_level,
            notes=notes
        )
        return f"Successfully updated lead status to '{interest_level}' with notes: '{notes}'."
    except Exception as e:
        logger.error(f"Failed to update lead status: {e}")
        return "Failed to update lead status due to a database error."
