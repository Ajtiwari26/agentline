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
    
    stream_sid = None
    pipeline = None
    sequence_number = 1
    timestamp_ms = 0
    
    # Define the callback that the pipeline will use to send audio back to Exotel
    async def send_audio_callback(pcm_bytes: bytes):
        nonlocal sequence_number, timestamp_ms
        if not stream_sid:
            return
            
        try:
            pcm_base64 = base64.b64encode(pcm_bytes).decode("utf-8")
            media_msg = {
                "event": "media",
                "sequence_number": str(sequence_number),
                "stream_sid": stream_sid,
                "media": {
                    "chunk": sequence_number,
                    "timestamp": str(timestamp_ms),
                    "payload": pcm_base64
                }
            }
            await websocket.send_text(json.dumps(media_msg))
            sequence_number += 1
            timestamp_ms += 200 # 200ms increments
        except Exception as e:
            logger.error(f"Failed to send audio chunk to Exotel: {e}")

    try:
        while True:
            # Wait for message from Exotel
            message_text = await websocket.receive_text()
            data = json.loads(message_text)
            event = data.get("event")
            
            if event == "start":
                stream_sid = data.get("stream_sid") or data.get("streamSid")
                logger.info(f"Stream started with SID: {stream_sid}")
                
                # Fetch phone number if present in custom params, or fallback
                # Inbound calls might contain phone info in start parameters
                caller_phone = data.get("start", {}).get("customParameters", {}).get("phone", "+919999999999")
                
                # Create and start the pipeline
                pipeline = VoicePipeline(phone=caller_phone, send_audio_callback=send_audio_callback)
                await pipeline.start()
                
            elif event == "media":
                media_payload = data.get("media", {}).get("payload")
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
