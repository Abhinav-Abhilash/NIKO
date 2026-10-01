import asyncio
import math
import struct
import time
from collections.abc import Callable
from typing import Any

from backend.app.core.events import EventBus, get_event_bus
from backend.app.core.logging import get_logger

logger = get_logger("voice_service")


class VoiceActivityDetector:
    """
    Real-time Voice Activity Detection (VAD) & Energy Gate.
    Calculates root-mean-square (RMS) energy and tracks speech/silence transitions
    with adaptive noise floor calibration.
    """

    def __init__(
        self,
        energy_threshold: float = 0.015,
        speech_pad_frames: int = 3,
        silence_pad_frames: int = 8,
    ) -> None:
        self.energy_threshold = energy_threshold
        self.speech_pad_frames = speech_pad_frames
        self.silence_pad_frames = silence_pad_frames

        self.is_user_speaking = False
        self.consecutive_speech_frames = 0
        self.consecutive_silence_frames = 0
        self.noise_floor = 0.005

    def calculate_pcm16_rms(self, pcm_bytes: bytes) -> float:
        """Calculate normalized RMS energy from 16-bit linear PCM audio chunk."""
        if not pcm_bytes:
            return 0.0
        sample_count = len(pcm_bytes) // 2
        if sample_count == 0:
            return 0.0

        try:
            # Unpack signed 16-bit integers
            shorts = struct.unpack(f"<{sample_count}h", pcm_bytes)
            sum_squares = sum((s / 32768.0) ** 2 for s in shorts)
            return math.sqrt(sum_squares / sample_count)
        except Exception:
            return 0.0

    def process_frame(self, pcm_bytes: bytes) -> dict[str, Any]:
        """
        Process a PCM frame and return detection event.
        Events: 'speech_start', 'speaking', 'speech_end', 'silence'.
        """
        rms = self.calculate_pcm16_rms(pcm_bytes)

        # Adaptive background noise tracking (slow upward/downward drift)
        if rms < self.energy_threshold:
            self.noise_floor = 0.95 * self.noise_floor + 0.05 * rms

        dynamic_threshold = max(self.energy_threshold, self.noise_floor * 2.5)
        is_above_threshold = rms >= dynamic_threshold

        event_type = "silence"

        if is_above_threshold:
            self.consecutive_speech_frames += 1
            self.consecutive_silence_frames = 0

            if not self.is_user_speaking:
                if self.consecutive_speech_frames >= self.speech_pad_frames:
                    self.is_user_speaking = True
                    event_type = "speech_start"
            else:
                event_type = "speaking"
        else:
            self.consecutive_silence_frames += 1
            self.consecutive_speech_frames = 0

            if self.is_user_speaking:
                if self.consecutive_silence_frames >= self.silence_pad_frames:
                    self.is_user_speaking = False
                    event_type = "speech_end"
                else:
                    event_type = "speaking"

        return {
            "event": event_type,
            "rms": round(rms, 5),
            "is_speaking": self.is_user_speaking,
            "dynamic_threshold": round(dynamic_threshold, 5),
        }


class VoiceBargeInEngine:
    """
    Manages full-duplex conversational voice sessions and barge-in interruptions.
    When user speech is detected during assistant speech or LLM generation,
    immediately aborts the active stream and dispatches audio queue flush in <100ms.
    """

    def __init__(self, event_bus: EventBus | None = None) -> None:
        self.event_bus = event_bus or get_event_bus()
        self.vad = VoiceActivityDetector()
        self.is_assistant_speaking = False
        self.active_generation_task: asyncio.Task[None] | None = None
        self._on_barge_in_callbacks: list[Callable[[], Any]] = []

    def register_barge_in_callback(self, cb: Callable[[], Any]) -> None:
        self._on_barge_in_callbacks.append(cb)

    def set_assistant_state(self, is_speaking: bool, generation_task: asyncio.Task[None] | None = None) -> None:
        self.is_assistant_speaking = is_speaking
        self.active_generation_task = generation_task

    async def handle_audio_frame(self, pcm_bytes: bytes, request_id: str | None = None) -> dict[str, Any]:
        """
        Process incoming user microphone audio chunk.
        If user starts speaking while assistant is speaking, triggers instant barge-in.
        """
        vad_result = self.vad.process_frame(pcm_bytes)
        event = vad_result["event"]

        if event == "speech_start" and self.is_assistant_speaking:
            logger.info("Barge-in detected: interrupting assistant playback", request_id=request_id)
            await self.trigger_barge_in(request_id=request_id)
            vad_result["barge_in_triggered"] = True
        else:
            vad_result["barge_in_triggered"] = False

        return vad_result

    async def trigger_barge_in(self, request_id: str | None = None) -> None:
        """Immediately abort active assistant generation and notify clients to flush audio."""
        self.is_assistant_speaking = False

        if self.active_generation_task and not self.active_generation_task.done():
            self.active_generation_task.cancel()
            self.active_generation_task = None

        for cb in self._on_barge_in_callbacks:
            try:
                res = cb()
                if asyncio.iscoroutine(res):
                    await res
            except Exception as e:
                logger.warning("Error in barge-in callback", error=str(e))

        await self.event_bus.publish(
            topic="voice",
            event_type="barge_in",
            payload={
                "request_id": request_id,
                "timestamp": time.time(),
                "action": "flush_audio_queue",
            },
        )


class NikoVoiceSynthesizer:
    """
    High-speed English Neural Chibi Voice Synthesizer for NIKO.
    Powered by Edge Neural TTS with high-energy anime pitch modulation (+45Hz) and pace boost.
    Streams synthesized audio chunks in milliseconds with zero cloud tokens.
    """

    def __init__(
        self,
        voice: str | None = None,
        pitch: str | None = None,
        rate: str | None = None,
    ) -> None:
        import os
        # Default to ja-JP-NanamiNeural speaking English with +45Hz (+15% pitch) and +10% rate
        self.voice = voice or os.getenv("NIKO_VOICE", "ja-JP-NanamiNeural")
        self.pitch = pitch or os.getenv("NIKO_VOICE_PITCH", "+45Hz")
        self.rate = rate or os.getenv("NIKO_VOICE_RATE", "+10%")

    async def synthesize_bytes(self, text: str) -> bytes:
        """Synthesize text into MP3 audio bytes using energetic anime configuration."""
        import edge_tts

        clean_text = text.strip()
        if not clean_text:
            return b""

        communicate = edge_tts.Communicate(
            text=clean_text,
            voice=self.voice or "ja-JP-NanamiNeural",
            pitch=self.pitch or "+45Hz",
            rate=self.rate or "+10%",
        )

        chunks: list[bytes] = []
        async for chunk in communicate.stream():
            if chunk.get("type") == "audio" and "data" in chunk:
                chunks.append(chunk["data"])

        return b"".join(chunks)

    async def synthesize_base64(self, text: str) -> str:
        """Synthesize text into base64-encoded audio for direct WebSocket streaming."""
        import base64

        audio_bytes = await self.synthesize_bytes(text)
        if not audio_bytes:
            return ""
        return base64.b64encode(audio_bytes).decode("utf-8")

