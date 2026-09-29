# ADR 0003: Autonomy Trust Tiers and the Provenance Rule

## Status
Accepted

## Context
A personal assistant must balance user autonomy and safety without lecturing, refusing commands, or acting as an obstacle. However, adversarial prompt injections (originating from untrusted web pages, OCR text, or files) pose a legitimate threat if they can coerce the model into modifying the host system.

## Decision
1. Security exists to stop external adversaries and injected content, not to restrict the owner. System prompts contain no moralizing or arbitrary topic hedges.
2. Every skill has a configurable autonomy policy (`ask`, `auto`, `auto+log`) editable in the Admin Panel. Default tiers (`SAFE`, `CONFIRM`, `BLOCKED`) are defaults only and user-overridable.
3. **The Provenance Rule**:
   - Actions directly prompted by the owner execute at the chosen autonomy without extra friction.
   - Actions proposed by the LLM downstream of reading untrusted external data (tagged with `<untrusted_data>`) are flagged with `external_untrusted` provenance. Non-destructive actions execute with a toast and undo window; state-altering actions require interactive confirmation.

## Consequences
- **Positive**: Full autonomy for the user while isolating host state from indirect prompt injections.
- **Negative**: Requires provenance tracking through message and tool execution chains.
