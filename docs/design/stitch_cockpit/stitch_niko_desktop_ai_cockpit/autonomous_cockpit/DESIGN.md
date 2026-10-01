---
name: Autonomous Cockpit
colors:
  surface: '#111316'
  surface-dim: '#111316'
  surface-bright: '#37393d'
  surface-container-lowest: '#0c0e11'
  surface-container-low: '#1a1c1f'
  surface-container: '#1e2023'
  surface-container-high: '#282a2d'
  surface-container-highest: '#333538'
  on-surface: '#e2e2e6'
  on-surface-variant: '#d7c4ad'
  inverse-surface: '#e2e2e6'
  inverse-on-surface: '#2f3034'
  outline: '#9f8e79'
  outline-variant: '#524533'
  surface-tint: '#ffba4b'
  primary: '#ffd59b'
  on-primary: '#442b00'
  primary-container: '#ffb020'
  on-primary-container: '#6b4600'
  inverse-primary: '#815600'
  secondary: '#4ae176'
  on-secondary: '#003915'
  secondary-container: '#00b954'
  on-secondary-container: '#004119'
  tertiary: '#ffd0cc'
  on-tertiary: '#68000a'
  tertiary-container: '#ffa9a3'
  on-tertiary-container: '#a00016'
  error: '#ffb4ab'
  on-error: '#690005'
  error-container: '#93000a'
  on-error-container: '#ffdad6'
  primary-fixed: '#ffddb1'
  primary-fixed-dim: '#ffba4b'
  on-primary-fixed: '#291800'
  on-primary-fixed-variant: '#624000'
  secondary-fixed: '#6bff8f'
  secondary-fixed-dim: '#4ae176'
  on-secondary-fixed: '#002109'
  on-secondary-fixed-variant: '#005321'
  tertiary-fixed: '#ffdad7'
  tertiary-fixed-dim: '#ffb3ad'
  on-tertiary-fixed: '#410004'
  on-tertiary-fixed-variant: '#930013'
  background: '#111316'
  on-background: '#e2e2e6'
  surface-variant: '#333538'
typography:
  headline-lg:
    fontFamily: Inter
    fontSize: 1.75rem
    fontWeight: '600'
    lineHeight: 2.25rem
    letterSpacing: -0.02em
  headline-md:
    fontFamily: Inter
    fontSize: 1.25rem
    fontWeight: '600'
    lineHeight: 1.75rem
    letterSpacing: -0.015em
  headline-sm:
    fontFamily: Inter
    fontSize: 1rem
    fontWeight: '600'
    lineHeight: 1.5rem
    letterSpacing: -0.01em
  body-lg:
    fontFamily: Inter
    fontSize: 0.9375rem
    fontWeight: '400'
    lineHeight: 1.5rem
  body-md:
    fontFamily: Inter
    fontSize: 0.875rem
    fontWeight: '400'
    lineHeight: 1.375rem
  body-sm:
    fontFamily: Inter
    fontSize: 0.8125rem
    fontWeight: '400'
    lineHeight: 1.25rem
  mono-lg:
    fontFamily: JetBrains Mono
    fontSize: 0.875rem
    fontWeight: '500'
    lineHeight: 1.375rem
    letterSpacing: -0.01em
  mono-md:
    fontFamily: JetBrains Mono
    fontSize: 0.8125rem
    fontWeight: '400'
    lineHeight: 1.25rem
  mono-sm:
    fontFamily: JetBrains Mono
    fontSize: 0.6875rem
    fontWeight: '500'
    lineHeight: 1rem
    letterSpacing: 0.02em
  label-caps:
    fontFamily: JetBrains Mono
    fontSize: 0.625rem
    fontWeight: '600'
    lineHeight: 0.875rem
    letterSpacing: 0.08em
rounded:
  sm: 0.125rem
  DEFAULT: 0.25rem
  md: 0.375rem
  lg: 0.5rem
  xl: 0.75rem
  full: 9999px
spacing:
  gutter: 0.75rem
  gutter-md: 1rem
  margin: 1rem
  margin-dock: 0.5rem
  space-xs: 0.25rem
  space-sm: 0.5rem
  space-md: 0.75rem
  space-lg: 1rem
  space-xl: 1.5rem
---

## Brand & Style

This design system defines an austere, mission-critical operational cockpit for high-agency power users commanding local and frontier AI models. Built on principles of precision avionics and industrial telemetry, the interface rejects decorative excess, pastel neon gradients, and diffused glass effects in favor of razor-sharp density, strict visual hierarchy, and mechanical predictability.

The emotional signature is cool-headed authority, extreme responsiveness, and deliberate intent. Surfaces are treated like precision-milled hardware instrumentation: deep graphite matte layers, tactile borders, micro-interactions with immediate mechanical snap, and high-readability monochromatic layouts pierced only by surgical amber telemetry and unambiguous status indicators.

Interactions follow a terminal-grade ethos: low latency, dense information architecture, persistent system telemetry, and unambiguous operational states. Every visual element exists to accelerate cognitive processing and model orchestration.

## Colors

The palette establishes an ultra-low-reflection environment optimized for extended high-focus operational sessions.

### Surface System
- **Canvas Base:** `#0B0C0E` (absolute foundation, deep graphite-black)
- **Surface Level 1:** `#121417` (navigation rails, side panels, persistent shells)
- **Surface Level 2:** `#181B20` (workspace panels, split view chambers, utility docks)
- **Surface Card:** `#1E2228` (interactive modules, telemetry blocks, inspection nodes)
- **Surface Hover:** `#262C34` (immediate tactile feedback state)
- **Structural Stroke / Hairline:** `#262B33` or `rgba(255, 255, 255, 0.08)`

### Signal Accents & Semantics
- **Signal Amber (Primary):** `#FFB020`
  - Glow Core: `rgba(255, 176, 32, 0.25)`
  - Muted Plate: `rgba(255, 176, 32, 0.12)`
  - Trace Stroke: `rgba(255, 176, 32, 0.35)`
- **Telemetry Green (Active / Healthy / Executed):** `#22C55E` (surface tint: `rgba(34, 197, 94, 0.12)`)
- **Warning / Fault Red (Error / Danger / High-Risk Tool):** `#EF4444` (surface tint: `rgba(239, 68, 68, 0.14)`)

### Typographic Contrast
- **Text Dominant:** `#EDEDEE` (high contrast, warm off-white)
- **Text De-emphasized:** `#9CA3AF` (subtitles, parameter keys)
- **Text Ghost:** `#4B5563` (disabled states, inactive rail triggers, structural dividers)

## Typography

The typographic hierarchy enforces a bifurcation between editorial intent and execution telemetry:

1. **System Grotesque (`Inter`):** Assigned to dialogue transcripts, section titles, natural language explanations, and high-level configuration headers. Optimized for high scanning speeds without optical distortion.
2. **Precision Monospace (`JetBrains Mono`):** Strictly enforced across all computational artifacts: telemetry counters, runtime latencies, token consumption tallies, model routing chips, ports, timestamps, parameter keys, code snippets, keyboard shortcut legends, and JSON payload inspect trees.

All caps labels are rendered in monospace with expanded tracking (`0.08em`) to mirror avionics switchgear and data plates.

## Layout & Spacing

The interface employs a persistent application shell designed for wide-aspect and multi-display desktop workstations. 

### Shell Architecture
- **Slim Navigation Rail (Left):** Fixed width of `56px`. Houses model engine switchers and primary module routers: Chat, Dashboard, Usage, Skills, Admin, Settings.
- **Context/Workspace Split:** A flex-column dynamic panel layout with resize handles. Accommodates simultaneous active agent stream and live telemetry/payload inspector side-by-side.
- **Status Deck (Bottom):** Fixed height `28px` docked status rail displaying active LLM provider ping (Gemini / Groq / OpenRouter), memory bounds, local port bindings, and current execution loop count.

### Grid Rhythm
A micro 4px base rhythm dictates all component geometry. Panels dock edge-to-edge separated by crisp 1px borders rather than empty outer margins, optimizing every pixel for data throughput and contextual awareness.

## Elevation & Depth

Visual hierarchy is achieved through strictly controlled mechanical stacking and hairline borders rather than diffuse, floating shadows:

1. **Base Plate (`#0B0C0E`):** Zero elevation, the substrate under all modules.
2. **Structural Tiers (`#121417` -> `#181B20`):** Elevation is expressed by stepped surface luminescence. Each incremental tier advances subtly in tone.
3. **Outlines:** All cards, dialogs, dropdowns, and split panes leverage `1px solid rgba(255, 255, 255, 0.08)` or `#262B33`. 
4. **Focused / Activated Outlines:** Shift directly to `1px solid rgba(255, 176, 32, 0.5)` with an inner/outer drop glow of `0 0 12px rgba(255, 176, 32, 0.15)`.
5. **Modals & Overlays:** `#181B20` surface with `box-shadow: 0 16px 40px -8px rgba(0, 0, 0, 0.8), 0 0 0 1px #262B33`. Backdrop is dimmed with a flat `#000000` at 65% opacity. Diffuse blurs are prohibited to maintain hardware rendering efficiency.

## Shapes

The design system maintains a hard-tooled, compact geometry:
- **Base Components (Inputs, buttons, chips, panels):** `4px` corner radius (`0.25rem`). Gives an intentional, machined aesthetic without brutalist sharpness.
- **Micro Tags, Keycaps, and Telemetry Badges:** `2px` or `3px` corner radius.
- **Status Indicators & 'The Core':** Pure geometric circles (`50%` radius).
- **Interactive Focus Rings:** Conformal to the underlying container border radius with `2px` offset and sharp edge containment.

## Components

### 1. The Core (Signature Autonomous Agent Engine)
A 72px x 72px concentric physical display unit centered in prompt docks or runtime telemetry panels:
- **Architecture:** 3 concentric hair-thin rings (`1px` width) circling an inner luminescent nucleus.
- **State: Idle** — Outer rings stationary; nucleus emits a slow, breathing pulse between `rgba(255,176,32,0.15)` and `rgba(255,176,32,0.35)`.
- **State: Thinking** — Rings decouple into rotating segmented dashes with opposing orbital directions (outer clockwise 4s, middle counter-clockwise 2.5s); nucleus shifts to high-frequency strobe.
- **State: Acting** — Segmented rings lock into geometric quadrants; illuminated tick-marks track active tool steps; Signal Amber intensity at 100% with `box-shadow: 0 0 16px rgba(255, 176, 32, 0.4)`.
- **State: Awaiting Approval** — Rings halt; outer ring snaps to solid Amber; nucleus pulses slowly; centers an unambiguous Amber padlock icon.

### 2. Buttons
- **Primary (Signal Execute):** Background `#FFB020`, text `#0B0C0E`, font weight 600. Hover: `#EAA015`. Active: `#D48F0E`. Zero shadow; instantaneous state transitions.
- **Secondary / Ghost:** Background `transparent`, border `1px solid #262B33`, text `#EDEDEE`. Hover: background `#181B20`, border `#3B424D`.
- **Destructive:** Background `rgba(239, 68, 68, 0.1)`, border `1px solid rgba(239, 68, 68, 0.3)`, text `#EF4444`. Hover: background `#EF4444`, text `#FFFFFF`.
- **Height & Spacing:** Standardized at `28px` (compact) and `34px` (standard). Monospace keyboard shortcuts (`⌘↵`, `ESC`) right-aligned within label bounds.

### 3. Chips & Model Selectors
- Rigid rectangular tags (`22px` height) with `3px` radius. Monospace font.
- **LLM Provider Badges:**
  - *Gemini*: Outline chip with minimal blue-shifted white marker.
  - *Groq*: Outline chip with signal orange-amber dot indicator.
  - *OpenRouter*: Outline chip with slate-cyan marker.
- Text reads explicit identifiers: `groq/llama-3.3-70b-versatile` or `gemini-2.0-flash`.

### 4. Input Fields & Prompt Terminal
- Terminal prompt area on `#121417`, framed with hairline `#262B33`.
- Active focus converts the entire border to `rgba(255, 176, 32, 0.4)`.
- Font: Hybrid (Prompt entry in `Inter`, system parameter prefixes like `@spotify`, `--temperature 0.2` in `JetBrains Mono` with Signal Amber syntax highlighting).

### 5. Checkboxes & Radio Controls
- `14px x 14px` square boxes (`2px` border radius).
- Background `#121417`, border `1px solid #262B33`.
- Checked: Background `#FFB020`, border `#FFB020`, with an internal dark square indicator (for radio) or crisp check glyph in `#0B0C0E`.

### 6. Cards & Inspect Nodes
- Surface `#1E2228`, border `1px solid #262B33`.
- Headers feature a dedicated border-bottom separator with monospace title, latency metrics right-aligned (`412 ms`), and status pill (`DONE` in `#22C55E`).
- Collapsible argument trays showing formatted JSON payload blocks with syntax-highlighted keys and values.

### 7. Micro-Telemetry Bar
- Horizontal dock pinned to module bottoms. Displays:
  `SYS_ACTIVE` (green dot) | `PORT: 7421` | `TOKENS: 4,129/m` | `LATENCY: 84ms` | `PROVIDER: GROQ`