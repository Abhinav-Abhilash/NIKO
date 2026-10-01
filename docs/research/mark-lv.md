# Mark-LV Architecture, Features, & Failure Analysis

> **Notice:** This document is produced under clean-room research guidelines. Mechanisms are analyzed conceptually and described in original prose. No source code, prompt templates, or assets were copied. Mark-LV is licensed under CC BY-NC 4.0.

---

### 1. Repository Overview & Architecture Summary

**Mark-LV** is a desktop voice assistant and computer automation platform built in Python. It features a custom Tkinter/PyVista HUD interface, local wake word detection, multi-provider LLM fallback ladders, system control actions, action undo history, and a local SQLite memory store.

```
+-----------------------------------------------------------------------------------+
|                            DESKTOP HUD INTERFACE (ui.py)                          |
|  - CustomTkinter Transparent Window   - 3D PyVista/OpenGL Face Mesh Avatar        |
|  - Audio Waveform Visualization       - Voice / Text Chat Widget                  |
+-----------------------------------------------------------------------------------+
                                         ^ | (Tkinter Event Loop / Queues)
                                         | v
+-----------------------------------------------------------------------------------+
|                              CORE ENGINE (main.py)                                |
|  [core/wake_word.py & audio_devices.py] [core/gemini.py]                         |
|    - Picovoice Porcupine / PyAudio        - Model Ladder & Provider Fallback     |
|    - Audio Device Input/Output Selection                                          |
|                                                                                   |
|  [core/echo.py]                         [core/confirm.py & core/undo.py]          |
|    - Speaker Audio Suppression Guard      - Risk Confirmation Dialog             |
|                                           - Action Undo Log & Reversal Stack     |
|                                                                                   |
|  [core/action_loader.py & plugin_loader.py] [memory/memory_manager.py]           |
|    - Dynamic Skill & Action Registries    - Local SQLite Fact & Context Store    |
+-----------------------------------------------------------------------------------+
```

#### Core Mechanical Architecture
- **Monolithic Controller (`main.py`):** Acts as the central orchestrator, initializing audio threads, wake word listeners, model clients, and action execution loops.
- **UI & 3D Mesh Avatar (`ui.py`):** Built using CustomTkinter for window management and PyVista/VTK for 3D face mesh rendering with viseme lip-sync animations.
- **Model Fallback Ladder (`core/gemini.py`):** Implements multi-model fallback. Primary requests target Gemini 2.0 Flash; if a 429 rate limit or quota exception occurs, it falls back sequentially to Gemini 1.5 Flash, Gemini 1.5 Pro, or Groq.
- **Echo Guard (`core/echo.py`):** Suppresses microphone input while TTS audio is playing to prevent the assistant's own voice output from triggering speech recognition.
- **Confirmation Gate (`core/confirm.py`):** Classifies actions into risk tiers (`SAFE`, `CONFIRM`, `DENY`). For risky actions, it displays a confirmation dialog requesting user confirmation.
- **Undo Subsystem (`core/undo.py`):** Maintains a stack of executed desktop/file actions (`file_controller`, `open_app`). Each action implements `execute()` and `undo()` methods.
- **Wake Word Engine (`core/wake_word.py`):** Integrates Picovoice Porcupine (`pvporcupine`) to continuously listen to local audio frames and trigger speech recognition upon detecting "Hey Jarvis" or "Mark".

---

### 2. Feature Mechanics & Implementation Analysis

#### A. Model Ladder & Failover (`core/gemini.py`)
- **Mechanism:** Wraps LLM calls in a try-except loop. When an API exception occurs (e.g. HTTP 429 quota exhaustion or server error), the client catches the exception, updates an internal provider index, and retries the prompt against the next model in the priority list.

#### B. Echo Suppression Guard (`core/echo.py`)
- **Mechanism:** Monitors TTS playback state. When TTS audio starts playing on the speaker device, `echo.py` sets a thread-safe boolean flag `is_speaking = True` and temporarily mutes audio buffer processing in the STT listener. Once playback finishes, it resets `is_speaking = False`.

#### C. Action Undo & History Stack (`core/undo.py`)
- **Mechanism:** Implements an action history stack. Reversible skills (such as moving files or opening apps) register an undo state payload containing original file paths or process IDs. When the user says "undo that", `undo.py` pops the latest action and executes its corresponding `undo()` method.

#### D. Dynamic Plugin Loader (`core/plugin_loader.py`, `core/action_loader.py`)
- **Mechanism:** Inspects the `actions/` and `plugins/` directories at startup, dynamically importing Python modules that subclass the base action class and registering their schema definitions into the LLM system prompt.

---

### 3. Failure Modes, Real-World Bugs, & Flaws

Based on code analysis of `main.py`, `ui.py`, `core/gemini.py`, `core/echo.py`, and `actions/`:

1. **Monolithic Architecture & Tkinter UI Freezes (`ui.py`, `main.py`):**
   - *Flaw:* `ui.py` contains nearly 6,000 lines in a single file combining OpenGL 3D mesh rendering, event queues, and widget layouts. Heavy synchronous operations (such as LLM network requests or file index scans) executed on or near the Tkinter mainloop cause frequent UI freezing and unresponsiveness.
2. **Echo Guard Eliminates User Interruption (`core/echo.py`):**
   - *Flaw:* By hard-muting the microphone during TTS playback, the system completely disables user interruption / barge-in. Users cannot stop a long spoken response without using a keyboard shortcut.
3. **Fragile Automation via Hardcoded PyAutoGUI Coordinates (`actions/computer_control.py`):**
   - *Flaw:* Computer control relies on `pyautogui` mouse clicks and hardcoded screen pixel coordinates. Changing display scale, resolution, or window positioning causes automation scripts to click incorrect UI targets, causing unintended clicks.
4. **Vulnerable Confirmation Gate Without Provenance or HMAC (`core/confirm.py`):**
   - *Flaw:* Approvals do not track action provenance or bind request IDs. A prompt injection attack embedded in a file name or web search result can trick the LLM into auto-confirming destructive operations without cryptographic validation.
5. **Incomplete & Unsafe Undo Stack (`core/undo.py`):**
   - *Flaw:* Destructive operations (such as file deletions or system setting modifications) are not backed up before execution. If an action fails mid-execution, the undo stack becomes corrupted, leaving the host system in an inconsistent state.

---

### 4. Key Lessons & Architectural Guidance for NIKO

1. **Decoupled Architecture:** Keep NIKO's React 19 / Tauri v2 frontend completely decoupled from the FastAPI backend supervisor over IPC/WebSocket. Never mix UI rendering with heavy agent loops.
2. **Full-Duplex Interruption over Hard-Muting:** Avoid Mark-LV's hard-muting echo guard. Instead, use full-duplex VAD interruption (`silero`) with server-side stream cancellation so users can interrupt NIKO naturally.
3. **Robust Action Reversal & Reversible Approvals:** Extend NIKO's existing 5-second undo window (`ApprovalService`) with shadow-copy backups before executing destructive file skills.
4. **Resilient Vision & OS Automation:** Avoid fragile pixel coordinate clicks (`pyautogui`). Rely on structured OS APIs, UI Automation trees, and allowlisted CLI executables.
