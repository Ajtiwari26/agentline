import os
import sys
import logging
import asyncio
from fastapi import FastAPI, WebSocket, Request, Depends, Response
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import config
from cloud.plivo_handler import handle_plivo_websocket
from cloud.ws_handler import handle_exotel_websocket
from cloud.web_handler import handle_web_websocket
from db.database import get_db, get_pending_callbacks

# Set up logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

app = FastAPI(title="AgentLine Telephony Cloud Backend")

# The DeployMate website pre-warms this service (GET /health) before a call.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["GET"],
    allow_headers=["*"],
)

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


@app.api_route("/voicebot", methods=["GET", "POST"])
async def voicebot_endpoint(request: Request):
    """
    Exotel Voicebot Applet makes HTTP request here.
    We return the wss:// URL of our websocket endpoint.
    """
    params = request.query_params
    call_from = params.get("CallFrom") or params.get("From") or "+919999999999"
    
    # Auto-detect direction from Exotel's callback parameters
    # Outbound API calls (trigger_exotel_call.py) send CallType=trans and Direction contains "outbound"
    # Inbound calls to our virtual number have Direction="inbound" or no CallType=trans
    exotel_direction = params.get("Direction", "").lower()
    exotel_call_type = params.get("CallType", "").lower()
    
    if "outbound" in exotel_direction or exotel_call_type == "trans":
        direction = "outbound"
    else:
        direction = "inbound"
    
    logger.info(f"Exotel voicebot request — CallFrom: {call_from}, Exotel Direction: {exotel_direction}, CallType: {exotel_call_type} → Resolved direction: {direction}")
    
    host = request.headers.get("host")
    # Resolve scheme (wss for https, ws for http)
    scheme = "wss" if request.url.scheme == "https" else "ws"
    websocket_url = f"{scheme}://{host}/ws/exotel?phone={call_from}&direction={direction}"
    logger.info(f"Directing to: {websocket_url}")
    return {"url": websocket_url}

@app.api_route("/plivo/answer", methods=["GET", "POST"])
@app.api_route("/plivo/voice", methods=["GET", "POST"])
async def plivo_answer_endpoint(request: Request):
    """
    Plivo Answer URL endpoint.
    Returns Plivo XML with <Stream> element for bidirectional audio.
    """
    params = request.query_params
    if request.method == "POST":
        try:
            form_data = await request.form()
            call_from = form_data.get("From") or params.get("From") or params.get("phone") or "+919999999999"
            direction_param = form_data.get("Direction") or params.get("Direction") or params.get("direction") or "inbound"
            call_uuid = form_data.get("CallUUID") or params.get("CallUUID") or ""
        except Exception:
            call_from = params.get("From") or params.get("phone") or "+919999999999"
            direction_param = params.get("Direction") or params.get("direction") or "inbound"
            call_uuid = params.get("CallUUID") or ""
    else:
        call_from = params.get("From") or params.get("phone") or "+919999999999"
        direction_param = params.get("Direction") or params.get("direction") or "inbound"
        call_uuid = params.get("CallUUID") or ""

    direction = "outbound" if "outbound" in direction_param.lower() else "inbound"
    
    host = request.headers.get("host")
    scheme = "wss" if request.url.scheme == "https" else "ws"
    websocket_url = f"{scheme}://{host}/ws/plivo?phone={call_from}&direction={direction}&call_uuid={call_uuid}"
    logger.info(f"Plivo call from {call_from} ({direction}) → Streaming to {websocket_url}")

    xml_content = f"""<?xml version="1.0" encoding="UTF-8"?>
<Response>
    <Stream bidirectional="true" keepCallAlive="true" contentType="audio/x-l16;rate=8000">{websocket_url}</Stream>
</Response>"""
    return Response(content=xml_content, media_type="application/xml")

@app.websocket("/ws/plivo")
async def plivo_websocket_route(websocket: WebSocket):
    """Bidirectional streaming WebSocket endpoint for Plivo audio."""
    await handle_plivo_websocket(websocket)

@app.websocket("/ws/exotel")
async def websocket_route(websocket: WebSocket):
    """Bidirectional streaming WebSocket endpoint for Exotel audio."""
    await handle_exotel_websocket(websocket)

@app.websocket("/ws/web")
async def web_websocket_route(websocket: WebSocket):
    """Browser voice endpoint for the DeployMate website inbound agent widget."""
    await handle_web_websocket(websocket)

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
