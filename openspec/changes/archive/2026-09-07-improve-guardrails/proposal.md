## Why

Cited CAMEX clauses with visible guardrails and L1 numbers still rest on five hardcoded regexes and a fake “all pass” log: paraphrased jailbreaks, retrieved poison, invented quotes, and answer-side advice are not real controls, and staff cannot see which step ran.

## What Changes

- One request-path guardrail pipeline with four stages (input, retrieve, generate, output). Policy YAML enables, disables, and shadows each rail.
- **BREAKING** (additive HTTP fields): each guardrail verdict gains `stage`, `enforced`, `would_block`, and verdicts `redact` and `skipped`. The staff trust panel lists every enabled rail plus retrieve/generate; skipped work is never stamped `pass`.
- Input rails: length on the raw body, Unicode normalize, secrets, no-advice, injection, scope. Injection and scope run on the composed follow-up.
- Retrieve stage scans **each** hit (hygiene + injection). Drop a poisoned chunk; zero survivors is silencio and the language model is not called. Survivors are wrapped as data-only with a random delimiter.
- Output rails: cite-or-abstain (this-turn dump ids **and** quote substring), freeze-honesty, no-advice on the answer, secrets on the answer, prompt-leak fingerprints, unsafe-output (ANSI / tool-shaped tags), markdown sanitize.
- Optional OpenTelemetry export to a sibling Phoenix process for local and dump-host eval; `chat.log` stays the durable sink.
- **BREAKING** (behavior): a citation id that exists in the dump but was not retrieved this turn, or a quote that is not in that hit, becomes silencio.

## Capabilities

### New Capabilities

- None. Observability stays on existing query-logging and platform; no new product surface besides the staff log and optional collector.

### Modified Capabilities

- `guardrails`: staged pipeline; shadow/enforce; document scan; new rails; skipped/redact; staff log lists every enabled step.
- `query-answering`: composed follow-up is railed; retrieved clauses scanned; delimited prompt; context budget; drop-all silencio.
- `assistant-ui`: Staff (IA) trust panel is the pipeline log (grouped by stage). Usuario still hides it.
- `query-logging`: policy version; stage/enforced/would_block/latency on `chat_turn`; secrets not echoed.
- `platform`: optional OTLP (fail-open); sibling `uvx` Phoenix process; `max_context_chars`; `llm_timeout_s`.

## Non-goals

- Banxico or any non-`bcra.gob.ar` corpus.
- Next.js v1.
- LlamaIndex.
- Redis.
- Filling the 1990–97 CAMEX catalog hole.
- GitHub-hosted vector index.
- ProtectAI / Prompt Guard / Llama Guard weights, Presidio, NeMo Colang, MiniLM rerank, NLI, tenant ACL, tools, paying CI for Phoenix evals.

## Impact

- `AnswerQuery`, `schemas.GuardrailVerdict`, Gradio trust panel, `chat.log` fields, Settings (`max_context_chars`, `llm_timeout_s`).
- Optional extra `otel` (Phoenix SDK + OpenAI instrumentor). Phoenix server is `uvx`, not an app dependency.
- Unit and Gherkin tests; src coverage stays >= 80%. README How to run names Phoenix serve and the extra.
- Host: optional systemd unit for Phoenix on loopback; existing API unit unchanged aside from `.env` keys.
