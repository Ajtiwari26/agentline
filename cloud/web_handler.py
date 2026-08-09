"""
WebSocket handler for the DeployMate website inbound voice widget.

Protocol (all JSON text frames):
  browser → server:
    {"type": "start"}                      begin the call (agent greets first)
    {"type": "audio", "data": "<b64>"}     16 kHz mono PCM16 mic audio
    {"type": "text",  "text": "..."}       optional text turn (tests/fallback)
    {"type": "end"}                        hang up
  server → browser:
    {"type": "ready"}                                          Gemini connected
    {"type": "audio", "data": "<b64>"}                         24 kHz mono PCM16
    {"type": "transcript", "role": "agent"|"caller",
     "text": "...", "final": bool}                             live transcript
    {"type": "interrupted"}                                    flush playback
    {"type": "turn_complete"}
    {"type": "tool", "name": "...", "status": "start"|"done"|"error"}
    {"type": "timeout"}                                        max length hit
    {"type": "error", "message": "..."}
"""

import json
import base64
import asyncio
import logging

from fastapi import WebSocket, WebSocketDisconnect

import os
import sys
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from core.web_pipeline import WebVoicePipeline

logger = logging.getLogger(__name__)

IDLE_TIMEOUT_SECONDS = 90


async def handle_web_websocket(websocket: WebSocket):
    await websocket.accept()
    logger.info("Website voice WebSocket connected.")

    send_lock = asyncio.Lock()

    async def send_event(event: dict):
        try:
            async with send_lock:
                await websocket.send_text(json.dumps(event))
        except Exception:
            pass  # client already gone; close() cleanup handles the rest

    pipeline = WebVoicePipeline(send_event=send_event)
    watchdog_task = None

    async def watchdog():
        # Ends the call when the per-call budget runs out.
        try:
            await asyncio.sleep(max(1.0, pipeline.seconds_left()))
            if pipeline.active:
                await send_event({"type": "timeout"})
                pipeline.active = False
        except asyncio.CancelledError:
            pass

    try:
        while True:
            try:
                message_text = await asyncio.wait_for(
                    websocket.receive_text(), timeout=IDLE_TIMEOUT_SECONDS
                )
            except asyncio.TimeoutError:
                logger.info("Website voice socket idle — closing.")
                break

            try:
                data = json.loads(message_text)
            except (TypeError, ValueError):
                continue
            msg_type = data.get("type")

            if msg_type == "start":
                if pipeline.session is None:
                    ok = await pipeline.start()
                    if not ok:
                        break
                    watchdog_task = asyncio.create_task(watchdog())

            elif msg_type == "audio":
                payload = data.get("data")
                if payload and pipeline.active:
                    try:
                        pcm = base64.b64decode(payload)
                    except (TypeError, ValueError):
                        continue
                    await pipeline.handle_incoming_audio(pcm)

            elif msg_type == "text":
                await pipeline.handle_incoming_text(str(data.get("text", ""))[:2000])

            elif msg_type == "end":
                logger.info("Website caller hung up.")
                break

            if not pipeline.active:
                break

    except WebSocketDisconnect:
        logger.info("Website voice WebSocket disconnected.")
    except Exception as e:
        logger.error(f"Error in website voice handler: {e}")
    finally:
        if watchdog_task:
            watchdog_task.cancel()
        await pipeline.close()
        try:
            await websocket.close()
        except Exception:
            pass
        logger.info("Website voice session cleaned up.")
