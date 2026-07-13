import os
import asyncio
import logging
import struct
import array
from typing import Callable, Coroutine, Dict, Any, List

from google import genai
from google.genai import types

import sys
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import config
from core.prompts import build_system_prompt, load_kb
from tools.email_tool import send_template_email
from tools.callback_tool import schedule_manager_callback
from tools.lead_tool import update_lead_status
from tools.product_tool import get_product_details

from contextlib import AsyncExitStack

logger = logging.getLogger(__name__)

# Tool execution map — the Live API sends function_call messages that we must handle manually
TOOL_HANDLERS = {
    "send_email": lambda args: send_template_email(
        phone=args.get("_phone", "unknown"),
        to_email=args.get("to_email", ""),
        template_name=args.get("template_name", "syllabus")
    ),
    "schedule_callback": lambda args: schedule_manager_callback(
        phone=args.get("_phone", "unknown"),
        time_str=args.get("time_str", ""),
        reason=args.get("reason", ""),
        name=args.get("name", ""),
        remarks=args.get("remarks", ""),
        doubts=args.get("doubts", ""),
        times_called=args.get("times_called", "")
    ),
    "log_lead_interest": lambda args: update_lead_status(
        phone=args.get("_phone", "unknown"),
        interest_level=args.get("interest_level", "warm"),
        notes=args.get("notes", ""),
        name=args.get("name", "")
    ),
    "query_product_info": lambda args: get_product_details(
        query=args.get("query", "")
    ),
}

# Tool declarations for Gemini Live API config
TOOL_DECLARATIONS = [
    types.FunctionDeclaration(
        name="send_email",
        description="Sends a template-based email to the user (e.g. syllabus, pricing, course brochures).",
        parameters=types.Schema(
            type="OBJECT",
            properties={
                "to_email": types.Schema(type="STRING", description="The recipient email address."),
                "template_name": types.Schema(type="STRING", description="The name of the template ('syllabus' or 'pricing'). Defaults to 'syllabus'."),
            },
            required=["to_email"],
        ),
    ),
    types.FunctionDeclaration(
        name="schedule_callback",
        description="Schedules a callback for the human manager to call the lead back later. Use this if the lead asks for a call tomorrow, or next morning, or has query about pricing/payment.",
        parameters=types.Schema(
            type="OBJECT",
            properties={
                "time_str": types.Schema(type="STRING", description="The requested callback time ('morning', 'afternoon', 'tomorrow', or specific hour like '11:00 AM')."),
                "reason": types.Schema(type="STRING", description="The reason for scheduling the callback (e.g. 'payment discussion', 'detailed syllabus review')."),
                "name": types.Schema(type="STRING", description="The lead's name if they shared it."),
                "remarks": types.Schema(type="STRING", description="Any specific notes or details about the call/request."),
                "doubts": types.Schema(type="STRING", description="Brief summary of the doubts, queries, or objections the lead raised during the call."),
                "times_called": types.Schema(type="STRING", description="Number of times called if known (e.g., 'first', 'second')."),
            },
            required=["time_str", "reason"],
        ),
    ),
    types.FunctionDeclaration(
        name="log_lead_interest",
        description="Updates the lead's status (hot, warm, cold) and records conversation notes or objections in the database. Call this whenever you understand the user's name, interest level, or specific requirements.",
        parameters=types.Schema(
            type="OBJECT",
            properties={
                "interest_level": types.Schema(type="STRING", description="The user's interest level ('hot', 'warm', 'cold')."),
                "notes": types.Schema(type="STRING", description="Concise summary of what they want, study, work, or their objection."),
                "name": types.Schema(type="STRING", description="The user's name if they shared it. Optional."),
            },
            required=["interest_level", "notes"],
        ),
    ),
    types.FunctionDeclaration(
        name="query_product_info",
        description="Queries the course catalog, pricing details, GPU requirements, or FAQ for relevant answers. Use this to get accurate details before answering fees or hardware questions.",
        parameters=types.Schema(
            type="OBJECT",
            properties={
                "query": types.Schema(type="STRING", description="What the customer is asking (e.g., 'fees', 'graphics card requirements', 'beginner difficulty')."),
            },
            required=["query"],
        ),
    ),
]


def resample_8k_to_16k(pcm_8k: bytes) -> bytes:
    """Upsample 8kHz 16-bit PCM to 16kHz by linear interpolation."""
    samples = array.array('h', pcm_8k)
    out = array.array('h')
    for i in range(len(samples)):
        out.append(samples[i])
        # Interpolate between current and next sample
        if i + 1 < len(samples):
            mid = (samples[i] + samples[i + 1]) // 2
            out.append(mid)
        else:
            out.append(samples[i])
    return out.tobytes()


def resample_24k_to_8k(pcm_24k: bytes) -> bytes:
    """Downsample 24kHz 16-bit PCM to 8kHz by taking every 3rd sample."""
    samples = array.array('h', pcm_24k)
    out = array.array('h')
    for i in range(0, len(samples), 3):
        out.append(samples[i])
    return out.tobytes()


class VoicePipeline:
    def __init__(self, phone: str, direction: str = "outbound", send_audio_callback: Callable[[bytes], Coroutine[Any, Any, None]] = None, call_sid: str = None):
        """
        Voice Pipeline using Gemini Live API for real-time audio-to-audio conversation.
        
        Args:
            phone: The phone number of the lead.
            direction: "inbound" or "outbound".
            send_audio_callback: Async callback that accepts 8kHz 16-bit PCM bytes to play or transmit.
            call_sid: The Exotel Call Sid for call tracking/recording.
        """
        self.phone = phone
        self.direction = direction
        self.send_audio_callback = send_audio_callback
        self.call_sid = call_sid
        
        # Fetch lead details from database if available
        lead_info = None
        try:
            from db.database import get_lead
            lead_info = get_lead(phone)
            logger.info(f"Loaded lead context from DB: {lead_info}")
        except Exception as e:
            logger.error(f"Failed to load lead context from DB: {e}")
            
        # Build system prompt from knowledge base, lead context, and call direction
        self.system_prompt = build_system_prompt(lead_info, direction=self.direction)
        
        # Initialize the Gemini client (Vertex AI with service account)
        sa_key_path = os.getenv("GOOGLE_APPLICATION_CREDENTIALS", "")
        if sa_key_path and os.path.exists(sa_key_path):
            logger.info(f"Initializing Gemini Live client with Vertex AI using Service Account: {sa_key_path}")
            from google.oauth2 import service_account
            scopes = ["https://www.googleapis.com/auth/cloud-platform"]
            credentials = service_account.Credentials.from_service_account_file(sa_key_path, scopes=scopes)
            self.client = genai.Client(
                vertexai=True,
                project=os.getenv("GCP_PROJECT", "igsl-67e70"),
                location="us-central1",
                credentials=credentials
            )
        else:
            import config
            logger.info("Initializing Gemini Live client with AI Studio API Key")
            self.client = genai.Client(api_key=config.GEMINI_API_KEY)
        
        # Determine the model name dynamically (Vertex AI vs AI Studio Live API)
        is_vertex = sa_key_path and os.path.exists(sa_key_path)
        self.model_name = "gemini-live-2.5-flash-native-audio" if is_vertex else "gemini-2.0-flash-exp"
        self.summary_model_name = "gemini-2.5-flash" if is_vertex else "gemini-1.5-flash"
        logger.info(f"Using Gemini Live model: {self.model_name}, Summary model: {self.summary_model_name}")
        
        # Interruption and Noise Gate states
        self.interrupted = False
        self.gate_open = False
        self.gate_hold_counter = 0
        self.gate_hold_limit = 12  # Hold for 12 chunks (12 * 20ms = 240ms)
        self.open_threshold_db = -55.0   # Lowered: phone audio is heavily compressed/attenuated
        self.close_threshold_db = -60.0
        
        # Echo Prevention: Mic Gate state
        # When the agent is speaking, we mute incoming audio to prevent echo.
        # Only audio louder than barge_in_threshold_db breaks through (real human interruption).
        self.is_speaking = False
        self.barge_in_threshold_db = -40.0  # Lowered: phone audio is much quieter than direct mic
        self.audio_packet_count = 0  # Counter for periodic dB diagnostic logging
        
        self.exit_stack = AsyncExitStack()
        self.session = None  # Gemini Live session handle
        self.receiver_task = None
        self.active = True
        self.welcome_sent = False
        self.transcript_log = []  # For MongoDB logging
        self.tool_call_counts = {}  # Track per-tool call count to prevent infinite retry loops

    async def start(self):
        """Connects to Gemini Live API and starts audio streaming."""
        logger.info(f"Starting Gemini Live Voice Pipeline for {self.phone} (Direction: {self.direction})...")
        
        # Load welcome text based on call direction
        welcome_text = None
        if self.direction == "outbound":
            kb = load_kb()
            welcome_text = kb.get("conversation_stages", {}).get("greeting", {}).get("script", "Hey! Kaise ho?")
        elif self.direction == "inbound":
            # For inbound calls, use a receptive welcome greeting
            agent_mode = getattr(config, "AGENT_MODE", "portfolio")
            if agent_mode == "portfolio":
                welcome_text = "Hey! Nukkad Tech Solutions mein aapka swagat hai. Main Ajay hoon. Bataiye, kaise madad kar sakta hoon?"
            else:
                welcome_text = "Hey! CourseWallah mein welcome hai yaar. Main Ajay hoon. Bolo, kya jaanna hai?"
        
        # Configure the Gemini Live session
        live_config = types.LiveConnectConfig(
            response_modalities=["AUDIO"],
            speech_config=types.SpeechConfig(
                voice_config=types.VoiceConfig(
                    prebuilt_voice_config=types.PrebuiltVoiceConfig(voice_name=getattr(config, "GEMINI_LIVE_VOICE", "Charon"))
                )
            ),
            # VAD tuning to reduce echo-triggered self-interruptions
            realtime_input_config=types.RealtimeInputConfig(
                automatic_activity_detection=types.AutomaticActivityDetection(
                    disabled=False,
                    start_of_speech_sensitivity=types.StartSensitivity.START_SENSITIVITY_LOW,
                    end_of_speech_sensitivity=types.EndSensitivity.END_SENSITIVITY_LOW,
                    prefix_padding_ms=200,   # Ignore first 200ms of audio onset (catches most echo)
                    silence_duration_ms=500,  # Require 500ms silence to end a turn
                )
            ),
            system_instruction=types.Content(
                parts=[types.Part.from_text(text=self.system_prompt)]
            ),
            tools=[types.Tool(function_declarations=TOOL_DECLARATIONS)],
        )
        
        try:
            # Connect to the Gemini Live WebSocket using ExitStack
            self.session = await self.exit_stack.enter_async_context(
                self.client.aio.live.connect(
                    model=self.model_name,
                    config=live_config
                )
            )
            logger.info(f"Gemini Live session ({self.model_name}) connected successfully!")
            
            # Start the background receiver task (listens for audio output and tool calls from Gemini)
            self.receiver_task = asyncio.create_task(self._receive_loop())
            
            # Send the welcome message to trigger Gemini to speak first
            if welcome_text:
                direction_context = "You just called this person." if self.direction == "outbound" else "This person just called you."
                logger.info(f"Sending {self.direction} welcome prompt to Gemini Live: '{welcome_text}'")
                self.transcript_log.append({"sender": "assistant", "text": welcome_text})
                await self.session.send(
                    input=types.LiveClientContent(
                        turns=[types.Content(
                            role="user",
                            parts=[types.Part.from_text(
                                text=f"{direction_context} Start the conversation by saying exactly this greeting (adapt naturally but keep the essence): {welcome_text}"
                            )]
                        )],
                        turn_complete=True
                    )
                )
                self.welcome_sent = True
                
        except Exception as e:
            logger.error(f"Failed to connect to Gemini Live API: {e}")
            self.active = False

    async def handle_incoming_audio(self, pcm_8k_bytes: bytes):
        """Receives 8kHz PCM from Exotel, applies smart mic gate + noise filtering, resamples, and sends to Gemini Live."""
        if not self.active or not self.session:
            return
            
        # Calculate decibel level of incoming 8kHz PCM (16-bit)
        import array
        import math
        samples = array.array('h', pcm_8k_bytes)
        db = -100.0
        if len(samples) > 0:
            sum_squares = sum(float(s) * s for s in samples)
            rms = math.sqrt(sum_squares / len(samples))
            db = 20 * math.log10(rms / 32768.0) if rms > 0 else -100.0
        
        # ── DIAGNOSTIC: Log dB levels every 50 packets so we can calibrate thresholds ──
        self.audio_packet_count += 1
        if self.audio_packet_count % 50 == 0:
            gate_status = "SPEAKING_GATE" if self.is_speaking else ("LISTENING_OPEN" if self.gate_open else "LISTENING_GATED")
            logger.info(f"Audio dB: {db:.1f} | State: {gate_status} | is_speaking={self.is_speaking} | Pkt#{self.audio_packet_count}")
        
        # ── SMART MIC GATE (Echo Prevention) ──
        # While the agent is speaking, the phone mic picks up the agent's own voice
        # and Exotel sends it back to us. We MUST drop this echoed audio to prevent
        # Gemini from thinking the user is talking and interrupting itself.
        # 
        # However, we still allow genuinely LOUD audio through (a real human interruption)
        # so the user can still barge-in by speaking over the agent.
        if self.is_speaking:
            if db < self.barge_in_threshold_db:
                # Audio is too quiet — likely echo from the agent's own voice. Drop it.
                return
            else:
                # Audio is loud enough to be a real human interruption. Let it through.
                logger.info(f"Barge-in detected while agent speaking (dB: {db:.1f}). Allowing audio through.")
        
        # ── NOISE GATE (Background Noise Filtering) ──
        # When the agent is NOT speaking (listening mode), apply noise gate
        # to filter low-level background noise that could trigger Gemini's VAD.
        if not self.is_speaking:
            if db >= self.open_threshold_db:
                self.gate_open = True
                self.gate_hold_counter = self.gate_hold_limit
            else:
                if self.gate_open:
                    self.gate_hold_counter -= 1
                    if self.gate_hold_counter <= 0:
                        self.gate_open = False
            
            if not self.gate_open:
                return
            
        try:
            # Resample 8kHz → 16kHz for Gemini Live input
            pcm_16k = resample_8k_to_16k(pcm_8k_bytes)
            
            # Send raw audio to Gemini Live session
            await self.session.send(
                input=types.LiveClientRealtimeInput(
                    media_chunks=[types.Blob(
                        data=pcm_16k,
                        mime_type="audio/pcm;rate=16000"
                    )]
                )
            )
        except Exception as e:
            logger.error(f"Error sending audio to Gemini Live: {e}")

    async def _receive_loop(self):
        """Background task: receives audio chunks and tool calls from Gemini Live."""
        logger.info("Gemini Live receiver loop started.")
        try:
            while self.active:
                async for response in self.session.receive():
                    if not self.active:
                        break
                    try:
                        # Handle server content (audio output from Gemini)
                        if response.server_content:
                            sc = response.server_content
                            
                            # Handle User turn transcription
                            if hasattr(sc, "user_turn") and sc.user_turn and sc.user_turn.parts:
                                for part in sc.user_turn.parts:
                                    if part.text:
                                        logger.info(f"User spoken transcript: '{part.text}'")
                                        self.transcript_log.append({"sender": "user", "text": part.text})
                                        
                            # Handle Gemini interruption
                            if sc.interrupted:
                                logger.info("Gemini Live session was interrupted by user voice.")
                                self.interrupted = True
                                self.is_speaking = False  # Agent stopped speaking due to interruption
                                # Send clear command to Exotel to flush its playback buffer
                                await self.send_audio_callback(b"CLEAR_STREAM")
                                continue
                                
                            # Reset interruption flag on new model content
                            if sc.model_turn:
                                self.interrupted = False
                                self.is_speaking = True  # Agent is now generating/speaking audio
                                
                            if self.interrupted:
                                # Discard any leftover packets if we are interrupted
                                continue
                                
                            if sc.model_turn and sc.model_turn.parts:
                                for part in sc.model_turn.parts:
                                    if self.interrupted:
                                        break
                                    if part.inline_data and part.inline_data.data:
                                        # Gemini outputs 24kHz PCM — downsample to 8kHz for Exotel
                                        pcm_24k = part.inline_data.data
                                        pcm_8k = resample_24k_to_8k(pcm_24k)
                                        
                                        # Stream 320-byte chunks (20ms at 8kHz) to Exotel
                                        chunk_size = 320
                                        for i in range(0, len(pcm_8k), chunk_size):
                                            if not self.active or self.interrupted:
                                                break
                                            chunk = pcm_8k[i:i+chunk_size]
                                            if len(chunk) < chunk_size:
                                                chunk = chunk + b"\x00" * (chunk_size - len(chunk))
                                            await self.send_audio_callback(chunk)
                                            
                                    if part.text:
                                        logger.info(f"Gemini Live text response: '{part.text}'")
                                        self.transcript_log.append({"sender": "assistant", "text": part.text})

                            # Check if the model finished its turn
                            if sc.turn_complete:
                                logger.info("Gemini Live turn complete.")
                                self.is_speaking = False  # Agent finished speaking, now listening
                        
                        # Handle tool calls from Gemini
                        if response.tool_call:
                            logger.info(f"Gemini Live tool call received: {response.tool_call}")
                            await self._handle_tool_calls(response.tool_call)
                        
                    except Exception as e:
                        logger.error(f"Error in Gemini Live receiver loop payload handling: {e}")
                
                # Prevent CPU spin if connection ends abruptly
                await asyncio.sleep(0.05)
                    
        except asyncio.CancelledError:
            pass
        except Exception as e:
            logger.error(f"Error in Gemini Live receiver: {e}")
        logger.info("Gemini Live receiver loop ended.")

    async def _handle_tool_calls(self, tool_call):
        """Executes tool calls from Gemini and sends results back to the Live session."""
        function_responses = []
        
        for fc in tool_call.function_calls:
            fn_name = fc.name
            fn_args = dict(fc.args) if fc.args else {}
            fn_args["_phone"] = self.phone  # Inject phone context
            
            # Log tool request to transcript
            self.transcript_log.append({
                "sender": "system", 
                "text": f"Tool call requested: {fn_name} with parameters: {fn_args}"
            })
            
            # Hard safety: limit each tool to max 2 calls per conversation to prevent infinite retry loops
            self.tool_call_counts[fn_name] = self.tool_call_counts.get(fn_name, 0) + 1
            if self.tool_call_counts[fn_name] > 2:
                result = f"Tool '{fn_name}' has already been called {self.tool_call_counts[fn_name] - 1} times. Maximum retries exceeded. Tell the user our team will follow up manually."
                logger.warning(f"Blocked tool call '{fn_name}' — retry limit exceeded (count: {self.tool_call_counts[fn_name]})")
                self.transcript_log.append({"sender": "system", "text": f"Tool response blocked: {result}"})
                function_responses.append(types.FunctionResponse(
                    name=fn_name,
                    response={"result": result}
                ))
                continue
            
            logger.info(f"Executing tool: {fn_name} with args: {fn_args}")
            
            handler = TOOL_HANDLERS.get(fn_name)
            if handler:
                # Decouple actions (email, callback, logging) from Gemini conversation flow to prevent timeouts
                if fn_name in ["send_email", "schedule_callback", "log_lead_interest"]:
                    # Define background runner task
                    async def _background_task(h, a, name):
                        try:
                            res = await asyncio.to_thread(h, a)
                            logger.info(f"Background tool {name} completed: {res}")
                        except Exception as e:
                            logger.error(f"Error in background tool {name}: {e}")
                    
                    # Fire-and-forget: run the task asynchronously in the background
                    asyncio.create_task(_background_task(handler, fn_args, fn_name))
                    
                    # Return immediate success back to Gemini within milliseconds
                    if fn_name == "send_email":
                        result = f"Successfully initiated email sending to {fn_args.get('to_email')}."
                    elif fn_name == "schedule_callback":
                        result = f"Successfully scheduled callback for {fn_args.get('time_str')}."
                    else:
                        result = "Successfully logged lead details."
                    logger.info(f"Returned instant tool response for action tool {fn_name} to Gemini Live.")
                else:
                    # Information retrieval tools (e.g. query_product_info) must be awaited synchronously
                    try:
                        result = await asyncio.to_thread(handler, fn_args)
                        logger.info(f"Tool result for {fn_name}: {result}")
                    except Exception as e:
                        result = f"Error executing {fn_name}: {str(e)}"
                        logger.error(result)
            else:
                result = f"Unknown tool: {fn_name}"
                logger.warning(result)
            
            # Log tool response result to transcript
            self.transcript_log.append({"sender": "system", "text": f"Tool execution result: {result}"})
            
            function_responses.append(types.FunctionResponse(
                name=fn_name,
                response={"result": result}
            ))
        
        # Send tool results back to Gemini Live session
        try:
            await self.session.send(
                input=types.LiveClientToolResponse(
                    function_responses=function_responses
                )
            )
            logger.info("Tool responses sent back to Gemini Live session.")
        except Exception as e:
            logger.error(f"Error sending tool response to Gemini Live: {e}")

    async def close(self):
        """Cleans up the pipeline and Gemini Live session."""
        logger.info("Closing Voice Pipeline...")
        self.active = False
        
        if self.receiver_task:
            self.receiver_task.cancel()
            try:
                await self.receiver_task
            except asyncio.CancelledError:
                pass
        
        # Close all resources in ExitStack
        try:
            await self.exit_stack.aclose()
            logger.info("Gemini Live session and exit stack closed.")
        except Exception as e:
            logger.error(f"Error closing exit stack: {e}")
        
        # Save session logs to MongoDB with background summarization and recording fetching
        async def _background_post_call_processing(call_sid, phone, transcript, direction):
            try:
                # 1. Generate summary via Gemini
                summary = None
                if transcript:
                    logger.info("Generating call summary via Gemini...")
                    convo_text = ""
                    for turn in transcript:
                        sender = turn.get("sender", "unknown").upper()
                        text = turn.get("text", "")
                        convo_text += f"{sender}: {text}\n"
                    
                    prompt = f"""
You are an expert AI CRM manager. Review the following phone call transcript between our AI assistant (Ajay) and a customer.
Generate a structured, professional summary (max 3-4 bullet points) covering:
1. Client Profile & Business details (if mentioned).
2. Key points discussed (queries, pricing, WhatsApp/Voice agent interest).
3. Client Objections or Doubts (if any).
4. Concrete Next Steps & Action Items (e.g., callbacks, emails).

Keep it concise and clear in English.

TRANSCRIPT:
{convo_text}
"""
                    try:
                        response = await asyncio.to_thread(
                            self.client.models.generate_content,
                            model=self.summary_model_name,
                            contents=prompt
                        )
                        summary = response.text
                        logger.info(f"Gemini Call Summary: {summary}")
                    except Exception as e:
                        logger.error(f"Error generating call summary via Gemini: {e}")

                # 2. Fetch recording URL from Exotel
                recording_url = None
                if call_sid:
                    logger.info(f"Fetching recording URL from Exotel for Call SID: {call_sid}...")
                    api_key = os.getenv("EXOTEL_API_KEY")
                    api_token = os.getenv("EXOTEL_API_TOKEN")
                    account_sid = os.getenv("EXOTEL_ACCOUNT_SID")
                    
                    if api_key and api_token and account_sid:
                        import requests
                        url = f"https://api.exotel.com/v1/Accounts/{account_sid}/Calls/{call_sid}.json"
                        for attempt in range(4):
                            # Progressive delay: wait 5s, 10s, 15s, 20s
                            await asyncio.sleep(5 + attempt * 5)
                            try:
                                res = await asyncio.to_thread(
                                    requests.get, url, auth=(api_key, api_token), timeout=10
                                )
                                if res.status_code == 200:
                                    res_data = res.json()
                                    call_info = res_data.get("Call", {})
                                    rec_url = call_info.get("RecordingUrl")
                                    if rec_url:
                                        recording_url = rec_url
                                        logger.info(f"Successfully retrieved Exotel recording URL: {recording_url}")
                                        break
                                    else:
                                        logger.info(f"Attempt {attempt+1}: Call details found, but RecordingUrl not ready yet.")
                                else:
                                    logger.warning(f"Exotel details failed with status {res.status_code}: {res.text}")
                            except Exception as e:
                                logger.error(f"Error fetching call details: {e}")
                                
                # 3. Save to database
                from db.database import add_conversation
                add_conversation(
                    call_id=f"call_{int(asyncio.get_event_loop().time())}",
                    phone=phone,
                    transcript=transcript,
                    duration_seconds=30,
                    mode="cloud",
                    direction=direction,
                    summary=summary,
                    recording_url=recording_url
                )
                logger.info("Call successfully summarized, recording fetched, and logged to MongoDB.")
            except Exception as e:
                logger.error(f"Error in background post call processing: {e}")

        # Fire and forget the background task
        asyncio.create_task(_background_post_call_processing(
            call_sid=self.call_sid,
            phone=self.phone,
            transcript=list(self.transcript_log) if self.transcript_log else [],
            direction=self.direction
        ))
