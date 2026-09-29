# ADR 0002: Cryptographic Approval Binding

## Status
Accepted

## Context
When an AI assistant requests confirmation to perform high-impact actions (such as launching applications, triggering reminders, or adjusting system state), a critical security flaw is Time-of-Check to Time-of-Use (TOCTOU) argument tampering: the user could approve an action displaying one set of parameters while a race condition or compromised message executes different parameters. Furthermore, approval decisions must never be reused or applied after a sensible timeout.

## Decision
1. Compute a deterministic SHA-256 hash (`args_hash`) over canonical JSON (sorted keys, compact separators) representing the exact arguments presented to the owner in the approval modal.
2. Store this hash in the `approvals` table tied 1:1 to the `tool_call_id`.
3. Before executing the action upon approval, verify that `compute_args_hash(actual_args) == approval.args_hash`.
4. Approvals are strictly single-use and transition to `approved`, `denied`, or `expired`. Any attempt to reuse or decide an expired or already-decided approval is rejected.

## Consequences
- **Positive**: Complete auditability, tamper-proof execution, single-use guarantees.
- **Negative**: Requires canonical JSON hashing overhead (negligible in microseconds).
