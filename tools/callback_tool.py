import os
import sys
from datetime import datetime, timedelta
import logging

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from db.database import schedule_callback

logger = logging.getLogger(__name__)

def schedule_manager_callback(
    phone: str, 
    time_str: str, 
    reason: str,
    name: str = "",
    remarks: str = "",
    doubts: str = "",
    times_called: str = ""
) -> str:
    """
    Schedules a callback for the manager.
    time_str can be:
    - 'morning' (defaults to next day 11:00 AM)
    - 'afternoon' (defaults to next day 3:00 PM)
    - 'tomorrow' (defaults to tomorrow same time)
    - A specific iso timestamp or custom string (e.g. '2026-07-09 10:00')
    """
    logger.info(f"Triggering callback tool. Phone: {phone}, requested time: {time_str}, reason: {reason}")
    
    now = datetime.utcnow()
    scheduled_dt = now + timedelta(days=1)  # Default tomorrow
    
    # Simple semantic parsing
    time_str_lower = time_str.lower()
    if "morning" in time_str_lower:
        scheduled_dt = datetime(scheduled_dt.year, scheduled_dt.month, scheduled_dt.day, 5, 30) # 11:00 AM IST is 5:30 AM UTC
    elif "afternoon" in time_str_lower:
        scheduled_dt = datetime(scheduled_dt.year, scheduled_dt.month, scheduled_dt.day, 9, 30) # 3:00 PM IST is 9:30 AM UTC
    elif "tomorrow" in time_str_lower:
        scheduled_dt = now + timedelta(days=1)
    else:
        # Try to parse custom formats
        for fmt in ("%Y-%m-%d %H:%M", "%d/%m/%Y %H:%M", "%I:%M %p"):
            try:
                parsed = datetime.strptime(time_str, fmt)
                if "%I:%M %p" in fmt:
                    # If only time, assume tomorrow or today
                    parsed = datetime(now.year, now.month, now.day, parsed.hour, parsed.minute)
                    if parsed < now:
                        parsed += timedelta(days=1)
                scheduled_dt = parsed
                break
            except ValueError:
                continue
                
    # Save to MongoDB
    try:
        callback_id = schedule_callback(
            phone=phone, 
            scheduled_time=scheduled_dt, 
            reason=reason,
            name=name,
            remarks=remarks,
            doubts=doubts,
            times_called=times_called
        )
        # Convert UTC back to IST for displaying to agent/caller
        ist_time = scheduled_dt + timedelta(hours=5, minutes=30)
        formatted_ist = ist_time.strftime("%I:%M %p on %d %b")
        return f"Successfully scheduled a callback for the manager to call {phone} at {formatted_ist}. Callback ID: {callback_id}"
    except Exception as e:
        logger.error(f"Failed to schedule callback: {e}")
        return "Failed to schedule callback due to a database error."
