#!/usr/bin/env python3
"""
Manual live model smoke verification script for NIKO.
Runs OUTSIDE CI to verify real upstream provider endpoints and models.
Usage:
    python scripts/smoke_models.py
"""

import asyncio
import os
import time
from typing import Any

import httpx
from dotenv import load_dotenv

load_dotenv()

# Models to verify
MODELS_TO_PROBE = [
    {"provider": "groq", "model": "openai/gpt-oss-20b", "role": "fast"},
    {"provider": "gemini", "model": "gemini-3.5-flash-lite", "role": "fast / vision_long"},
    {"provider": "groq", "model": "openai/gpt-oss-120b", "role": "coder"},
    {"provider": "gemini", "model": "gemini-3.8-flash", "role": "coder / vision_long"},
    {"provider": "openrouter", "model": "openrouter/free", "role": "fast / coder fallback"},
    {"provider": "openrouter", "model": "cohere/north-mini-code:free", "role": "coder fallback"},
]


async def probe_gemini(api_key: str, model: str) -> dict[str, Any]:
    url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"
    headers = {
        "x-goog-api-key": api_key,
        "Content-Type": "application/json",
    }
    payload = {
        "contents": [{"role": "user", "parts": [{"text": "Say 'OK' and nothing else."}]}],
        "generationConfig": {
            "maxOutputTokens": 16,
            "thinkingConfig": {"thinkingLevel": "low"},
        },
    }
    start = time.time()
    async with httpx.AsyncClient(timeout=15.0) as client:
        res = await client.post(url, headers=headers, json=payload)
        latency_ms = int((time.time() - start) * 1000)
        if res.status_code == 200:
            data = res.json()
            candidates = data.get("candidates", [])
            text = ""
            if candidates:
                parts = candidates[0].get("content", {}).get("parts", [])
                text = "".join(p.get("text", "") for p in parts).strip()
            return {"status": "SUCCESS", "status_code": 200, "latency_ms": latency_ms, "reply": text[:50]}
        return {"status": f"HTTP {res.status_code}", "status_code": res.status_code, "latency_ms": latency_ms, "reply": res.text[:80]}


async def probe_groq(api_key: str, model: str) -> dict[str, Any]:
    url = "https://api.groq.com/openai/v1/chat/completions"
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }
    payload = {
        "model": model,
        "messages": [{"role": "user", "content": "Say 'OK' and nothing else."}],
        "max_tokens": 16,
    }
    start = time.time()
    async with httpx.AsyncClient(timeout=15.0) as client:
        res = await client.post(url, headers=headers, json=payload)
        latency_ms = int((time.time() - start) * 1000)
        if res.status_code == 200:
            data = res.json()
            choices = data.get("choices", [])
            text = ""
            if choices and isinstance(choices[0], dict):
                msg = choices[0].get("message") or {}
                text = (msg.get("content") or msg.get("reasoning") or "").strip()
            return {"status": "SUCCESS", "status_code": 200, "latency_ms": latency_ms, "reply": text[:50]}
        return {"status": f"HTTP {res.status_code}", "status_code": res.status_code, "latency_ms": latency_ms, "reply": res.text[:80]}


async def probe_openrouter(api_key: str | None, model: str) -> dict[str, Any]:
    url = "https://openrouter.ai/api/v1/chat/completions"
    headers = {
        "Content-Type": "application/json",
    }
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"
    payload = {
        "model": model,
        "messages": [{"role": "user", "content": "Say 'OK' and nothing else."}],
        "max_tokens": 16,
    }
    start = time.time()
    async with httpx.AsyncClient(timeout=20.0) as client:
        res = await client.post(url, headers=headers, json=payload)
        latency_ms = int((time.time() - start) * 1000)
        if res.status_code == 200:
            data = res.json()
            choices = data.get("choices", [])
            text = ""
            if choices and isinstance(choices[0], dict):
                msg = choices[0].get("message") or {}
                text = (msg.get("content") or msg.get("reasoning") or "").strip()
            return {"status": "SUCCESS", "status_code": 200, "latency_ms": latency_ms, "reply": text[:50]}
        return {"status": f"HTTP {res.status_code}", "status_code": res.status_code, "latency_ms": latency_ms, "reply": res.text[:80]}


async def main() -> None:
    gemini_key = os.getenv("INITIAL_GEMINI_API_KEY") or os.getenv("GEMINI_API_KEY") or ""
    groq_key = os.getenv("INITIAL_GROQ_API_KEY") or os.getenv("GROQ_API_KEY") or ""
    openrouter_key = os.getenv("INITIAL_OPENROUTER_API_KEY") or os.getenv("OPENROUTER_API_KEY") or ""

    print("================================================================================")
    print("                      NIKO LIVE MODEL SMOKE VERIFICATION                        ")
    print("================================================================================")
    print(f"Gemini Key Present:     {'YES (redacted)' if gemini_key else 'NO'}")
    print(f"Groq Key Present:       {'YES (redacted)' if groq_key else 'NO'}")
    print(f"OpenRouter Key Present: {'YES (redacted)' if openrouter_key else 'NO (using free tier)'}")
    print("--------------------------------------------------------------------------------")
    print(f"{'PROVIDER':<12} | {'ROLE':<22} | {'MODEL':<30} | {'STATUS':<10} | {'LATENCY':<8}")
    print("--------------------------------------------------------------------------------")

    for item in MODELS_TO_PROBE:
        prov = item["provider"]
        mod = item["model"]
        role = item["role"]

        try:
            if prov == "gemini":
                if not gemini_key:
                    print(f"{prov:<12} | {role:<22} | {mod:<30} | {'SKIPPED (no key)':<10} | {'-':<8}")
                    continue
                res = await probe_gemini(gemini_key, mod)
            elif prov == "groq":
                if not groq_key:
                    print(f"{prov:<12} | {role:<22} | {mod:<30} | {'SKIPPED (no key)':<10} | {'-':<8}")
                    continue
                res = await probe_groq(groq_key, mod)
            elif prov == "openrouter":
                res = await probe_openrouter(openrouter_key, mod)
            else:
                continue

            status_str = res["status"]
            lat_str = f"{res['latency_ms']}ms"
            print(f"{prov:<12} | {role:<22} | {mod:<30} | {status_str:<10} | {lat_str:<8}")
        except Exception as e:
            print(f"{prov:<12} | {role:<22} | {mod:<30} | {'ERROR':<10} | {str(e)[:20]:<8}")

    print("================================================================================")
    print("Smoke probe completed.")


if __name__ == "__main__":
    asyncio.run(main())
