# Audio Assets & Third-Party Credits

This document catalogues all local audio assets packaged with the NIKO desktop client, documenting their exact provenance, synthesis source, author, and licensing terms.

---

## Local Sound Effects (`frontend/public/sounds/`)

All sound effects used by the NIKO virtual companion and desktop overlay are 100% locally synthesized PCM WAV audio generated deterministically via procedural mathematical harmonics (`scripts/generate_local_sounds.py`). No remote audio assets, third-party binary blobs, or proprietary sound libraries are bundled.

| File Path | Description | Synthesis Generator / Formula | Author | License | Verification Status |
|---|---|---|---|---|---|
| `frontend/public/sounds/approval.wav` | Urgent two-tone chime (A5 880Hz to E6 1318.5Hz) alerting the operator that an autonomous tool execution is awaiting human permission | Exponential decayed sine wave harmonics (`scripts/generate_local_sounds.py::gen_approval_sound`) | NIKO Project Contributors | CC0 1.0 Universal (Public Domain Dedication) | Verified (100% Procedural) |
| `frontend/public/sounds/message.wav` | Gentle soft chime (C6 1046.5Hz to G6 1568Hz) signifying that the assistant has concluded inference | Decayed pure sine tones (`scripts/generate_local_sounds.py::gen_message_sound`) | NIKO Project Contributors | CC0 1.0 Universal (Public Domain Dedication) | Verified (100% Procedural) |
| `frontend/public/sounds/tool.wav` | Tactile mechanical chirp (660Hz base + 1320Hz overtone) indicating background skill/tool invocation | Exponential damped dual harmonic (`scripts/generate_local_sounds.py::gen_tool_sound`) | NIKO Project Contributors | CC0 1.0 Universal (Public Domain Dedication) | Verified (100% Procedural) |
| `frontend/public/sounds/error.wav` | Low descending pitch tone (320Hz sliding down to 180Hz) signaling a rejected or failed operation | Linear downward frequency sweep (`scripts/generate_local_sounds.py::gen_error_sound`) | NIKO Project Contributors | CC0 1.0 Universal (Public Domain Dedication) | Verified (100% Procedural) |
| `frontend/public/sounds/click.wav` | Crisp tactile click (1800Hz transient) for interactive buttons and pet companion taps | High-frequency rapidly decaying impulse (`scripts/generate_local_sounds.py::gen_click_sound`) | NIKO Project Contributors | CC0 1.0 Universal (Public Domain Dedication) | Verified (100% Procedural) |
| `frontend/public/sounds/wake.wav` | Bright ascending arpeggio (C5, E5, G5, C6) when the companion awakens or receives user attention | Sequential 4-note modal arpeggio (`scripts/generate_local_sounds.py::gen_wake_sound`) | NIKO Project Contributors | CC0 1.0 Universal (Public Domain Dedication) | Verified (100% Procedural) |

---

## Unverified License Audits

- **Flagged Assets**: None. All packaged audio files originate directly from the repository's open-source mathematical synthesis scripts and carry unencumbered CC0 / Public Domain terms.
- **Remote Sound Fetching**: Strictly forbidden. The client never attempts to stream or download audio assets from external endpoints or unauthenticated CDNs.
