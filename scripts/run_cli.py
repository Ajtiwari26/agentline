import os
import sys
import asyncio
import logging
import sounddevice as sd
import numpy as np
from dotenv import load_dotenv

# Ensure import paths work
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import config
from core.pipeline import VoicePipeline
from db.database import setup_indexes

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

# Load local .env if available
load_dotenv()

async def main():
    # Validate keys
    if not config.validate_config():
        logger.error("Missing configuration. Please check your .env file.")
        sys.exit(1)
        
    print("Initializing Database...")
    try:
        setup_indexes()
        print("Database indexes configured.")
    except Exception as e:
        print(f"Warning: Could not connect to MongoDB or setup indexes: {e}")
        print("Continuing in mock-db mode.")

    # Phone placeholder
    phone = "+919999999999"
    
    # Setup playback stream
    print("Initializing sound output stream...")
    # 8000Hz, 1 channel (mono), 16-bit signed integer PCM
    out_stream = sd.RawOutputStream(
        samplerate=8000,
        channels=1,
        dtype='int16'
    )
    out_stream.start()
    
    async def send_audio(pcm_bytes: bytes):
        """Callback to write outgoing agent speech to the speaker."""
        # Non-blocking write to speaker stream
        out_stream.write(pcm_bytes)
        
    # Initialize pipeline
    pipeline = VoicePipeline(phone=phone, send_audio_callback=send_audio)
    
    # Input callback for sounddevice
    def audio_input_callback(indata, frames, time, status):
        if status:
            logger.warning(f"Sounddevice status: {status}")
        # indata is raw bytes of PCM16 audio
        # Run in executor because callback is called in a separate OS thread
        asyncio.run_coroutine_threadsafe(
            pipeline.handle_incoming_audio(bytes(indata)),
            loop
        )

    # Start input stream
    print("Initializing sound input stream (Microphone)...")
    in_stream = sd.RawInputStream(
        samplerate=8000,
        channels=1,
        dtype='int16',
        callback=audio_input_callback,
        blocksize=1600 # 200ms blocks
    )
    
    # Get active event loop to schedule callbacks
    global loop
    loop = asyncio.get_running_loop()
    
    print("\n--- VOICE BOT LOCAL TEST ---")
    print("Starting voice agent pipeline. The agent will speak a welcome message first.")
    print("Speak into your microphone. Press Ctrl+C to exit.\n")
    
    await pipeline.start()
    in_stream.start()
    
    try:
        while True:
            await asyncio.sleep(1)
    except KeyboardInterrupt:
        print("\nExiting voice test...")
    finally:
        in_stream.stop()
        in_stream.close()
        out_stream.stop()
        out_stream.close()
        await pipeline.close()
        print("Session cleaned up.")

if __name__ == "__main__":
    asyncio.run(main())
