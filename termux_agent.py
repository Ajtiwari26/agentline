import os
import sys
import asyncio
import logging
import socket
import array

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger("TermuxAgent")

# Add agentline parent directory to path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from core.pipeline import VoicePipeline

# Sockets and ports configuration
HOST = "127.0.0.1"
PORT_CAPTURE = 9001
PORT_PLAYBACK = 9002
PORT_CONTROL = 9003

pipeline = None
playback_socket = None

def downsample_16k_to_8k(pcm_16k: bytes) -> bytes:
    """Downsamples 16kHz 16-bit mono PCM to 8kHz 16-bit mono PCM using array slicing."""
    samples = array.array('h', pcm_16k)
    downsampled = samples[::2]
    return downsampled.tobytes()

async def send_audio_to_playback(chunk: bytes):
    """Sends 8kHz 16-bit PCM bytes to the Android AudioBridge playback socket."""
    global playback_socket
    if playback_socket:
        try:
            loop = asyncio.get_running_loop()
            await loop.sock_sendall(playback_socket, chunk)
        except Exception as e:
            logger.error(f"Failed to send playback audio: {e}")

async def handle_capture_client(reader, writer):
    """Receives 16kHz PCM stream from AudioBridge, downsamples to 8kHz, and feeds into pipeline."""
    global pipeline
    logger.info("Shizuku Audio capture stream connected!")
    try:
        while True:
            # Read chunks of raw 16kHz PCM audio
            data = await reader.read(4096)
            if not data:
                logger.info("Capture stream closed by client.")
                break
                
            if pipeline and pipeline.active:
                # Downsample 16kHz -> 8kHz
                pcm_8k = downsample_16k_to_8k(data)
                await pipeline.handle_incoming_audio(pcm_8k)
    except Exception as e:
        logger.error(f"Error in capture stream handler: {e}")
    finally:
        writer.close()
        await writer.wait_closed()
        logger.info("Capture stream disconnected.")

async def start_capture_server():
    """Starts the TCP server on PORT_CAPTURE to listen for ShizukuUserService connections."""
    server = await asyncio.start_server(handle_capture_client, HOST, PORT_CAPTURE)
    logger.info(f"Capture server listening on {HOST}:{PORT_CAPTURE}...")
    async with server:
        await server.serve_forever()

async def run_pipeline(phone_number: str, direction: str = "outbound"):
    """Initializes and starts the VoicePipeline."""
    global pipeline, playback_socket
    
    # Setup playback socket
    logger.info(f"Connecting to playback socket on {HOST}:{PORT_PLAYBACK}...")
    while True:
        try:
            playback_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            playback_socket.setblocking(False)
            loop = asyncio.get_running_loop()
            await loop.sock_connect(playback_socket, (HOST, PORT_PLAYBACK))
            logger.info("Connected to playback socket!")
            break
        except ConnectionRefusedError:
            await asyncio.sleep(0.5)

    # Initialize voice pipeline
    pipeline = VoicePipeline(phone=phone_number, direction=direction, send_audio_callback=send_audio_to_playback)
    await pipeline.start()

async def stop_pipeline():
    """Stops the VoicePipeline and closes the playback socket."""
    global pipeline, playback_socket
    if pipeline:
        await pipeline.close()
        pipeline = None
        
    if playback_socket:
        playback_socket.close()
        playback_socket = None
    logger.info("Pipeline stopped.")

async def main():
    # Start the local capture stream server in the background
    asyncio.create_task(start_capture_server())

    logger.info("Termux Agent starting. Connecting to Control Socket...")
    
    # Connect to the Control Server socket (AudioBridgeService)
    while True:
        try:
            control_reader, control_writer = await asyncio.open_connection(HOST, PORT_CONTROL)
            logger.info("Connected to control socket!")
            break
        except ConnectionRefusedError:
            await asyncio.sleep(1.0)

    try:
        while True:
            line = await control_reader.readline()
            if not line:
                logger.info("Control connection lost. Exiting...")
                break
                
            message = line.decode('utf-8').strip()
            logger.info(f"Control message: {message}")
            
            if message.startswith("CALL_STARTED:"):
                parts = message.split(":")
                phone_number = parts[1]
                direction = parts[2] if len(parts) > 2 else "outbound"
                logger.info(f"Call detected: number={phone_number}, direction={direction}. Launching voice agent...")
                await run_pipeline(phone_number, direction)
                
            elif message == "CALL_ENDED":
                logger.info("Call hung up. Shutting down voice agent...")
                await stop_pipeline()
                
    except Exception as e:
        logger.error(f"Error in control loop: {e}")
    finally:
        await stop_pipeline()
        control_writer.close()
        await control_writer.wait_closed()

if __name__ == "__main__":
    asyncio.run(main())
