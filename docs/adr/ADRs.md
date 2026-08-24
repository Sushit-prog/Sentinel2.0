# ADR-001: Provider-agnostic model layer replaces direct LangChain-Groq usage

**Status:** Accepted · **Date:** 2026-08

## Context
The hackathon codebase hard-wired `langchain_groq.ChatGroq` into business
logic with no timeouts, retries, cost visibility, or output validation.
Groq's 2026 catalog also deprecated the Llama models we defaulted to,
breaking the app at runtime.

## Decision
Own the abstraction: `backend/core/llm/` defines our interface
(`complete`, `extract`), a Groq adapter, routing (strong/fast tiers),
retry/backoff, sliding-window rate limiting, daily token budget, JSON-schema
structured outputs with one repair round, and a `FakeLLMClient` for offline
tests. LangChain/LangGraph were removed entirely.

## Consequences
+ Provider/model swaps are config changes (proven live: llama→gpt-oss).
+ Deterministic testing without network; 81-test suite runs in seconds.
− We maintain ~250 lines the framework would have provided.
− Agent-graph ergonomics lost — accepted: audit showed our "graphs" were
  linear chains; explicit functions trace better.

# ADR-002: Storage = SQLite-default SQLAlchemy + Postgres path; Neo4j dropped

Neo4j ran with an unbounded in-memory fallback and no session tagging;
cross-module correlation used fuzzy embeddings over IDs. Replaced by:
SQLAlchemy models (`cases/traces/entities/events/jobs`), exact normalized
entity resolution as the correlation join key, SQLite default, Postgres for
production (validator enforces). NetworkX handles ring analysis in-process.

# ADR-003: Selective, bounded verification sampling

Farquhar et al. (Nature 2024) inspire consistency-based uncertainty, but
full semantic entropy needs an entailment model. We implemented K-sample
label-consistency on the fast tier. Benchmark ablation showed unconditional
sampling suppressed recall (0.394) at 3x latency; shipped design verifies
only sub-0.90-confidence verdicts and bounds the confidence penalty at 30%.
Full NLI clustering remains future work.

# ADR-004: Module surgery

Removed: WhatsApp Shield (UI sugar), GeoIntel's random-coordinate heatmap
(`random.choice` was assigning incident locations - fictional intelligence),
CURRENCYGuard's "vision LLM" framing (model never saw images).
Kept/demoted: currency screening as honest heuristics with INCONCLUSIVE
abstention and embedded disclaimers. Every surviving component justifies
itself via benchmark or security posture.
