# SENTINEL Threat Model (v2)

Scope: the API service and its pipelines. Assets: citizen PII, verdict
integrity, alert integrity, provider budget.

## Adversary classes

1. **Malicious submitter** — crafts message text to manipulate analysis.
2. **Analyst misuse** — legitimate API user extracting stored PII.
3. **Upstream provider compromise/failure** — Groq outage or tampering.
4. **Evidence poisoning** — previously ingested scam patterns carry
   attacker-controlled text into future prompts (indirect injection).

## Attack surface & controls

| Threat | Vector | Control | Test |
|---|---|---|---|
| Direct prompt injection | message text | Quarantined extractor with data-not-directions system contract; schema-only output; no tools at any LLM stage; prescreen signals hidden from privileged stage | `test_adversarial.py` |
| Indirect injection via evidence | retrieved pattern text in prompts | Evidence redacted (`redact()`), truncated, numbered; verdict citations constrained to item indices; policy gate is code, not model | `evidence.py`, `_build_evidence_block` |
| Alert manipulation | model-authored action text | Citizen alerts are template-only; regression test after adversarial suite caught this exact leak pre-ship | `test_injected_text_never_authors_citizen_alert` |
| Verdict forgery ("say benign") | obedient injected model output | Rule component of fused risk persists even against an obeying model; CRITICAL requires agreement 1.0; emission gated by code | `test_injection_cannot_force_legitimate_verdict` |
| PII at rest | stored case/event text | `redact()` before persistence (phones/OTP/cards/UPI/email); full text exists only in-flight; logs never receive raw inputs | `test_redact.py` |
| Budget exhaustion / DoS-by-cost | spamming analyze | Daily token guard → BudgetExceeded → degraded path; per-identity rate limit; input length caps at validation layer | `test_budget_exhaustion_degrades_not_crashes`, middleware tests |
| Provider failure | outage/malformed JSON | Retry+backoff; non-retryable errors wrapped as ProviderUnavailable → conservative rules-only result, flagged `degraded=true` | live-demonstrated during rate-limit event |
| Unauthorized access | missing key | API-key middleware (constant-time compare); required by config validator in production; health/docs stay open for probes | middleware tests |

## Residual risks (accepted, documented)

- The privileged stage still sees raw message text inside a MESSAGE block;
  this is deliberate (verdict quality) and bounded by: no tools, schema
  constraint, verification sampling, template alerts, deterministic gates.
  Full information-flow control (CaMeL-style) is future work.
- Verification samples measure fast-model self-consistency, not truth.
- Per-process rate limiting; horizontal deployments need Redis or similar.
