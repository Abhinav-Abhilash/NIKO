# NIKO: Vision & Architecture

## The Pet IS the AI

In NIKO, the desktop character pet is not a cosmetic mascot—**the pet IS NIKO**, the embodied desktop AI assistant and its primary human interface.

### Principles
1. **Embodied Presence**:
   - NIKO lives directly on the user's desktop as an embodied companion with physical state awareness (idle, thinking, executing tools, waiting for approvals, speaking, cooling down).
   - Interactions occur directly with the pet: clicking the pet opens a lightweight inline text input beside it, voice conversations stream responses in its dynamic speech bubble, and human-in-the-loop approvals are asked in its embodied voice.
2. **Optional Overlay HUD**:
   - The hovering acrylic overlay card is an optional power-user HUD mode (`pet-overlay` or `overlay-only`).
   - By default (`pet-only`), NIKO operates entirely through the lightweight embodied character on the desktop.
3. **Local Telemetry & Zero Token Waste**:
   - All idle animations, physical gaze tracking, posture state transitions, blinking, and audio chimes run purely locally. Zero LLM tokens or API calls are consumed for idle presence.
   - LLM quota is spent only when the user explicitly queries or commands NIKO.
4. **Customizable Identity & Persona**:
   - The companion's name and persona are user-configurable in settings (default: NIKO) and dynamically shape system prompts and interaction styles.
