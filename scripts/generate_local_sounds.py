import math
import struct
import wave
from pathlib import Path

SOUNDS_DIR = Path(__file__).resolve().parents[1] / "frontend" / "public" / "sounds"
SOUNDS_DIR.mkdir(parents=True, exist_ok=True)
SAMPLE_RATE = 44100


def write_wav(filename: str, samples: list[float]) -> None:
    path = SOUNDS_DIR / filename
    with wave.open(str(path), "wb") as wav:
        wav.setnchannels(1)  # Mono
        wav.setsampwidth(2)  # 16-bit
        wav.setframerate(SAMPLE_RATE)
        # Convert floats in [-1.0, 1.0] to 16-bit signed PCM
        raw_bytes = bytearray()
        for s in samples:
            clamped = max(-1.0, min(1.0, s))
            int_val = int(clamped * 32767.0)
            raw_bytes.extend(struct.pack("<h", int_val))
        wav.writeframes(raw_bytes)
    print(f"Generated: {path} ({len(samples)} samples, {len(samples)/SAMPLE_RATE:.2f}s)")


def gen_approval_sound() -> list[float]:
    """Attention two-tone chime (A5 -> E6) for confirmation/permission requests."""
    duration = 0.45
    total_samples = int(duration * SAMPLE_RATE)
    samples = []
    f1, f2 = 880.0, 1318.5  # A5 then E6
    for i in range(total_samples):
        t = i / SAMPLE_RATE
        if t < 0.2:
            # First note A5
            env = math.exp(-t * 12.0)
            s = math.sin(2 * math.pi * f1 * t) * env * 0.6
        else:
            # Second note E6
            t2 = t - 0.2
            env = math.exp(-t2 * 9.0)
            s = math.sin(2 * math.pi * f2 * t2) * env * 0.6
        samples.append(s)
    return samples


def gen_message_sound() -> list[float]:
    """Gentle soft chime (C6 -> G6) indicating assistant completed turn."""
    duration = 0.35
    total_samples = int(duration * SAMPLE_RATE)
    samples = []
    f1, f2 = 1046.5, 1567.98
    for i in range(total_samples):
        t = i / SAMPLE_RATE
        if t < 0.15:
            env = math.exp(-t * 16.0)
            s = math.sin(2 * math.pi * f1 * t) * env * 0.5
        else:
            t2 = t - 0.15
            env = math.exp(-t2 * 12.0)
            s = math.sin(2 * math.pi * f2 * t2) * env * 0.5
        samples.append(s)
    return samples


def gen_tool_sound() -> list[float]:
    """Subtle mechanical click/blip indicating background skill/tool execution."""
    duration = 0.12
    total_samples = int(duration * SAMPLE_RATE)
    samples = []
    freq = 660.0
    for i in range(total_samples):
        t = i / SAMPLE_RATE
        env = math.exp(-t * 35.0)
        s = (math.sin(2 * math.pi * freq * t) + 0.3 * math.sin(2 * math.pi * (freq * 2) * t)) * env * 0.45
        samples.append(s)
    return samples


def gen_error_sound() -> list[float]:
    """Low descending tone for errors/failures."""
    duration = 0.35
    total_samples = int(duration * SAMPLE_RATE)
    samples = []
    for i in range(total_samples):
        t = i / SAMPLE_RATE
        freq = 320.0 - (t / duration) * 140.0  # 320Hz down to 180Hz
        env = math.exp(-t * 7.0)
        s = math.sin(2 * math.pi * freq * t) * env * 0.6
        samples.append(s)
    return samples


def gen_click_sound() -> list[float]:
    """Crisp high tactile click for interactive buttons/pet taps."""
    duration = 0.05
    total_samples = int(duration * SAMPLE_RATE)
    samples = []
    for i in range(total_samples):
        t = i / SAMPLE_RATE
        freq = 1800.0 - t * 12000.0
        env = math.exp(-t * 90.0)
        s = math.sin(2 * math.pi * max(100.0, freq) * t) * env * 0.4
        samples.append(s)
    return samples


def gen_wake_sound() -> list[float]:
    """Bright ascending arpeggio for pet wakeup / summon."""
    duration = 0.35
    total_samples = int(duration * SAMPLE_RATE)
    samples = []
    notes = [523.25, 659.25, 783.99, 1046.5]  # C5, E5, G5, C6
    for i in range(total_samples):
        t = i / SAMPLE_RATE
        idx = min(3, int(t / 0.08))
        t_sub = t - idx * 0.08
        env = math.exp(-t_sub * 18.0)
        freq = notes[idx]
        s = math.sin(2 * math.pi * freq * t_sub) * env * 0.5
        samples.append(s)
    return samples


if __name__ == "__main__":
    write_wav("approval.wav", gen_approval_sound())
    write_wav("message.wav", gen_message_sound())
    write_wav("tool.wav", gen_tool_sound())
    write_wav("error.wav", gen_error_sound())
    write_wav("click.wav", gen_click_sound())
    write_wav("wake.wav", gen_wake_sound())
    print("All local sound files generated successfully.")
