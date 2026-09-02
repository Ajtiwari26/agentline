import json
import base64
import logging
import asyncio
from fastapi import WebSocket, WebSocketDisconnect

import os
import sys
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from core.pipeline import VoicePipeline

logger = logging.getLogger(__name__)

def normalize_phone(p: str) -> str:
    """Strips all non-digits and returns last 10 digits for consistent matching."""
    digits = "".join(filter(str.isdigit, str(p or "")))
    if len(digits) > 10:
        return digits[-10:]
    return digits

# In-memory registry for pre-warmed pipelines (keyed by call_uuid and canonical phone digits)
PREWARMED_PIPELINES = {}

async def prewarm_plivo_pipeline(phone: str, direction: str = "outbound", call_uuid: str = None) -> VoicePipeline:
    """
    Pre-warms Gemini Live session in the background as soon as the call connects/answers,
    generating the greeting while the WebSocket handshake completes.
    """
    norm_phone = normalize_phone(phone)
    key = call_uuid or norm_phone
    if key in PREWARMED_PIPELINES and PREWARMED_PIPELINES[key].active:
        logger.info(f"Pipeline already pre-warmed for key: {key}")
        return PREWARMED_PIPELINES[key]
        
    formatted_phone = "+91" + norm_phone if len(norm_phone) == 10 else ("+" + norm_phone if not phone.startswith("+") else phone)
    logger.info(f"⚡ Pre-warming Gemini Live pipeline in background for {formatted_phone} (Norm: {norm_phone}, Call UUID: {call_uuid}, Direction: {direction})...")
    pipeline = VoicePipeline(
        phone=formatted_phone,
        direction=direction,
        call_sid=call_uuid
    )
    if call_uuid:
        PREWARMED_PIPELINES[call_uuid] = pipeline
    if norm_phone:
        PREWARMED_PIPELINES[norm_phone] = pipeline
        
    asyncio.create_task(pipeline.start())
    return pipeline

async def handle_plivo_websocket(websocket: WebSocket):
    """
    Bidirectional streaming WebSocket handler for Plivo Audio Streams.
    
    Protocol:
      - Incoming:
          - 'start': Stream and call metadata (streamId, callId, from, to)
          - 'media': Base64 encoded audio packets (8kHz 16-bit linear PCM or mulaw)
          - 'stop': Stream termination
      - Outbound:
          - 'playAudio': Base64 encoded audio packets sent to Plivo
          - 'clearAudio': Clears buffered audio on Plivo when user interrupts (barge-in)
    """
    await websocket.accept()
    logger.info("Plivo WebSocket connection established.")
    
    # Read parameters passed in the WebSocket URL query string
    query_phone = websocket.query_params.get("phone")
    query_direction = websocket.query_params.get("direction", "inbound")
    
    stream_id = None
    call_uuid = None
    pipeline = None
    incoming_count = 0
    early_audio_buffer = []
    
    # Define callback that VoicePipeline uses to send audio back to Plivo
    outbound_audio_count = 0
    async def send_audio_callback(pcm_bytes: bytes):
        nonlocal stream_id, outbound_audio_count
        if not stream_id:
            early_audio_buffer.append(pcm_bytes)
            if len(early_audio_buffer) % 20 == 1:
                logger.info(f"📦 Audio buffered (no stream_id yet): {len(early_audio_buffer)} packets in early_audio_buffer")
            return
            
        try:
            if pcm_bytes == b"CLEAR_STREAM":
                clear_msg = {
                    "event": "clearAudio",
                    "streamId": stream_id
                }
                await websocket.send_text(json.dumps(clear_msg))
                logger.info(f"Sent clearAudio to Plivo for stream {stream_id} to flush playback buffer.")
                return
                
            pcm_base64 = base64.b64encode(pcm_bytes).decode("utf-8")
            play_msg = {
                "event": "playAudio",
                "streamId": stream_id,
                "media": {
                    "contentType": "audio/x-l16",
                    "sampleRate": 8000,
                    "payload": pcm_base64
                }
            }
            await websocket.send_text(json.dumps(play_msg))
            outbound_audio_count += 1
            if outbound_audio_count <= 5 or outbound_audio_count % 50 == 0:
                logger.info(f"🔊 Sent audio packet #{outbound_audio_count} to Plivo stream {stream_id}")
        except Exception as e:
            logger.error(f"Failed to send audio chunk to Plivo: {e}")

    try:
        while True:
            # Wait for message from Plivo (timeout after 60s of silence)
            try:
                message_text = await asyncio.wait_for(websocket.receive_text(), timeout=60.0)
            except asyncio.TimeoutError:
                logger.warning(f"No data received for 60s on stream {stream_id}. Closing connection.")
                break
                
            data = json.loads(message_text)
            event = data.get("event")
            
            if event != "media":
                logger.info(f"Received WebSocket event from Plivo: {event}. Raw payload: {data}")
            
            if event == "start":
                start_obj = data.get("start", {})
                stream_id = data.get("streamId") or start_obj.get("streamId") or data.get("stream_id")
                call_uuid = start_obj.get("callId") or start_obj.get("callUuid") or start_obj.get("call_uuid") or data.get("callUuid")
                logger.info(f"Plivo stream started with streamId: {stream_id}, callId: {call_uuid}")
                
                # Resolve customer phone:
                # In outbound calls, customer is 'to' or query_phone. In inbound calls, customer is 'from' or query_phone.
                if query_direction == "outbound":
                    caller_phone = query_phone or start_obj.get("to") or "+919999999999"
                else:
                    caller_phone = start_obj.get("from") or query_phone or "+919999999999"
                
                resolved_direction = query_direction
                norm_caller = normalize_phone(caller_phone)
                norm_query = normalize_phone(query_phone)
                
                # Check for an already pre-warmed pipeline for this call
                pipeline = (
                    (PREWARMED_PIPELINES.pop(call_uuid, None) if call_uuid else None) or 
                    (PREWARMED_PIPELINES.pop(norm_caller, None) if norm_caller else None) or 
                    (PREWARMED_PIPELINES.pop(norm_query, None) if norm_query else None)
                )
                
                if pipeline and pipeline.active:
                    logger.info(f"⚡ FAST-PATH: Binding to pre-warmed Gemini Live pipeline for {caller_phone} (Call UUID: {call_uuid}, Direction: {resolved_direction})")
                    pipeline.call_sid = call_uuid
                    pipeline.direction = resolved_direction
                    await pipeline.set_send_audio_callback(send_audio_callback)
                else:
                    logger.info(f"Standard path: Initializing new VoicePipeline for {caller_phone} (Direction: {resolved_direction})...")
                    pipeline = VoicePipeline(
                        phone=caller_phone,
                        direction=resolved_direction,
                        send_audio_callback=send_audio_callback,
                        call_sid=call_uuid
                    )
                    asyncio.create_task(pipeline.start())

                # Flush any early generated audio chunks immediately down the WebSocket
                if early_audio_buffer:
                    logger.info(f"⚡ Instant playback: Flushing {len(early_audio_buffer)} early-generated audio packets to Plivo stream {stream_id}")
                    for chunk in early_audio_buffer:
                        await send_audio_callback(chunk)
                    early_audio_buffer.clear()
                
            elif event == "media":
                incoming_count += 1
                media_payload = data.get("media", {}).get("payload")
                if incoming_count % 50 == 0:
                    logger.info(f"Received {incoming_count} media packets from Plivo (payload size: {len(media_payload) if media_payload else 0}).")
                if pipeline and media_payload:
                    pcm_bytes = base64.b64decode(media_payload)
                    await pipeline.handle_incoming_audio(pcm_bytes)
                    
            elif event == "stop":
                logger.info(f"Plivo stream stopped for streamId: {stream_id}")
                if pipeline and not getattr(pipeline, "call_sid", None) and call_uuid:
                    pipeline.call_sid = call_uuid
                break
                
    except WebSocketDisconnect:
        logger.info(f"Plivo WebSocket disconnected for streamId: {stream_id}")
    except Exception as e:
        logger.error(f"Error in Plivo WebSocket handler: {e}")
    finally:
        if pipeline:
            await pipeline.close()
            logger.info("Plivo VoicePipeline closed.")
