import json
import base64
import asyncio
import logging
import struct
import websockets
import config

logger = logging.getLogger(__name__)

def resample_8k_to_16k(audio_bytes: bytes) -> bytes:
    """Resamples 8kHz 16-bit PCM mono audio to 16kHz by duplicating samples."""
    n = len(audio_bytes) // 2
    if n == 0:
        return b""
    samples = struct.unpack(f"<{n}h", audio_bytes)
    resampled = []
    for i in range(n - 1):
        s0 = samples[i]
        s1 = samples[i+1]
        s_mid = (s0 + s1) // 2
        resampled.extend((s0, s_mid))
    if n > 0:
        resampled.extend((samples[-1], samples[-1]))
    return struct.pack(f"<{len(resampled)}h", *resampled)

class SarvamSTTClient:
    def __init__(self, callback):
        self.callback = callback  # Called when a transcript segment is finalized
        self.websocket = None
        self.headers = {
            "api-subscription-key": config.SARVAM_API_KEY
        }
        self.uri = "wss://api.sarvam.ai/speech-to-text/ws?language-code=hi-IN&model=saaras:v3"
        self.listener_task = None

    async def connect(self):
        logger.info("Connecting to Sarvam STT WebSocket...")
        try:
            from websockets.legacy.client import connect
            self.websocket = await connect(self.uri, extra_headers=self.headers)
            # Send initial config frame
            config_frame = {
                "audio": {
                    "data": "data",
                    "sample_rate": 16000,
                    "encoding": "audio/wav"
                }
            }
            await self.websocket.send(json.dumps(config_frame))
            logger.info("Sarvam STT connection configured.")
            self.listener_task = asyncio.create_task(self._listen_loop())
            return True
        except Exception as e:
            logger.error(f"Failed to connect to Sarvam STT: {e}")
            return False

    async def send_audio_chunk(self, pcm_8k_bytes: bytes):
        """Sends raw 8kHz PCM bytes, resampling them to 16kHz for Sarvam."""
        if not self.websocket or not self.websocket.open:
            return
        try:
            pcm_16k = resample_8k_to_16k(pcm_8k_bytes)
            base64_audio = base64.b64encode(pcm_16k).decode("utf-8")
            audio_message = {
                "audio": {
                    "data": base64_audio,
                    "encoding": "audio/wav",
                    "sample_rate": 16000
                }
            }
            await self.websocket.send(json.dumps(audio_message))
        except Exception as e:
            logger.error(f"Error sending audio chunk to Sarvam STT: {e}")

    async def _listen_loop(self):
        logger.info("Sarvam STT listener loop started.")
        while True:
            try:
                if not self.websocket or not self.websocket.open:
                    await asyncio.sleep(0.1)
                    continue
                response = await self.websocket.recv()
                data = json.loads(response)
                
                # Check for transcript data
                if data.get("type") == "data" and "data" in data:
                    transcript = data["data"].get("transcript", "").strip()
                    if transcript:
                        logger.info(f"STT Final Transcript: {transcript}")
                        if asyncio.iscoroutinefunction(self.callback):
                            await self.callback(transcript)
                        else:
                            self.callback(transcript)
            except websockets.exceptions.ConnectionClosed:
                logger.warning("Sarvam STT connection closed.")
                break
            except Exception as e:
                logger.error(f"Error in STT listener loop: {e}")
                await asyncio.sleep(0.1)

    async def close(self):
        if self.listener_task:
            self.listener_task.cancel()
        if self.websocket:
            await self.websocket.close()
            logger.info("Sarvam STT connection closed.")
