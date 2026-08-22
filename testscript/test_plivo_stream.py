import os
import sys
import json
import base64
import asyncio
from fastapi.testclient import TestClient

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from cloud.server import app

def test_plivo_answer_endpoint():
    """Test Plivo XML response generation for incoming / outbound calls."""
    client = TestClient(app)
    
    # 1. Test GET request
    response = client.get("/plivo/answer?From=+919399250600&Direction=inbound&CallUUID=test-uuid-1234")
    print(f"GET /plivo/answer status: {response.status_code}")
    print(f"Content-Type: {response.headers.get('content-type')}")
    assert response.status_code == 200
    assert "application/xml" in response.headers.get("content-type", "")
    assert "<Stream" in response.text
    assert "bidirectional=\"true\"" in response.text
    assert "audio/x-l16;rate=8000" in response.text
    assert "test-uuid-1234" in response.text
    print("GET /plivo/answer test PASSED!\n")
    
    # 2. Test POST request (Plivo webhook style)
    response_post = client.post(
        "/plivo/answer",
        data={
            "From": "+919876543210",
            "Direction": "outbound",
            "CallUUID": "uuid-outbound-999"
        }
    )
    print(f"POST /plivo/answer status: {response_post.status_code}")
    assert response_post.status_code == 200
    assert "uuid-outbound-999" in response_post.text
    assert "direction=outbound" in response_post.text
    print("POST /plivo/answer test PASSED!\n")

def test_plivo_websocket_flow():
    """Test Plivo WebSocket start and media exchange."""
    client = TestClient(app)
    
    print("Testing Plivo WebSocket endpoint /ws/plivo...")
    with client.websocket_connect("/ws/plivo?phone=+919399250600&direction=inbound") as ws:
        # 1. Send start event
        start_payload = {
            "event": "start",
            "sequenceNumber": 1,
            "streamId": "plivo-stream-001",
            "start": {
                "streamId": "plivo-stream-001",
                "callId": "plivo-call-001",
                "from": "+919399250600",
                "to": "+911234567890",
                "mediaFormat": {
                    "encoding": "audio/x-l16",
                    "sampleRate": 8000
                }
            }
        }
        ws.send_text(json.dumps(start_payload))
        print("Sent Plivo 'start' event.")
        
        # 2. Send silence / dummy audio media packet (8kHz PCM 16-bit, 320 bytes = 20ms)
        dummy_pcm = b"\x00" * 320
        media_payload = {
            "event": "media",
            "sequenceNumber": 2,
            "streamId": "plivo-stream-001",
            "media": {
                "track": "inbound",
                "chunk": 1,
                "timestamp": 20,
                "payload": base64.b64encode(dummy_pcm).decode("utf-8")
            }
        }
        ws.send_text(json.dumps(media_payload))
        print("Sent Plivo 'media' audio packet.")
        
        # 3. Send stop event
        stop_payload = {
            "event": "stop",
            "streamId": "plivo-stream-001",
            "stop": {
                "callId": "plivo-call-001"
            }
        }
        ws.send_text(json.dumps(stop_payload))
        print("Sent Plivo 'stop' event.")
        
    print("Plivo WebSocket lifecycle test PASSED!\n")

if __name__ == "__main__":
    print("--- Starting Plivo Integration Tests ---")
    test_plivo_answer_endpoint()
    test_plivo_websocket_flow()
    print("--- ALL PLIVO TESTS PASSED SUCCESSFULLY! ---")
