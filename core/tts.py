import os
import base64
import requests
import logging
import asyncio
import config

logger = logging.getLogger(__name__)

# Simple cache for welcome messages or common phrases
_audio_cache = {}

def get_sarvam_tts_sync(text: str, language_code: str = "hi-IN", speaker: str = "shubh", sample_rate: int = 8000) -> bytes:
    """Synchronous request to Sarvam Text-to-Speech API. Returns raw PCM bytes."""
    url = "https://api.sarvam.ai/text-to-speech"
    payload = {
        "text": text,
        "target_language_code": language_code,
        "speaker": speaker,
        "model": "bulbul:v3",
        "speech_sample_rate": sample_rate,
        "output_audio_codec": "linear16"
    }
    headers = {
        "api-subscription-key": config.SARVAM_API_KEY
    }
    
    try:
        response = requests.post(url, json=payload, headers=headers, timeout=10)
        if response.status_code == 200:
            res_data = response.json()
            audios = res_data.get("audios", [])
            pcm_bytes = b"".join(base64.b64decode(audio_base64) for audio_base64 in audios)
            return pcm_bytes
        else:
            logger.error(f"Sarvam TTS failed with status {response.status_code}: {response.text}")
            return b""
    except Exception as e:
        logger.error(f"Error calling Sarvam TTS: {e}")
        return b""

async def get_sarvam_tts(text: str, language_code: str = "hi-IN", speaker: str = "shubh", sample_rate: int = 8000) -> bytes:
    """Asynchronous wrapper for Sarvam Text-to-Speech API."""
    cache_key = f"{text}_{language_code}_{speaker}_{sample_rate}"
    if cache_key in _audio_cache:
        return _audio_cache[cache_key]
        
    pcm_bytes = await asyncio.to_thread(
        get_sarvam_tts_sync, text, language_code, speaker, sample_rate
    )
    
    if pcm_bytes:
        # Cache small responses (< 1MB)
        if len(pcm_bytes) < 1024 * 1024:
            _audio_cache[cache_key] = pcm_bytes
            
    return pcm_bytes

async def pre_cache_welcome_message(welcome_text: str):
    """Pre-synthesizes and caches the main greeting response to prevent media timeouts."""
    logger.info("Pre-caching welcome message...")
    pcm = await get_sarvam_tts(welcome_text)
    if pcm:
        logger.info(f"Welcome message cached successfully. Cache size: {len(pcm)} bytes.")
    else:
        logger.error("Failed to cache welcome message.")
