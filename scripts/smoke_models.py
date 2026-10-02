#!/usr/bin/env python3
"""
Manual live model smoke verification script for NIKO.
Runs OUTSIDE CI to verify real upstream provider endpoints and models.

Usage:
    python scripts/smoke_models.py          # Quick smoke (high-quota models only: Groq 20b, Flash-Lite, OpenRouter free)
    python scripts/smoke_models.py --full   # Full probe (includes scarce 20-RPD Flash models)
"""

import argparse
import asyncio
import os
import time
from typing import Any

import httpx
from dotenv import load_dotenv

load_dotenv()

# Standard low-impact models (500+ RPD)
STANDARD_MODELS = [
    {"provider": "groq", "model": "openai/gpt-oss-20b", "role": "fast (primary)", "rpd": "1,000"},
    {"provider": "gemini", "model": "gemini-3.5-flash-lite", "role": "fast / vision_long", "rpd": "500"},
    {"provider": "openrouter", "model": "openrouter/free", "role": "fast / coder fallback", "rpd": "200"},
]

# Scarce models (20 RPD pools)
SCARCE_MODELS = [
    {"provider": "groq", "model": "openai/gpt-oss-120b", "role": "coder (primary)", "rpd": "1,000"},
    {"provider": "gemini", "model": "gemini-3.8-flash", "role": "coder (ladder 1)", "rpd": "20 (scarce)"},
    {"provider": "gemini", "model": "gemini-3.7-flash", "role": "coder (ladder 2)", "rpd": "20 (scarce)"},
    {"provider": "gemini", "model": "gemini-3.5-flash", "role": "coder (ladder 3)", "rpd": "20 (scarce)"},
    {"provider": "openrouter", "model": "cohere/north-mini-code:free", "role": "coder fallback", "rpd": "200"},
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
    parser = argparse.ArgumentParser(description="NIKO Model Live Smoke Probe")
    parser.add_argument(
        "--full",
        "-f",
        action="store_true",
        help="Include scarce 20-RPD Flash models in probe (consumes real quota)",
    )
    args = parser.parse_args()

    gemini_key = os.getenv("INITIAL_GEMINI_API_KEY") or os.getenv("GEMINI_API_KEY") or ""
    groq_key = os.getenv("INITIAL_GROQ_API_KEY") or os.getenv("GROQ_API_KEY") or ""
    openrouter_key = os.getenv("INITIAL_OPENROUTER_API_KEY") or os.getenv("OPENROUTER_API_KEY") or ""

    models_to_probe = list(STANDARD_MODELS)
    if args.full:
        print("********************************************************************************")
        print("  WARNING: FULL PROBE ENABLED. CONSUMES 1 REQUEST FROM 20-RPD FLASH POOLS!      ")
        print("********************************************************************************")
        models_to_probe.extend(SCARCE_MODELS)
    else:
        print("Note: Running standard probe (500+ RPD models). Use '--full' to test 20-RPD models.")

    print("================================================================================")
    print("                      NIKO LIVE MODEL SMOKE VERIFICATION                        ")
    print("================================================================================")
    print(f"Gemini Key Present:     {'YES (redacted)' if gemini_key else 'NO'}")
    print(f"Groq Key Present:       {'YES (redacted)' if groq_key else 'NO'}")
    print(f"OpenRouter Key Present: {'YES (redacted)' if openrouter_key else 'NO (using free tier)'}")
    print("--------------------------------------------------------------------------------")
    print(f"{'PROVIDER':<12} | {'ROLE':<22} | {'MODEL':<28} | {'RPD':<10} | {'STATUS':<9} | {'LATENCY':<7}")
    print("--------------------------------------------------------------------------------")

    for item in models_to_probe:
        prov = item["provider"]
        mod = item["model"]
        role = item["role"]
        rpd = item["rpd"]

        try:
            if prov == "gemini":
                if not gemini_key:
                    print(f"{prov:<12} | {role:<22} | {mod:<28} | {rpd:<10} | {'NO KEY':<9} | {'-':<7}")
                    continue
                res = await probe_gemini(gemini_key, mod)
            elif prov == "groq":
                if not groq_key:
                    print(f"{prov:<12} | {role:<22} | {mod:<28} | {rpd:<10} | {'NO KEY':<9} | {'-':<7}")
                    continue
                res = await probe_groq(groq_key, mod)
            elif prov == "openrouter":
                res = await probe_openrouter(openrouter_key, mod)
            else:
                continue

            status_str = res["status"]
            lat_str = f"{res['latency_ms']}ms"
            print(f"{prov:<12} | {role:<22} | {mod:<28} | {rpd:<10} | {status_str:<9} | {lat_str:<7}")
        except Exception as e:
            print(f"{prov:<12} | {role:<22} | {mod:<28} | {rpd:<10} | {'ERROR':<9} | {str(e)[:15]:<7}")

    print("================================================================================")
    print("Smoke probe completed.")


if __name__ == "__main__":
    asyncio.run(main())
