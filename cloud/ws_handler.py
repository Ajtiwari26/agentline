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

async def handle_exotel_websocket(websocket: WebSocket):
    await websocket.accept()
    logger.info("Exotel WebSocket connection established.")
    
    # Read parameters passed in the WebSocket URL query string
    query_phone = websocket.query_params.get("phone")
    query_direction = websocket.query_params.get("direction", "inbound")
    
    stream_sid = None
    pipeline = None
    sequence_number = 1
    timestamp_ms = 0
    incoming_count = 0
    
    # Define the callback that the pipeline will use to send audio back to Exotel
    async def send_audio_callback(pcm_bytes: bytes):
        nonlocal sequence_number, timestamp_ms
        if not stream_sid:
            return
            
        try:
            if pcm_bytes == b"CLEAR_STREAM":
                clear_msg = {
                    "event": "clear",
                    "stream_sid": stream_sid
                }
                await websocket.send_text(json.dumps(clear_msg))
                logger.info(f"Sent clear event to Exotel for stream {stream_sid} to flush playback buffer.")
                return
                
            pcm_base64 = base64.b64encode(pcm_bytes).decode("utf-8")
            media_msg = {
                "event": "media",
                "sequence_number": str(sequence_number),
                "stream_sid": stream_sid,
                "media": {
                    "chunk": str(sequence_number),
                    "timestamp": str(timestamp_ms),
                    "payload": pcm_base64
                }
            }
            await websocket.send_text(json.dumps(media_msg))
            sequence_number += 1
            timestamp_ms += 20 # 20ms increments
        except Exception as e:
            logger.error(f"Failed to send audio chunk to Exotel: {e}")

    try:
        while True:
            # Wait for message from Exotel
            message_text = await websocket.receive_text()
            data = json.loads(message_text)
            event = data.get("event")
            logger.info(f"Received WebSocket event from Exotel: {event}. Raw payload: {data}")
            
            if event == "start":
                stream_sid = data.get("stream_sid") or data.get("streamSid")
                logger.info(f"Stream started with SID: {stream_sid}")
                
                # Fetch phone number directly from start payload or query string
                caller_phone = (
                    data.get("start", {}).get("from") or 
                    query_phone or 
                    data.get("start", {}).get("customParameters", {}).get("phone") or 
                    "+919999999999"
                )
                logger.info(f"Resolved caller phone number: {caller_phone}")
                
                # Force direction="outbound" to play welcome greeting immediately
                pipeline = VoicePipeline(phone=caller_phone, direction="outbound", send_audio_callback=send_audio_callback)
                # Run the pipeline startup in a background task so we don't block the WebSocket loop
                asyncio.create_task(pipeline.start())
                
            elif event == "media":
                incoming_count += 1
                media_payload = data.get("media", {}).get("payload")
                if incoming_count % 50 == 0:
                    logger.info(f"Received {incoming_count} media packets from Exotel (payload size: {len(media_payload) if media_payload else 0}).")
                if pipeline and media_payload:
                    pcm_bytes = base64.b64decode(media_payload)
                    # Feed audio bytes to the pipeline
                    await pipeline.handle_incoming_audio(pcm_bytes)
                    
            elif event == "stop":
                logger.info(f"Stream stopped for SID: {stream_sid}")
                break
                
    except WebSocketDisconnect:
        logger.info(f"WebSocket disconnected for SID: {stream_sid}")
    except Exception as e:
        logger.error(f"Error in Exotel WebSocket handler: {e}")
    finally:
        if pipeline:
            await pipeline.close()
            logger.info("Pipeline closed.")
