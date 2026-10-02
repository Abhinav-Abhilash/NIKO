import asyncio
from collections.abc import AsyncGenerator

import pytest

from backend.app.core.events import EventBus
from backend.app.services.sentence_divider import SentenceDivider, split_stream_sentences
from backend.app.services.voice_service import (
    NikoVoiceSynthesizer,
    VoiceActivityDetector,
    VoiceBargeInEngine,
)


def test_sentence_divider_basic() -> None:
    divider = SentenceDivider(min_sentence_length=10)

    # Feeding short token chunks
    s1 = divider.feed("Hello world! ")
    assert s1 == ["Hello world!"]

    s2 = divider.feed("This is NIKO assistant. ")
    assert s2 == ["This is NIKO assistant."]

    # Multi-token sentence with punctuation
    r1 = divider.feed("I am processing ")
    assert r1 == []
    r2 = divider.feed("your query right now.")
    assert r2 == ["I am processing your query right now."]
    r3 = divider.feed(" Let's get started.")
    assert r3 == ["Let's get started."]

    # Flush remaining
    divider.feed(" Final trailing words without dot")
    s4 = divider.flush()
    assert s4 == ["Final trailing words without dot"]


def test_sentence_divider_abbreviations_and_numbers() -> None:
    divider = SentenceDivider(min_sentence_length=5)

    # Should not split on "e.g."
    res1 = divider.feed("Please see e.g. the roadmap. ")
    assert res1 == ["Please see e.g. the roadmap."]

    # Should not split on decimal numbers like "3.14"
    res2 = divider.feed("Pi is approximately 3.14159. Have a good day! ")
    assert res2 == ["Pi is approximately 3.14159.", "Have a good day!"]


@pytest.mark.asyncio
async def test_split_stream_sentences_generator() -> None:
    async def token_generator() -> AsyncGenerator[str, None]:
        tokens = ["Good ", "morning, ", "operator! ", "All ", "systems ", "are ", "operational.\n", "Ready."]
        for t in tokens:
            await asyncio.sleep(0.001)
            yield t

    sentences = [s async for s in split_stream_sentences(token_generator(), min_sentence_length=5)]
    assert len(sentences) >= 2
    assert "Good morning, operator!" in sentences[0]
    assert "Ready." in sentences[-1]


def test_voice_activity_detector_silence_vs_speech() -> None:
    vad = VoiceActivityDetector(energy_threshold=0.01)

    # Silence: zero PCM
    silence_pcm = b"\x00\x00" * 320
    assert vad.calculate_pcm16_rms(silence_pcm) == 0.0
    res_silence = vad.process_frame(silence_pcm)
    assert res_silence["event"] == "silence"
    assert res_silence["is_speaking"] is False

    # Loud audio: alternating high amplitude 16-bit values
    loud_samples = bytearray()
    for _ in range(320):
        loud_samples.extend((16000).to_bytes(2, byteorder="little", signed=True))
    loud_pcm = bytes(loud_samples)

    # Feed loud frames to exceed speech_pad_frames (3)
    vad.process_frame(loud_pcm)
    vad.process_frame(loud_pcm)
    res_speech = vad.process_frame(loud_pcm)
    assert res_speech["is_speaking"] is True
    assert res_speech["event"] in ("speech_start", "speaking")


@pytest.mark.asyncio
async def test_voice_barge_in_engine() -> None:
    bus = EventBus()
    engine = VoiceBargeInEngine(event_bus=bus)

    barge_in_called: bool = False

    def on_barge() -> None:
        nonlocal barge_in_called
        barge_in_called = True

    engine.register_barge_in_callback(on_barge)

    # Set assistant as speaking
    dummy_task = asyncio.create_task(asyncio.sleep(10))
    engine.set_assistant_state(is_speaking=True, generation_task=dummy_task)

    # Loud audio frame to trigger speech_start
    loud_samples = bytearray()
    for _ in range(320):
        loud_samples.extend((18000).to_bytes(2, byteorder="little", signed=True))
    loud_pcm = bytes(loud_samples)

    # Feed frames to trigger speech_start
    await engine.handle_audio_frame(loud_pcm)
    await engine.handle_audio_frame(loud_pcm)
    res = await engine.handle_audio_frame(loud_pcm, request_id="req_test_123")

    assert res["barge_in_triggered"] is True
    assert barge_in_called
    assert bool(dummy_task.cancelling()) or dummy_task.cancelled()
    assert engine.is_assistant_speaking is False

    # Cleanup task
    dummy_task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await dummy_task


@pytest.mark.asyncio
async def test_niko_voice_synthesizer_config_and_synthesis() -> None:
    synth = NikoVoiceSynthesizer()
    assert synth.voice == "ja-JP-NanamiNeural"
    assert synth.pitch == "+45Hz"
    assert synth.rate == "+10%"

    # Empty text returns empty
    assert await synth.synthesize_bytes("") == b""
    assert await synth.synthesize_base64("") == ""

    # Synthesis of short phrase produces valid base64 audio
    b64 = await synth.synthesize_base64("Ready!")
    assert isinstance(b64, str)
    assert len(b64) > 100

