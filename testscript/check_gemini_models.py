import os
import sys
import asyncio
from dotenv import load_dotenv

# Strip GCP environment variables so google-genai does not redirect to Vertex AI
for var in [
    "GOOGLE_APPLICATION_CREDENTIALS",
    "GCP_SERVICE_ACCOUNT_JSON",
    "GCP_PROJECT",
    "GCP_LOCATION",
    "GOOGLE_CLOUD_PROJECT",
    "GOOGLE_CLOUD_LOCATION",
]:
    os.environ.pop(var, None)

load_dotenv()
api_key = os.getenv("GEMINI_API_KEY", "")
current_live_model = os.getenv("GEMINI_LIVE_MODEL", "gemini-2.5-flash-native-audio-latest")

print(f"Loaded API Key: {api_key[:10]}...{api_key[-4:] if len(api_key) > 14 else ''}")
print(f"Current Live Model in .env: {current_live_model}")

from google import genai
from google.genai import types

async def test_live_connection(client, model_name):
    print(f"\nTesting Live connection probe to '{model_name}'...")
    try:
        config = types.LiveConnectConfig(
            response_modalities=["AUDIO"],
            speech_config=types.SpeechConfig(
                voice_config=types.VoiceConfig(
                    prebuilt_voice_config=types.PrebuiltVoiceConfig(voice_name="Aoede")
                )
            ),
        )
        async with client.aio.live.connect(model=model_name, config=config) as session:
            print(f" -> SUCCESS! Real-time Live session handshake PASSED for '{model_name}'!")
            return True
    except Exception as e:
        print(f" -> FAILED Live connection to '{model_name}': {e}")
        return False

async def main():
    if not api_key:
        print("ERROR: No GEMINI_API_KEY found in .env")
        return

    client = genai.Client(api_key=api_key)

    # 1. Fetch all models
    print("\n--- 1. Querying Available Models from Google API ---")
    try:
        models = list(client.models.list())
        print(f"API Key is ACTIVE! Total models accessible: {len(models)}")
        
        all_model_ids = [getattr(m, "name", str(m)) for m in models]
        
        print("\nAll Available Models:")
        for mid in sorted(all_model_ids):
            print(f"  • {mid}")

        # Check for 3.8 models
        models_38 = [mid for mid in all_model_ids if "3.8" in mid]
        print("\n--- 2. Checking for Gemini 3.8 Models ---")
        if models_38:
            print(f"Found Gemini 3.8 models: {models_38}")
        else:
            print("No models containing '3.8' found in the standard models list.")

        # Check for Live / Native Audio / 2.5 models
        live_like = [mid for mid in all_model_ids if any(k in mid.lower() for k in ["live", "realtime", "native", "2.5"])]
        print(f"\nLive/Realtime/2.5 models in catalog: {live_like}")

    except Exception as e:
        print(f"Error querying models list: {e}")

    # 2. Live Connection Probe
    print("\n--- 3. Testing Real Live WebSockets ---")
    
    # Test current working 2.5 model
    await test_live_connection(client, current_live_model)
    
    # Test Gemini 3.8 Live candidates
    candidates_38 = [
        "gemini-3.8-live",
        "gemini-3.8-flash",
        "gemini-3.8-live-extended-thinking",
        "models/gemini-3.8-live",
    ]
    for m in candidates_38:
        await test_live_connection(client, m)

if __name__ == "__main__":
    asyncio.run(main())
