import os
import sys
import json
import base64
import asyncio
import logging
import websockets
import sounddevice as sd
import numpy as np

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

# URL of the deployed Render backend Exotel WebSocket route
WS_URL = "wss://agentline-backend.onrender.com/ws/exotel"

async def main():
    target_phone = "9399250600"
    direction = "inbound"
    
    if len(sys.argv) > 1:
        direction = sys.argv[1].strip().lower()
        if direction not in ["inbound", "outbound"]:
            direction = "inbound"
            
    if len(sys.argv) > 2:
        target_phone = sys.argv[2].strip()

    # Build the WebSocket query URL with phone and direction params
    websocket_url = f"{WS_URL}?phone={target_phone}&direction={direction}"
    
    # Setup Mac Speaker stream at 16000Hz (highly compatible with macOS CoreAudio)
    out_stream = sd.RawOutputStream(
        samplerate=16000,
        channels=1,
        dtype='int16'
    )
    out_stream.start()

    print(f"Connecting to deployed Render WebSocket: {websocket_url} ...")
    
    try:
        async with websockets.connect(websocket_url) as ws:
            print("Connected to Render WebSocket!")
            
            # Send Exotel Start Event to trigger VoicePipeline
            stream_sid = "mock_mac_stream_12345"
            start_msg = {
                "event": "start",
                "stream_sid": stream_sid,
                "start": {
                    "from": target_phone,
                    "callSid": "mock_mac_call_67890"
                }
            }
            await ws.send(json.dumps(start_msg))
            print("Sent start handshake. Session initialized.")
            
            # Microphone Input Callback: captures at 16kHz, downsamples to 8kHz, base64 encodes, and sends
            loop = asyncio.get_running_loop()
            
            def audio_input_callback(indata, frames, time, status):
                if status:
                    logger.warning(f"Microphone status warning: {status}")
                # Convert input 16kHz bytes back to 16-bit integers
                samples_16k = np.frombuffer(indata, dtype=np.int16)
                # Downsample 16kHz -> 8kHz by taking every second sample
                samples_8k = samples_16k[::2]
                pcm_8k_bytes = samples_8k.tobytes()
                
                # Base64 encode and format into Exotel media event
                payload = base64.b64encode(pcm_8k_bytes).decode("utf-8")
                media_msg = {
                    "event": "media",
                    "stream_sid": stream_sid,
                    "media": {
                        "payload": payload
                    }
                }
                
                asyncio.run_coroutine_threadsafe(
                    ws.send(json.dumps(media_msg)),
                    loop
                )

            # Mac Mic Input: 16000Hz mono 16-bit. 3200 frames = 200ms blocks
            in_stream = sd.RawInputStream(
                samplerate=16000,
                channels=1,
                dtype='int16',
                callback=audio_input_callback,
                blocksize=3200
            )
            in_stream.start()
            
            print("\n>>> Speak into your Mac microphone. Press Ctrl+C to stop. <<<\n")
            
            # Receive audio from WebSocket, upsample (8kHz -> 16kHz), and play back
            async for message in ws:
                data = json.loads(message)
                event = data.get("event")
                
                if event == "clear":
                    logger.info("Received CLEAR_STREAM event from server.")
                elif event == "media":
                    payload_b64 = data.get("media", {}).get("payload")
                    if payload_b64:
                        pcm_8k_bytes = base64.b64decode(payload_b64)
                        samples_8k = np.frombuffer(pcm_8k_bytes, dtype=np.int16)
                        # Upsample 8kHz -> 16kHz by repeating each sample twice
                        samples_16k = np.repeat(samples_8k, 2)
                        out_stream.write(samples_16k.tobytes())
                        
    except websockets.exceptions.ConnectionClosed:
        print("\nConnection closed by Render backend.")
    except KeyboardInterrupt:
        print("\nStopping local audio bridge...")
    finally:
        out_stream.stop()
        out_stream.close()
        print("Session ended.")

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\nExiting...")
