import os
import sys
import asyncio
import logging

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import config
from google.genai import types

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

async def test_live_api():
    print("=== Testing Gemini Live API Connection ===")
    client, is_vertex = config.get_gemini_client()
    print(f"Mode: {'Vertex AI' if is_vertex else 'AI Studio API Key'}")
    
    # Select appropriate model based on Vertex AI vs AI Studio
    model_name = "gemini-live-2.5-flash-native-audio" if is_vertex else "gemini-2.5-flash-native-audio-latest"
    print(f"Target Model: {model_name}")
    
    live_config = types.LiveConnectConfig(
        response_modalities=["AUDIO"],
        speech_config=types.SpeechConfig(
            voice_config=types.VoiceConfig(
                prebuilt_voice_config=types.PrebuiltVoiceConfig(voice_name="Aoede")
            )
        )
    )
    
    try:
        print("Connecting to Gemini Live WebSocket...")
        async with client.aio.live.connect(model=model_name, config=live_config) as session:
            print("SUCCESS! Connected to Gemini Live API WebSocket successfully.")
            
            # Send a simple text prompt to verify two-way streaming
            await session.send(
                input=types.LiveClientContent(
                    turns=[types.Content(
                        role="user",
                        parts=[types.Part.from_text(text="Hello, respond with a short audio greeting.")]
                    )],
                    turn_complete=True
                )
            )
            print("Prompt sent. Waiting for initial response...")
            
            received = False
            async for response in session.receive():
                if response.server_content:
                    sc = response.server_content
                    if sc.model_turn and sc.model_turn.parts:
                        for part in sc.model_turn.parts:
                            if part.inline_data:
                                print(f"Received audio chunk: {len(part.inline_data.data)} bytes")
                                received = True
                            if part.text:
                                print(f"Received text: {part.text}")
                    if sc.turn_complete:
                        print("Turn complete received!")
                        break
                if received:
                    break
                    
            if received:
                print("=== Gemini Live API is 100% ACTIVE and FUNCTIONAL ===")
                return True
            else:
                print("Connected but did not receive audio response.")
                return False
    except Exception as e:
        print(f"FAILED to connect to Gemini Live API: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    success = asyncio.run(test_live_api())
    sys.exit(0 if success else 1)
