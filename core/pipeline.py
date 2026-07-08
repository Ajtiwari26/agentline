import os
import asyncio
import logging
import base64
import array
from typing import Callable, Coroutine, Dict, Any, List

import sys
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from core.stt import SarvamSTTClient
from core.tts import get_sarvam_tts, pre_cache_welcome_message
from core.agent import GeminiAgent
from core.prompts import load_kb

logger = logging.getLogger(__name__)

class VoicePipeline:
    def __init__(self, phone: str, direction: str = "outbound", send_audio_callback: Callable[[bytes], Coroutine[Any, Any, None]] = None):
        """
        Voice Pipeline Orchestrator with full-duplex barge-in & direction handling.
        
        Args:
            phone: The phone number of the lead.
            direction: "inbound" (lead called us) or "outbound" (we called lead).
            send_audio_callback: Async callback that accepts 8kHz 16-bit PCM bytes to play or transmit.
        """
        self.phone = phone
        self.direction = direction
        self.send_audio_callback = send_audio_callback
        
        # Initialize Gemini Agent
        self.agent = GeminiAgent(phone)
        
        # Initialize STT Client
        self.stt_client = SarvamSTTClient(callback=self.on_transcript_received)
        
        self.audio_queue = asyncio.Queue()
        self.is_speaking = False
        self.interrupted = False
        self.welcome_message_sent = False
        
        # VAD threshold: RMS amplitude for active speech (8kHz 16-bit PCM)
        self.rms_threshold = 800.0
        
        self.process_queue_task = None
        self.active = True

    async def start(self):
        """Starts the STT connection and background processes."""
        logger.info(f"Starting Voice Pipeline for {self.phone} (Direction: {self.direction})...")
        
        # Connect STT WebSocket
        connected = await self.stt_client.connect()
        if not connected:
            logger.error("STT Client failed to connect. Voice pipeline might not transcribe.")
            
        # Start queue processor
        self.process_queue_task = asyncio.create_task(self._process_audio_queue())
        
        # Inbound vs Outbound welcome trigger logic
        if self.direction == "outbound":
            kb = load_kb()
            welcome_text = kb.get("conversation_stages", {}).get("greeting", {}).get("script", "Hey! Kaise ho?")
            asyncio.create_task(self.trigger_welcome_message(welcome_text))
        else:
            logger.info("Inbound call: Sitting silently waiting for caller's first speech greeting...")

    async def handle_incoming_audio(self, pcm_8k_bytes: bytes):
        """Receives 8kHz mono PCM bytes, checks for barge-in VAD, and queues it for STT."""
        if not self.active:
            return
            
        # Compute RMS to check for voice activity (barge-in)
        samples = array.array('h', pcm_8k_bytes)
        rms = 0.0
        if samples:
            sum_squares = sum(s * s for s in samples)
            rms = (sum_squares / len(samples)) ** 0.5

        # If agent is speaking and we detect user voice activity, trigger barge-in interruption
        if self.is_speaking and rms > self.rms_threshold:
            logger.info(f"[Barge-in] User voice detected (RMS: {rms:.1f} > threshold {self.rms_threshold}). Interrupting agent.")
            self.interrupted = True
            
            # Clear in-flight audio queue to discard old voice frames
            while not self.audio_queue.empty():
                try:
                    self.audio_queue.get_nowait()
                    self.audio_queue.task_done()
                except asyncio.QueueEmpty:
                    break
                    
        await self.audio_queue.put(pcm_8k_bytes)

    async def _process_audio_queue(self):
        """Continuously pops audio from the queue and sends to STT client."""
        while self.active:
            try:
                chunk = await self.audio_queue.get()
                await self.stt_client.send_audio_chunk(chunk)
                self.audio_queue.task_done()
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error in queue processor: {e}")
                await asyncio.sleep(0.1)

    async def on_transcript_received(self, text: str):
        """Triggered when Sarvam STT finalizes a transcript segment."""
        # Block transcription triggers only if we are currently active speaking and not interrupted
        if (self.is_speaking and not self.interrupted) or not self.active:
            return
            
        logger.info(f"Transcript received: '{text}'")
        self.is_speaking = True
        
        try:
            # 1. Get response from Gemini
            response_text = await self.agent.generate_response(text)
            
            # 2. Convert to Speech and Stream out
            await self.speak_response(response_text)
        except Exception as e:
            logger.error(f"Error processing transcript: {e}")
            self.is_speaking = False

    async def speak_response(self, text: str):
        """Synthesizes text to speech using Sarvam AI and plays/streams it back."""
        self.is_speaking = True
        self.interrupted = False
        logger.info(f"Synthesizing response: '{text}'")
        
        try:
            pcm_bytes = await get_sarvam_tts(text)
            if not pcm_bytes:
                logger.error("TTS returned empty audio.")
                return
                
            chunk_size = 3200
            sleep_time = 0.2
            
            for i in range(0, len(pcm_bytes), chunk_size):
                if not self.active or self.interrupted:
                    logger.info("Speech playback interrupted/stopped.")
                    break
                chunk = pcm_bytes[i:i+chunk_size]
                # Pad final chunk if needed
                if len(chunk) < chunk_size:
                    chunk = chunk + b"\x00" * (chunk_size - len(chunk))
                    
                await self.send_audio_callback(chunk)
                await asyncio.sleep(sleep_time)
                
        except Exception as e:
            logger.error(f"Error playing response: {e}")
        finally:
            self.is_speaking = False
            self.interrupted = False
            logger.info("Speech playback completed.")

    async def trigger_welcome_message(self, welcome_text: str):
        """Plays the initial welcome greeting."""
        if self.welcome_message_sent:
            return
        self.welcome_message_sent = True
        self.is_speaking = True
        
        logger.info("Triggering greeting welcome message...")
        await self.speak_response(welcome_text)

    async def close(self):
        """Cleans up pipeline connections and tasks."""
        logger.info("Closing Voice Pipeline...")
        self.active = False
        
        if self.process_queue_task:
            self.process_queue_task.cancel()
            
        await self.stt_client.close()
        
        # Save session logs to MongoDB
        try:
            from db.database import add_conversation
            history = self.agent.get_history()
            duration = 30
            
            if history:
                add_conversation(
                    call_id=f"call_{int(asyncio.get_event_loop().time())}",
                    phone=self.phone,
                    transcript=[{"sender": h["role"], "text": h["content"]} for h in history],
                    duration_seconds=duration,
                    mode="local",
                    direction=self.direction
                )
                logger.info("Conversation successfully logged to MongoDB.")
        except Exception as e:
            logger.error(f"Failed to log conversation to DB: {e}")
