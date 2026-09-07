## Context

See proposal.md Why. Runtime already has a `GuardrailPipeline` (input / retrieve / generate / output), `RegexBackend` for injection on query and chunks, speech-act no-advice, scope on the latest utterance, and mechanism tests in `tests/test_guardrails.py` plus `tests/test_guardrail_interactions.py`. Five ports, composition root, ingest/refresh, router, chunking A/B, session memory, and host-side refresh are unchanged.

## Goals / Non-Goals

**Goals:**

- Labeled offline JSONL probe corpus mapped to existing rail ids.
- Every `user_query` family is an EN/ES/DE triplet.
- Expand `INJECTION` and `Wetter` so German and standard-template `assert` rows are honest.
- Document Garak-style encodings as `gap` (`xfail(strict=False)`).

**Non-Goals:**

- Decoder rail, second backend, Hugging Face, Garak CLI.
- Expanding `CAMEX_HINTS`, `FOLLOW_UP`, or `DEONTIC_VETO`.
- Rewriting `evals/gold.jsonl` into German.

## Decisions

### Decision: JSONL corpus + named-rail runner, not full AnswerQuery

Each row names one `rail` and expected verdict. Hits/answers are optional JSON. Alternative: only grow `test_guardrails.py` (unreviewable as a suite; no completeness check).

### Decision: `user_query` flag drives language tripling

Retrieve chunk text stays Spanish dump language. Output markup (`<script>`, ANSI) is `user_query: false`. Alternative: triple every row including XSS (noise).

### Decision: constrained German injection, not stems

Patterns require override/reveal verb + instruction/prompt object (`ignoriere … Anweisungen`, `vergiss alles oben`, `zeige … systemprompt`). Alternative: `ignorier` stem — over-blocks `Kann ich den Cepo ignorieren`.

### Decision: gap rows instead of failing encodings

Base64/ROT13/leetspeak/homoglyph/split stay `status: gap`. Alternative: add a decoder — violates non-goals.

### Decision: IBM 1–4 take/leave (unchanged)

| Take | Leave |
|---|---|
| Structured JSON; FastAPI; prompt with last_refresh / to_as_of | Flask; model bake-off |
| RAG loop; Gradio | LlamaIndex; LangGraph agent |
| Chroma + metadata filters | Recommender |
| Vector search; parent = get_section | Second index |

### Decision: Slip order

Never cut: EN/ES/DE user-query triplets, over-refusal pass triplets, constrained German injection, coverage >= 80%, tests offline.

Slip-first: extra Gherkin beyond one scenario, pesos-parken cue if `sollte` already catches the DE advice triplet.

## Risks / Trade-offs

- [German `Anweisungen` in CAMEX questions] → require override verbs; XSTest pass `Welche Anweisungen gibt die A 3500` is CI-blocking.
- [`zeig` matching MULC definition] → require `systemprompt` / `system-prompt` object.
- [`you are now` / `du bist jetzt` false positives] → keep existing EN breadth; DE matches that bar; gold sweep guards ES/EN.
- [Gap xfail later starts passing] → `strict=False` so a later backend can flip them.

## Migration Plan

No dump rebuild. Next API start loads the same packaged policy with a wider regex. Rollback: revert the change.

## Open Questions

None.
