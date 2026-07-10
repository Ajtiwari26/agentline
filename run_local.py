import os
import sys
import asyncio
import logging
import csv
import sounddevice as sd
from dotenv import load_dotenv

sys.path.append(os.path.dirname(os.path.abspath(__file__)))
import config
from bluetooth.call_manager import LocalCallManager, get_android_call_state
from db.database import setup_indexes

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

load_dotenv()

async def main():
    if not config.validate_config():
        sys.exit(1)
        
    print("Connecting to MongoDB...")
    try:
        setup_indexes()
        print("MongoDB indexes configured successfully.")
    except Exception as e:
        print(f"Warning: MongoDB connection failed: {e}")
        print("Continuing anyway...")

    # Configure audio stream
    # 8000Hz, 1 channel (mono), 16-bit signed integer PCM
    out_stream = sd.RawOutputStream(
        samplerate=8000,
        channels=1,
        dtype='int16'
    )
    out_stream.start()
    
    async def send_audio_to_headset(pcm_bytes: bytes):
        """Callback to write outgoing agent speech to the Bluetooth output."""
        out_stream.write(pcm_bytes)

    # Initialize Local Call Manager
    manager = LocalCallManager(send_audio_callback=send_audio_to_headset)

    # Input callback for sounddevice (captures Bluetooth microphone)
    def audio_input_callback(indata, frames, time, status):
        if status:
            logger.warning(f"Sounddevice input warning: {status}")
        # Send raw PCM bytes to pipeline if call is active
        if manager.active_pipeline:
            asyncio.run_coroutine_threadsafe(
                manager.active_pipeline.handle_incoming_audio(bytes(indata)),
                loop
            )

    # Start input stream
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

    print("\n==============================================")
    print("      AGENTLINE — LOCAL VOICE MANAGER          ")
    print("==============================================")
    print("Target Phone Device: 10BF5P2AZF0010T (via USB)")
    print("Sound Output: Bluetooth Headset (Default Out)")
    print("Sound Input: Bluetooth Mic (Default In)")
    print("==============================================")
    print("Select running mode:")
    print("1) Inbound Auto-Answer Mode (Listen for incoming calls)")
    print("2) Outbound Campaign Mode (Load CSV list and call leads)")
    
    choice = input("\nEnter choice (1 or 2): ").strip()
    
    if choice == "1":
        print("\nStarting Inbound Auto-Answer listener...")
        print("Monitoring phone call events. Press Ctrl+C to exit.\n")
        await manager.start_inbound_listener()
        try:
            while True:
                await asyncio.sleep(1)
        except KeyboardInterrupt:
            pass
            
    elif choice == "2":
        default_csv = "leads_bhopal.csv" if getattr(config, "AGENT_MODE", "portfolio") == "portfolio" else "leads.csv"
        csv_path = input(f"Enter path to leads CSV file (default: {default_csv}): ").strip() or default_csv
        if not os.path.exists(csv_path):
            # Create a sample leads.csv if missing
            print(f"Creating sample file '{csv_path}'...")
            with open(csv_path, "w", newline="") as f:
                writer = csv.writer(f)
                writer.writerow(["phone", "name"])
                writer.writerow(["+919999999999", "Test Lead"])
                
        leads = []
        with open(csv_path, "r") as f:
            reader = csv.DictReader(f)
            for row in reader:
                if row.get("phone"):
                    leads.append(row["phone"].strip())
                    
        print(f"\nLoaded {len(leads)} leads from {csv_path}.")
        print("Starting Outbound Campaign in 3 seconds. Press Ctrl+C to cancel...")
        await asyncio.sleep(3)
        
        # Start call state listener in background so it can answer/cleanup too
        await manager.start_inbound_listener()
        
        # Run campaign
        await manager.run_outbound_campaign(leads, delay_between_calls=12)
        
    else:
        print("Invalid choice. Exiting.")
        
    # Cleanup
    in_stream.stop()
    in_stream.close()
    out_stream.stop()
    out_stream.close()
    await manager.stop()
    print("\nLocal Voice Manager stopped.")

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\nExiting...")
