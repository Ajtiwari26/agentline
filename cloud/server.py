import os
import sys
import logging
import asyncio
from fastapi import FastAPI, WebSocket, Request, Depends
from fastapi.responses import JSONResponse

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import config
from cloud.ws_handler import handle_exotel_websocket
from db.database import get_db, get_pending_callbacks

# Set up logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

app = FastAPI(title="AgentLine Telephony Cloud Backend")

@app.on_event("startup")
async def startup_event():
    # Pre-cache the welcome message so it's ready immediately
    from core.tts import pre_cache_welcome_message
    from core.prompts import load_kb
    kb = load_kb()
    welcome_text = kb.get("conversation_stages", {}).get("greeting", {}).get("script", "Hey! Kaise ho?")
    asyncio.create_task(pre_cache_welcome_message(welcome_text))

@app.get("/health")
async def health_check():
    return {"status": "healthy", "mode": "cloud_inbound"}

@app.get("/test-gemini")
async def test_gemini_models():
    import os
    from google import genai
    from google.oauth2 import service_account
    
    sa_key_path = os.getenv("GOOGLE_APPLICATION_CREDENTIALS", "")
    project = os.getenv("GCP_PROJECT", "igsl-67e70")
    
    if not sa_key_path or not os.path.exists(sa_key_path):
        return {"error": f"No service account key found at path: {sa_key_path}"}
        
    try:
        scopes = ["https://www.googleapis.com/auth/cloud-platform"]
        credentials = service_account.Credentials.from_service_account_file(sa_key_path, scopes=scopes)
        client = genai.Client(
            vertexai=True,
            project=project,
            location="us-central1",
            credentials=credentials
        )
        
        models = [
            "gemini-1.5-flash", 
            "gemini-1.5-flash-001", 
            "gemini-1.5-flash-002", 
            "gemini-2.5-flash", 
            "gemini-2.0-flash-exp"
        ]
        results = {}
        for m in models:
            try:
                res = client.models.generate_content(model=m, contents="ping")
                results[m] = {"status": "success", "text": res.text.strip() if res.text else ""}
            except Exception as e:
                results[m] = {"status": "failed", "error": str(e)}
        return {"results": results}
    except Exception as e:
        return {"error": str(e)}

@app.api_route("/voicebot", methods=["GET", "POST"])
async def voicebot_endpoint(request: Request):
    """
    Exotel Voicebot Applet makes HTTP request here.
    We return the wss:// URL of our websocket endpoint.
    """
    params = request.query_params
    call_from = params.get("CallFrom") or params.get("From") or "+919999999999"
    direction = "outbound"  # Force outbound to play the welcome greeting immediately
    
    host = request.headers.get("host")
    # Resolve scheme (wss for https, ws for http)
    scheme = "wss" if request.url.scheme == "https" else "ws"
    websocket_url = f"{scheme}://{host}/ws/exotel?phone={call_from}&direction={direction}"
    logger.info(f"Received call routing query from Exotel. Directing to: {websocket_url}")
    return {"url": websocket_url}

@app.websocket("/ws/exotel")
async def websocket_route(websocket: WebSocket):
    """Bidirectional streaming WebSocket endpoint for Exotel audio."""
    await handle_exotel_websocket(websocket)

# Leads Dashboard APIs
@app.get("/api/leads")
async def api_get_leads():
    """Retrieve logged leads and their interest level."""
    try:
        db = get_db()
        leads = list(db.leads.find({}, {"_id": 0}).sort("last_contacted", -1))
        return JSONResponse(content={"success": True, "leads": leads})
    except Exception as e:
        logger.error(f"Error fetching leads: {e}")
        return JSONResponse(status_code=500, content={"success": False, "error": str(e)})

@app.get("/api/callbacks")
async def api_get_callbacks():
    """Retrieve scheduled callbacks."""
    try:
        callbacks = get_pending_callbacks()
        # Convert _id to string for serialization
        for cb in callbacks:
            cb["_id"] = str(cb["_id"])
            if isinstance(cb.get("scheduled_time"), datetime):
                # import datetime inside if needed or let bson/pymongo handle
                pass
        # To avoid datetime serialization issues, we convert timestamps to iso strings
        import datetime
        for cb in callbacks:
            if isinstance(cb.get("scheduled_time"), datetime.datetime):
                cb["scheduled_time"] = cb["scheduled_time"].isoformat()
            if isinstance(cb.get("created_at"), datetime.datetime):
                cb["created_at"] = cb["created_at"].isoformat()
        return JSONResponse(content={"success": True, "callbacks": callbacks})
    except Exception as e:
        logger.error(f"Error fetching callbacks: {e}")
        return JSONResponse(status_code=500, content={"success": False, "error": str(e)})
