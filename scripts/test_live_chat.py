#!/usr/bin/env python3
"""
Test Live Chat script against the running NIKO backend.
Sends a test message over WebSocket or REST and prints the exact reply or error.
"""

import asyncio
import json
import os

import httpx
from dotenv import load_dotenv

load_dotenv()

BACKEND_URL = os.getenv("BACKEND_URL", "http://127.0.0.1:8000")
WS_URL = os.getenv("WS_URL", "ws://127.0.0.1:8000/ws")

async def test_live_chat():
    print(f"Connecting to running backend at {BACKEND_URL}...")
    async with httpx.AsyncClient(timeout=5.0) as client:
        try:
            health = await client.get(f"{BACKEND_URL}/api/v1/health")
            print(f"Health response ({health.status_code}): {health.text}")
        except Exception as e:
            print(f"Backend connection error: {type(e).__name__}: {e}")
            return

    # Try auth session or WS
    print("Testing chat endpoint...")
    try:
        import websockets
        async with websockets.connect(f"{WS_URL}?origin=http://localhost:5173", timeout=5.0) as ws:
            req_id = "test-live-probe-1"
            await ws.send(json.dumps({
                "type": "chat",
                "request_id": req_id,
                "content": "Hello NIKO, are you awake?",
            }))
            print("Message sent, waiting for reply...")
            while True:
                msg_raw = await asyncio.wait_for(ws.recv(), timeout=10.0)
                data = json.loads(msg_raw)
                print("Received event:", data)
                if data.get("type") in ("chat:done", "error", "chat:error"):
                    break
    except Exception as e:
        print(f"Chat error: {type(e).__name__}: {e}")

if __name__ == "__main__":
    asyncio.run(test_live_chat())
