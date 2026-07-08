import os
import sys
import time
import subprocess
import asyncio
import logging
from typing import List, Optional

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import config
from core.pipeline import VoicePipeline

logger = logging.getLogger(__name__)

DEVICE_SERIAL = "10BF5P2AZF0010T"

def run_adb_command(args: List[str]) -> str:
    """Helper to run ADB commands targeting the specific device serial."""
    cmd = ["adb", "-s", DEVICE_SERIAL] + args
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, check=True, timeout=10)
        return result.stdout.strip()
    except subprocess.CalledProcessError as e:
        logger.error(f"ADB command failed: {cmd}. Error: {e.stderr}")
        return ""
    except subprocess.TimeoutExpired:
        logger.error(f"ADB command timed out: {cmd}")
        return ""

def get_android_call_state() -> int:
    """
    Returns the current telephony call state:
    0: Idle
    1: Ringing (Incoming)
    2: Off-hook (Active/Dialing)
    """
    output = run_adb_command(["shell", "dumpsys", "telephony.registry"])
    for line in output.splitlines():
        if "mCallState" in line:
            # Format is usually 'mCallState=0' or similar
            parts = line.split("=")
            if len(parts) > 1:
                try:
                    return int(parts[1].strip()[0]) # grab first character to avoid issues
                except ValueError:
                    pass
    return 0

def get_incoming_number() -> str:
    """Attempts to retrieve the incoming call phone number."""
    output = run_adb_command(["shell", "dumpsys", "telephony.registry"])
    for line in output.splitlines():
        if "mCallIncomingNumber" in line or "mIncomingCallNumber" in line:
            parts = line.split("=")
            if len(parts) > 1:
                return parts[1].strip()
    return ""

def trigger_dial(phone_number: str):
    """Triggers the phone dialer to call the specified number."""
    logger.info(f"Triggering outbound call via ADB to {phone_number}...")
    run_adb_command(["shell", "am", "start", "-a", "android.intent.action.CALL", "-d", f"tel:{phone_number}"])

def answer_call():
    """Answers an incoming call (simulating KEYCODE_CALL)."""
    logger.info("Answering call via ADB...")
    # Keyevent 5 is KEYCODE_CALL (answer)
    run_adb_command(["shell", "input", "keyevent", "5"])

def hangup_call():
    """Hangs up the current active call (simulating KEYCODE_ENDCALL)."""
    logger.info("Hanging up call via ADB...")
    # Keyevent 6 is KEYCODE_ENDCALL (hang up)
    run_adb_command(["shell", "input", "keyevent", "6"])


class LocalCallManager:
    def __init__(self, send_audio_callback):
        self.send_audio_callback = send_audio_callback
        self.active_pipeline: Optional[VoicePipeline] = None
        self.lead_queue: List[str] = []
        self.campaign_active = False
        self.inbound_active = True
        self._loop_task = None

    async def start_inbound_listener(self):
        """Starts monitoring call states to handle auto-answering and queueing."""
        logger.info("Starting local inbound call listener loop...")
        self._loop_task = asyncio.create_task(self._listener_loop())

    async def _listener_loop(self):
        while self.inbound_active:
            try:
                state = get_android_call_state()
                
                # State 1 is Ringing (incoming call)
                if state == 1:
                    incoming_num = get_incoming_number() or "Unknown Caller"
                    logger.info(f"Incoming call detected from: {incoming_num}")
                    
                    if self.active_pipeline:
                        # Agent is currently busy on a call
                        logger.info("Agent is busy. Adding incoming number to retry/outbound campaign queue...")
                        if incoming_num not in self.lead_queue and incoming_num != "Unknown Caller":
                            self.lead_queue.append(incoming_num)
                        # Optional: Send busy message or let carrier conditional forwarding handle it
                    else:
                        # Agent is idle, answer the call
                        logger.info("Agent is idle. Auto-answering call...")
                        answer_call()
                        
                        # Wait a bit for the connection to establish
                        await asyncio.sleep(2)
                        
                        # Start pipeline
                        self.active_pipeline = VoicePipeline(
                            phone=incoming_num,
                            send_audio_callback=self.send_audio_callback
                        )
                        await self.active_pipeline.start()
                        
                # Monitor active call end
                elif state == 0 and self.active_pipeline:
                    logger.info("Call disconnected. Cleaning up pipeline...")
                    await self.active_pipeline.close()
                    self.active_pipeline = None
                    
            except Exception as e:
                logger.error(f"Error in listener loop: {e}")
                
            await asyncio.sleep(1) # check call state every 1s

    async def run_outbound_campaign(self, leads: List[str], delay_between_calls: int = 10):
        """Runs an automated campaign dialing a list of leads one-by-one."""
        self.lead_queue.extend(leads)
        self.campaign_active = True
        logger.info(f"Outbound campaign started with {len(leads)} leads.")
        
        while self.campaign_active and self.lead_queue:
            # Check if phone is idle before dialing
            state = get_android_call_state()
            if state != 0:
                logger.info("Phone is busy. Waiting for it to become idle...")
                await asyncio.sleep(5)
                continue
                
            # Pop next lead
            lead = self.lead_queue.pop(0)
            logger.info(f"Next campaign lead: dialing {lead}...")
            
            trigger_dial(lead)
            
            # Wait for call to connect (up to 15s)
            connected = False
            for _ in range(15):
                await asyncio.sleep(1)
                if get_android_call_state() == 2:
                    connected = True
                    break
                    
            if not connected:
                logger.warning(f"Could not connect to {lead}. Moving to next lead.")
                continue
                
            logger.info(f"Call active with {lead}. Launching AI agent pipeline...")
            self.active_pipeline = VoicePipeline(
                phone=lead,
                send_audio_callback=self.send_audio_callback
            )
            await self.active_pipeline.start()
            
            # Keep monitoring call state until it returns to idle
            while get_android_call_state() == 2:
                await asyncio.sleep(1)
                
            logger.info(f"Call with {lead} ended. Cleaning up pipeline...")
            await self.active_pipeline.close()
            self.active_pipeline = None
            
            # Delay between calls to prevent spam flags
            logger.info(f"Waiting {delay_between_calls}s before dialing next lead...")
            await asyncio.sleep(delay_between_calls)
            
        self.campaign_active = False
        logger.info("Outbound campaign completed.")

    async def stop(self):
        self.inbound_active = False
        self.campaign_active = False
        if self._loop_task:
            self._loop_task.cancel()
        if self.active_pipeline:
            await self.active_pipeline.close()
            self.active_pipeline = None
