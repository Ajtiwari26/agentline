import os
import sys
import asyncio
import logging
import sounddevice as sd
from dotenv import load_dotenv

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import config
from bluetooth.call_manager import trigger_dial, get_android_call_state, hangup_call
from core.pipeline import VoicePipeline
from db.database import setup_indexes

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

load_dotenv()

async def main():
    if not config.validate_config():
        logger.error("Configuration validation failed. Exiting.")
        sys.exit(1)
        
    print("Configuring Database indexes...")
    try:
        setup_indexes()
    except Exception as e:
        logger.warning(f"Database setup failed: {e}. Continuing...")

    # Set up sound output stream (8000Hz mono 16-bit PCM)
    out_stream = sd.RawOutputStream(
        samplerate=8000,
        channels=1,
        dtype='int16'
    )
    out_stream.start()

    async def send_audio_callback(pcm_bytes: bytes):
        """Send generated agent speech audio to the phone via Bluetooth."""
        out_stream.write(pcm_bytes)

    target_phone = "9399250600"
    if len(sys.argv) > 1:
        target_phone = sys.argv[1].strip()
        
    print(f"\n[1/3] Triggering call to {target_phone} via USB ADB...")
    trigger_dial(target_phone)

    print("[2/3] Waiting for call to connect (up to 20 seconds)...")
    connected = False
    for i in range(20):
        await asyncio.sleep(1)
        state = get_android_call_state()
        print(f"  Checking call state... Current state: {state}")
        if state == 2:
            connected = True
            break
            
    if not connected:
        print("\n[ERROR] Call was not answered or failed to connect.")
        out_stream.stop()
        out_stream.close()
        return

    print("\n[3/3] Call Connected! Launching Voice Agent pipeline...")
    pipeline = VoicePipeline(phone=target_phone, send_audio_callback=send_audio_callback)
    
    # Input callback to capture audio from the phone microphone
    def audio_input_callback(indata, frames, time, status):
        if status:
            logger.warning(f"Audio Input Status Warning: {status}")
        asyncio.run_coroutine_threadsafe(
            pipeline.handle_incoming_audio(bytes(indata)),
            loop
        )

    in_stream = sd.RawInputStream(
        samplerate=8000,
        channels=1,
        dtype='int16',
        callback=audio_input_callback,
        blocksize=1600 # 200ms blocks
    )
    in_stream.start()

    global loop
    loop = asyncio.get_running_loop()
    await pipeline.start()

    print("\nConversation started. Speak to the agent. Press Ctrl+C to hang up.")
    try:
        # Loop while call remains active (state == 2)
        while get_android_call_state() == 2:
            await asyncio.sleep(1)
        print("\nCall disconnected by peer.")
    except KeyboardInterrupt:
        print("\nHanging up call programmatically...")
        hangup_call()
    finally:
        in_stream.stop()
        in_stream.close()
        out_stream.stop()
        out_stream.close()
        await pipeline.close()
        print("Pipeline shut down. Exiting.")

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\nExiting...")
