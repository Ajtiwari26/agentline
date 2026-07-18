import os
import sys
import asyncio
import logging
import sounddevice as sd
from dotenv import load_dotenv
from google import genai
from google.genai import types
from contextlib import AsyncExitStack

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import config
from core.prompts import build_system_prompt, load_kb
from db.database import get_lead, setup_indexes

logging.basicConfig(level=logging.WARNING, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

load_dotenv()

async def main():
    # 1. Setup DB and Lead Context
    try:
        setup_indexes()
    except Exception:
        pass
        
    target_phone = "9399250600"
    direction = "inbound"
    if len(sys.argv) > 1:
        direction = sys.argv[1].strip().lower()
    if len(sys.argv) > 2:
        target_phone = sys.argv[2].strip()

    lead_info = get_lead(target_phone)
    print(f"Loaded Lead Context: {lead_info}")
    
    system_prompt = build_system_prompt(lead_info, direction=direction)
    
    # 2. Initialize Gemini Client
    sa_key_path = os.getenv("GOOGLE_APPLICATION_CREDENTIALS", "")
    if sa_key_path and os.path.exists(sa_key_path):
        from google.oauth2 import service_account
        scopes = ["https://www.googleapis.com/auth/cloud-platform"]
        credentials = service_account.Credentials.from_service_account_file(sa_key_path, scopes=scopes)
        client = genai.Client(
            vertexai=True,
            project=os.getenv("GCP_PROJECT", "igsl-67e70"),
            location="us-central1",
            credentials=credentials
        )
        model = "gemini-live-2.5-flash-native-audio"
    else:
        client = genai.Client(api_key=config.GEMINI_API_KEY)
        model = "gemini-2.0-flash"
        
    print(f"Connecting to Gemini Live ({model})...")
    
    kb = load_kb()
    company = getattr(config, "COMPANY", "nukkad").lower()
    welcome_text = ""
    if direction == "inbound":
        if company == "bla_bli_blu":
            agent_name = kb.get("system", {}).get("agent_name", "Kavya")
            brand_name = kb.get("system", {}).get("brand_name", "Bla Bli Blu")
            welcome_text = f"Hey! {brand_name} mein aapka swagat hai. Main {agent_name} hoon. Bataiye, kaise madad kar sakti hoon?"
        else:
            agent_name = getattr(config, "AGENT_NAME", "Ajay")
            welcome_text = f"Hey! Nukkad Tech Solutions mein aapka swagat hai. Main {agent_name} hoon. Bataiye, kaise madad kar {'sakti' if agent_name.lower() == 'kavya' else 'sakta'} hoon?"
    else:
        welcome_text = kb.get("conversation_stages", {}).get("greeting", {}).get("script", "Hey! Kaise ho?")
    # Determine voice name dynamically (default to female Aoede for Kavya/Bla Bli Blu, Charon otherwise)
    env_voice = getattr(config, "GEMINI_LIVE_VOICE", None)
    if company == "bla_bli_blu" or kb.get("system", {}).get("agent_name", "").lower() == "kavya":
        voice_name = env_voice if env_voice and env_voice != "Charon" else "Aoede"
    else:
        voice_name = env_voice or "Charon"

    live_config = types.LiveConnectConfig(
        response_modalities=["AUDIO"],
        speech_config=types.SpeechConfig(
            voice_config=types.VoiceConfig(
                prebuilt_voice_config=types.PrebuiltVoiceConfig(voice_name=voice_name)
            )
        ),
        system_instruction=types.Content(parts=[types.Part.from_text(text=system_prompt)]),
    )
    
    # 3. Audio setup
    # Query and print available audio devices
    print("\n--- Available Audio Devices ---")
    try:
        devices = sd.query_devices()
        print(devices)
        default_input = sd.query_devices(kind='input')
        default_output = sd.query_devices(kind='output')
        print(f"Default Input: {default_input['name']}")
        print(f"Default Output: {default_output['name']}")
    except Exception as dev_err:
        print(f"Warning: Could not query audio devices: {dev_err}")
    print("--------------------------------\n")
    
    try:
        out_stream = sd.RawOutputStream(samplerate=24000, channels=1, dtype='int16')
        out_stream.start()
    except Exception as out_err:
        print(f"Fatal: Failed to start speaker output stream: {out_err}")
        return
    
    exit_stack = AsyncExitStack()
    
    try:
        async with exit_stack:
            session = await exit_stack.enter_async_context(
                client.aio.live.connect(model=model, config=live_config)
            )
            print("Connected! Starting audio loop...")
        
            # Trigger greeting
            await session.send(
                input=types.LiveClientContent(
                    turns=[types.Content(
                        role="user",
                        parts=[types.Part.from_text(
                            text=f"Start the conversation by saying exactly this greeting: {welcome_text}"
                        )]
                    )],
                    turn_complete=True
                )
            )
            
            # Audio input callback (captures Mac mic at 16kHz and sends directly to Gemini)
            loop = asyncio.get_running_loop()
            def audio_input_callback(indata, frames, time, status):
                audio_bytes = bytes(indata)
                fut = asyncio.run_coroutine_threadsafe(
                    session.send(
                        input=types.LiveClientRealtimeInput(
                            media_chunks=[types.Blob(
                                data=audio_bytes,
                                mime_type="audio/pcm;rate=16000"
                            )]
                        )
                    ),
                    loop
                )
                def fut_callback(f):
                    try:
                        f.result()
                    except Exception as e:
                        print(f"Background Audio Send Error: {e}")
                fut.add_done_callback(fut_callback)
                
            in_stream = sd.RawInputStream(
                samplerate=16000,
                channels=1,
                dtype='int16',
                callback=audio_input_callback,
                blocksize=3200 # 200ms blocks
            )
            in_stream.start()
            
            print("\n>>> Speak into your Mac microphone. Press Ctrl+C to stop. <<<\n")
            
            # Receive loop
            try:
                async for response in session.receive():
                    server_content = response.server_content
                    if server_content is not None:
                        model_turn = server_content.model_turn
                        if model_turn is not None:
                            for part in model_turn.parts:
                                if part.inline_data and part.inline_data.data:
                                    # Play Gemini's 24kHz audio stream directly
                                    out_stream.write(part.inline_data.data)
            except asyncio.CancelledError:
                pass
            except KeyboardInterrupt:
                pass
            except Exception as e:
                import traceback
                print("Error in receive loop:")
                traceback.print_exc()
            finally:
                in_stream.stop()
                in_stream.close()
                print("Session ended.")
    except Exception as e:
        import traceback
        print("Error in exit stack:")
        traceback.print_exc()
    finally:
        out_stream.stop()
        out_stream.close()

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\nExiting...")
    except Exception as e:
        import traceback
        print("Fatal error in main:")
        traceback.print_exc()
