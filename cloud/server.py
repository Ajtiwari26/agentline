import os
import sys
import logging
import asyncio
from fastapi import FastAPI, WebSocket, Request, Depends, Response
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import config
from cloud.plivo_handler import handle_plivo_websocket, prewarm_plivo_pipeline
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
    logger.info("AgentLine Backend initialized with Gemini Live & Plivo Telephony.")

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
    Returns valid Plivo XML with <Stream> element for bidirectional audio.
    """
    params = request.query_params
    query_direction = params.get("direction") or params.get("Direction")
    query_phone = params.get("phone") or params.get("Phone")
    
    form_data = {}
    if request.method == "POST":
        try:
            form = await request.form()
            form_data = dict(form)
        except Exception:
            pass
        if not form_data:
            try:
                body_bytes = await request.body()
                if body_bytes:
                    import urllib.parse
                    parsed = urllib.parse.parse_qs(body_bytes.decode("utf-8"))
                    form_data = {k: v[0] if isinstance(v, list) and len(v) == 1 else v for k, v in parsed.items()}
            except Exception:
                pass
        if not form_data:
            try:
                form_data = await request.json()
            except Exception:
                pass

    # Resolve direction: explicit query parameter 'direction=outbound' takes highest priority
    direction_val = query_direction or form_data.get("Direction") or form_data.get("direction") or "inbound"
    direction = "outbound" if "outbound" in str(direction_val).lower() else "inbound"

    # Resolve phone number:
    # On outbound calls, the lead is query_phone or 'To'. On inbound calls, the lead is 'From'.
    if direction == "outbound":
        call_phone = query_phone or form_data.get("To") or form_data.get("to") or params.get("to") or form_data.get("From") or form_data.get("from") or "+919999999999"
    else:
        call_phone = form_data.get("From") or form_data.get("from") or query_phone or params.get("From") or params.get("from") or "+919999999999"
        
    call_uuid = form_data.get("CallUUID") or form_data.get("call_uuid") or form_data.get("CallUuid") or params.get("CallUUID") or params.get("call_uuid") or ""

    # Clean and sanitize phone number
    cleaned_phone = str(call_phone).strip().replace(" ", "")
    if not cleaned_phone.startswith("+"):
        cleaned_phone = "+" + cleaned_phone

    # ⚡ Pre-warm Gemini Live pipeline immediately in the background
    asyncio.create_task(prewarm_plivo_pipeline(cleaned_phone, direction=direction, call_uuid=call_uuid))
    
    host = request.headers.get("host")
    scheme = "wss" if request.url.scheme == "https" else "ws"
    
    # XML requires &amp; instead of bare & in URL attributes and text nodes
    websocket_url = f"{scheme}://{host}/ws/plivo?phone={cleaned_phone}&amp;direction={direction}&amp;call_uuid={call_uuid}"
    logger.info(f"Plivo call for {cleaned_phone} (Resolved Direction: {direction}) → Streaming to {websocket_url}")

    xml_content = f"""<?xml version="1.0" encoding="UTF-8"?>
<Response>
    <Stream bidirectional="true" keepCallAlive="true" contentType="audio/x-l16;rate=8000">{websocket_url}</Stream>
</Response>"""
    return Response(content=xml_content, media_type="application/xml")

@app.api_route("/plivo/prewarm", methods=["GET", "POST"])
async def plivo_prewarm_endpoint(phone: str, direction: str = "outbound", call_uuid: str = None):
    """Explicitly pre-warms a Gemini Live pipeline before placing an outbound call."""
    cleaned_phone = str(phone).strip().replace(" ", "")
    logger.info(f"API Trigger: Explicit pre-warm requested for {cleaned_phone}")
    asyncio.create_task(prewarm_plivo_pipeline(cleaned_phone, direction=direction, call_uuid=call_uuid))
    return {"status": "prewarming_initiated", "phone": cleaned_phone}

@app.api_route("/plivo/hangup", methods=["GET", "POST"])
async def plivo_hangup_endpoint(request: Request):
    """Plivo Hangup callback endpoint."""
    return Response(content="OK", media_type="text/plain")

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
