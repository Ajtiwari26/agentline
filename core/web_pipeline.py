"""
WebVoicePipeline — Gemini Live pipeline for the DeployMate website widget.

Differences from the Exotel VoicePipeline:
- Audio in is 16 kHz PCM16 straight from the browser (no 8 kHz resampling).
- Audio out is forwarded as raw 24 kHz PCM16 (the browser schedules playback).
- Echo is handled by the browser's echoCancellation, so no dB mic-gating here.
- Input/output transcription is enabled and streamed to the browser as JSON
  events so the widget can render a live transcript.
- Tools: save_lead + send_details_email (DeployMate-branded, see
  tools/website_tools.py). Leads land in the DeployMate site's MongoDB tagged
  "website inbound agent lead".
"""

import os
import sys
import json
import uuid
import asyncio
import logging
import time
from typing import Callable, Coroutine, Any

from google.genai import types
from contextlib import AsyncExitStack

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import config
from core.web_prompts import build_website_prompt
from tools.website_tools import (
    send_website_email,
    save_website_lead,
    attach_transcript_to_lead,
)

logger = logging.getLogger(__name__)

MAX_CALL_SECONDS = 360  # hard cap per demo call to protect the Vertex bill

WEB_TOOL_DECLARATIONS = [
    types.FunctionDeclaration(
        name="save_lead",
        description=(
            "Saves or updates the caller's details as a lead in DeployMate's CRM. "
            "Call this as soon as you learn ANY new detail (name, company, phone, requirement, interest). "
            "Calling it again updates the same lead with the new details."
        ),
        parameters=types.Schema(
            type="OBJECT",
            properties={
                "name": types.Schema(type="STRING", description="Caller's name if shared."),
                "email": types.Schema(type="STRING", description="Caller's email if shared and confirmed."),
                "phone": types.Schema(type="STRING", description="Caller's phone number if shared."),
                "company": types.Schema(type="STRING", description="Company/business name if shared."),
                "requirement": types.Schema(type="STRING", description="One-line English summary of what they need."),
                "interest_level": types.Schema(type="STRING", description="'hot', 'warm' or 'cold'."),
                "language": types.Schema(type="STRING", description="Language the caller is speaking (e.g. 'hindi', 'english')."),
            },
            required=["interest_level"],
        ),
    ),
    types.FunctionDeclaration(
        name="send_details_email",
        description=(
            "Sends the DeployMate services brief email to the caller. CRITICAL: only call AFTER the caller "
            "has verbally confirmed the complete email address via the email capture protocol."
        ),
        parameters=types.Schema(
            type="OBJECT",
            properties={
                "to_email": types.Schema(type="STRING", description="Confirmed recipient email address."),
                "name": types.Schema(type="STRING", description="Caller's name for the greeting."),
                "personal_note": types.Schema(
                    type="STRING",
                    description="2-4 warm sentences IN THE CALLER'S LANGUAGE summarizing the call and what DeployMate proposes for them.",
                ),
                "requirement": types.Schema(type="STRING", description="One-line English summary of their requirement."),
            },
            required=["to_email"],
        ),
    ),
]


class WebVoicePipeline:
    def __init__(self, send_event: Callable[[dict], Coroutine[Any, Any, None]]):
        """
        Args:
            send_event: async callback that delivers a JSON-serializable event
                        dict to the browser WebSocket.
        """
        self.send_event = send_event
        self.session_id = uuid.uuid4().hex[:16]
        self.system_prompt = build_website_prompt(getattr(config, "AGENT_NAME", "Kavya"))
        self.client, self.is_vertex = config.get_gemini_client()
        self.model_name = (
            "gemini-live-2.5-flash-native-audio" if self.is_vertex
            else "gemini-2.5-flash-native-audio-latest"
        )

        self.exit_stack = AsyncExitStack()
        self.session = None
        self.receiver_task = None
        self.active = True
        self.started_at = time.monotonic()
        self.transcript_log = []
        self.tool_call_counts = {}
        self.lead_saved = False
        # Partial transcription accumulators (flushed on turn boundaries)
        self._pending_user_text = ""
        self._pending_agent_text = ""

    async def start(self):
        logger.info(f"[web:{self.session_id}] starting Gemini Live web pipeline (model={self.model_name})")
        live_config = types.LiveConnectConfig(
            response_modalities=["AUDIO"],
            speech_config=types.SpeechConfig(
                voice_config=types.VoiceConfig(
                    prebuilt_voice_config=types.PrebuiltVoiceConfig(
                        voice_name=getattr(config, "GEMINI_LIVE_VOICE", "Aoede")
                    )
                )
            ),
            input_audio_transcription=types.AudioTranscriptionConfig(),
            output_audio_transcription=types.AudioTranscriptionConfig(),
            realtime_input_config=types.RealtimeInputConfig(
                automatic_activity_detection=types.AutomaticActivityDetection(
                    disabled=False,
                    prefix_padding_ms=100,
                    silence_duration_ms=600,
                )
            ),
            system_instruction=types.Content(
                parts=[types.Part.from_text(text=self.system_prompt)]
            ),
            tools=[types.Tool(function_declarations=WEB_TOOL_DECLARATIONS)],
        )

        try:
            self.session = await self.exit_stack.enter_async_context(
                self.client.aio.live.connect(model=self.model_name, config=live_config)
            )
            logger.info(f"[web:{self.session_id}] Gemini Live session connected")
            self.receiver_task = asyncio.create_task(self._receive_loop())

            # Make the agent speak first, like a receptionist picking up the phone.
            await self.session.send(
                input=types.LiveClientContent(
                    turns=[types.Content(
                        role="user",
                        parts=[types.Part.from_text(text=(
                            "A visitor just called DeployMate's website line and the call connected. "
                            "Greet them now IN HINDI exactly in this spirit, warm and short: "
                            "\"Namaste! DeployMate mein aapka swagat hai. Main Kavya hoon, aapki AI receptionist. "
                            "Bataiye, main aapki kaise madad kar sakti hoon?\""
                        ))]
                    )],
                    turn_complete=True,
                )
            )
            await self.send_event({"type": "ready"})
            return True
        except Exception as e:
            logger.error(f"[web:{self.session_id}] failed to connect to Gemini Live: {e}")
            self.active = False
            await self.send_event({"type": "error", "message": "Could not connect the AI line. Please try again."})
            return False

    def seconds_left(self) -> float:
        return MAX_CALL_SECONDS - (time.monotonic() - self.started_at)

    async def handle_incoming_audio(self, pcm_16k: bytes):
        """Browser sends 16 kHz mono PCM16 — forward straight to Gemini."""
        if not self.active or not self.session:
            return
        try:
            await self.session.send(
                input=types.LiveClientRealtimeInput(
                    media_chunks=[types.Blob(data=pcm_16k, mime_type="audio/pcm;rate=16000")]
                )
            )
        except Exception as e:
            logger.error(f"[web:{self.session_id}] error sending audio to Gemini: {e}")

    async def handle_incoming_text(self, text: str):
        """Optional text channel (used by automated tests and as an accessibility fallback)."""
        if not self.active or not self.session or not text.strip():
            return
        self.transcript_log.append({"sender": "user", "text": text.strip()})
        await self.session.send(
            input=types.LiveClientContent(
                turns=[types.Content(role="user", parts=[types.Part.from_text(text=text.strip())])],
                turn_complete=True,
            )
        )

    async def _flush_user_text(self):
        if self._pending_user_text.strip():
            self.transcript_log.append({"sender": "user", "text": self._pending_user_text.strip()})
            self._pending_user_text = ""

    async def _flush_agent_text(self):
        if self._pending_agent_text.strip():
            self.transcript_log.append({"sender": "assistant", "text": self._pending_agent_text.strip()})
            self._pending_agent_text = ""

    async def _receive_loop(self):
        import base64
        logger.info(f"[web:{self.session_id}] receiver loop started")
        try:
            while self.active:
                async for response in self.session.receive():
                    if not self.active:
                        break
                    try:
                        sc = response.server_content
                        if sc:
                            if sc.interrupted:
                                await self._flush_agent_text()
                                await self.send_event({"type": "interrupted"})
                                continue

                            if sc.input_transcription and sc.input_transcription.text:
                                self._pending_user_text += sc.input_transcription.text
                                await self.send_event({
                                    "type": "transcript", "role": "caller",
                                    "text": self._pending_user_text, "final": False,
                                })

                            if sc.output_transcription and sc.output_transcription.text:
                                # Agent started answering → the caller's turn is over.
                                if self._pending_user_text.strip():
                                    await self.send_event({
                                        "type": "transcript", "role": "caller",
                                        "text": self._pending_user_text, "final": True,
                                    })
                                    await self._flush_user_text()
                                self._pending_agent_text += sc.output_transcription.text
                                await self.send_event({
                                    "type": "transcript", "role": "agent",
                                    "text": self._pending_agent_text, "final": False,
                                })

                            if sc.model_turn and sc.model_turn.parts:
                                for part in sc.model_turn.parts:
                                    if part.inline_data and part.inline_data.data:
                                        await self.send_event({
                                            "type": "audio",
                                            "data": base64.b64encode(part.inline_data.data).decode("ascii"),
                                        })

                            if sc.turn_complete:
                                if self._pending_agent_text.strip():
                                    await self.send_event({
                                        "type": "transcript", "role": "agent",
                                        "text": self._pending_agent_text, "final": True,
                                    })
                                await self._flush_agent_text()
                                await self.send_event({"type": "turn_complete"})

                        if response.tool_call:
                            await self._handle_tool_calls(response.tool_call)

                    except Exception as e:
                        logger.error(f"[web:{self.session_id}] receiver payload error: {e}")

                await asyncio.sleep(0.05)
        except asyncio.CancelledError:
            pass
        except Exception as e:
            logger.error(f"[web:{self.session_id}] receiver loop error: {e}")
            if self.active:
                await self.send_event({"type": "error", "message": "The AI line dropped. Please call again."})
                self.active = False
        logger.info(f"[web:{self.session_id}] receiver loop ended")

    async def _handle_tool_calls(self, tool_call):
        function_responses = []
        for fc in tool_call.function_calls:
            fn_name = fc.name
            fn_args = dict(fc.args) if fc.args else {}
            self.transcript_log.append({"sender": "system", "text": f"Tool call: {fn_name}({fn_args})"})

            limit = 6 if fn_name == "save_lead" else 2
            self.tool_call_counts[fn_name] = self.tool_call_counts.get(fn_name, 0) + 1
            if self.tool_call_counts[fn_name] > limit:
                result = f"Tool '{fn_name}' call limit reached. Tell the caller the team will follow up manually."
                function_responses.append(types.FunctionResponse(name=fn_name, response={"result": result}))
                continue

            await self.send_event({"type": "tool", "name": fn_name, "status": "start"})

            if fn_name == "save_lead":
                self.lead_saved = True
                args = {
                    "name": fn_args.get("name", ""),
                    "email": fn_args.get("email", ""),
                    "phone": fn_args.get("phone", ""),
                    "company": fn_args.get("company", ""),
                    "requirement": fn_args.get("requirement", ""),
                    "interest_level": fn_args.get("interest_level", "warm"),
                    "language": fn_args.get("language", "hindi"),
                    "session_id": self.session_id,
                }
                asyncio.create_task(self._run_tool_bg(save_website_lead, args, fn_name))
                result = "Lead saved successfully."
            elif fn_name == "send_details_email":
                args = {
                    "to_email": fn_args.get("to_email", ""),
                    "name": fn_args.get("name", ""),
                    "personal_note": fn_args.get("personal_note", ""),
                    "requirement": fn_args.get("requirement", ""),
                }
                asyncio.create_task(self._run_tool_bg(send_website_email, args, fn_name))
                result = f"Email is being sent to {fn_args.get('to_email')}."
            else:
                result = f"Unknown tool: {fn_name}"

            self.transcript_log.append({"sender": "system", "text": f"Tool result: {result}"})
            function_responses.append(types.FunctionResponse(name=fn_name, response={"result": result}))

        try:
            await self.session.send(
                input=types.LiveClientToolResponse(function_responses=function_responses)
            )
        except Exception as e:
            logger.error(f"[web:{self.session_id}] error sending tool response: {e}")

    async def _run_tool_bg(self, handler, args: dict, fn_name: str):
        try:
            res = await asyncio.to_thread(handler, **args)
            logger.info(f"[web:{self.session_id}] background tool {fn_name} done: {res}")
            await self.send_event({"type": "tool", "name": fn_name, "status": "done"})
        except Exception as e:
            logger.error(f"[web:{self.session_id}] background tool {fn_name} failed: {e}")
            await self.send_event({"type": "tool", "name": fn_name, "status": "error"})
            # The tool already reported instant success to keep latency low, so
            # tell the model the truth and let it correct itself mid-call.
            if fn_name == "send_details_email" and self.active and self.session:
                try:
                    await self.session.send(
                        input=types.LiveClientContent(
                            turns=[types.Content(role="user", parts=[types.Part.from_text(text=(
                                "SYSTEM NOTE (not the caller speaking): the email you tried to send "
                                "actually FAILED to deliver. Briefly apologize to the caller and assure "
                                "them the DeployMate team will email the details manually within a few hours."
                            ))])],
                            turn_complete=True,
                        )
                    )
                except Exception:
                    pass

    async def close(self):
        if not self.active and self.session is None:
            return
        logger.info(f"[web:{self.session_id}] closing web pipeline")
        self.active = False
        if self.receiver_task:
            self.receiver_task.cancel()
            try:
                await self.receiver_task
            except asyncio.CancelledError:
                pass
        try:
            await self.exit_stack.aclose()
        except Exception as e:
            logger.error(f"[web:{self.session_id}] error closing exit stack: {e}")

        # Persist the conversation on the lead doc (creates one if the agent
        # never called save_lead, so no website call is ever lost).
        await self._flush_user_text()
        await self._flush_agent_text()
        transcript = [t for t in self.transcript_log if t.get("sender") in ("user", "assistant")]
        duration = int(time.monotonic() - self.started_at)
        if transcript:
            try:
                await asyncio.to_thread(
                    attach_transcript_to_lead, self.session_id, self.transcript_log, duration
                )
            except Exception as e:
                logger.error(f"[web:{self.session_id}] failed to persist transcript: {e}")
