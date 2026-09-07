## Context

See proposal.md Why. Runtime already has one `GuardrailPipeline` (input / retrieve / output), packaged `policy.yaml`, `AnswerQuery` composition of follow-ups, hit-prefilled citations, retrieve hygiene-then-injection, regex no-advice/scope/injection, and structlog `chat_turn`. Five ports unchanged. This change is on the `improve-guardrails` runtime (that sibling change is not archived).

## Goals / Non-Goals

**Goals:**

- Decide-then-apply so shadow does not mutate `RailContext`.
- Cite-or-abstain on model-produced this-turn quotes only.
- Retrieve injection on original chunk text; hygiene only on survivors.
- Scope and no-advice on the latest utterance; injection on composed text.
- Speech-act no-advice with a deontic veto; always-on Unicode normalize.
- Complete, secret-redacted `chat_turn`; staff chips for enforced / would_block.

**Non-Goals:**

- Sixth port, embedding/classifier backends, LLM-as-judge on input, CJK detection, markdown sanitizer rewrite, extra secret shapes, ingest/refresh changes.

## Decisions

### Decision: RailPatch, apply only if enforced

`Rail.run` reads `ctx` and returns `RailResult` plus optional `RailPatch` (`text`, `raw`, `answer`, `finding`, `citations`, `hits`, `dropped_ids`). `GuardrailPipeline` applies the patch only when `global_enforce and rail.enforce`. Shadow remaps `block` → `pass` + `would_block` and does not apply warn/redact/block patches. `ChunkMappingRail` no longer branches on `self.enforce` internally. Alternative: copy `ctx` per rail (allocates every turn).

### Decision: Normalize is not shadowable

`AnswerQuery` always NFKC + zero-width strips `raw` and the latest utterance before secrets / no-advice / injection / scope, even if `normalize.enforce` is false. The normalize log row still appears. Alternative: fail closed if policy disables normalize (less flexible for tests).

### Decision: Latest vs composed text

Keep `ctx.raw` as the latest utterance (post-normalize). After compose, `ctx.text` is the retrieval query. Length uses latest raw. No-advice (input) and scope use latest. Injection and secrets use composed. Retrieve uses composed `ctx.text`. Alternative: two compose paths (ceremony).

### Decision: Cite model ids only; messy JSON still counts

`AnswerQuery` sets `ctx.citations` from `draft.citations` whose `id` is in `ctx.turn_ids`. `_citations_from_hits` is not a pass condition. `_quote_ok` requires a non-empty `quote in body`. `Fuente:` is appended after cite-or-abstain. Sidecar `top_k` still comes from hits. LLM adapter messy-JSON parse stays. Alternative: NLI grounding (non-goal).

### Decision: Injection before hygiene

Policy order: `chunk-injection` then `chunk-hygiene`. Hygiene strips only `SYSTEM:`, `<|im_start|>`, HTML comments. Jailbreak phrases are injection, scored on original text.

### Decision: Speech-act no-advice

Cues (deliberation/recommendation, ES/EN + PT/FR/IT/DE cognates) AND NOT a deontic CAMEX veto on the same string. Output uses the same check on the answer, plus block if the cue is not a quoted span from a this-turn hit. Input still short-circuits. Alternative: retrieve-then-refuse for advice questions (spec still forbids LLM on a blocked advice question).

### Decision: Scope denylist wins; `punto` is not enough

On the latest utterance, `OUT_OF_SCOPE` blocks even when `CAMEX_HINTS` also match. Drop `punto` from sufficient hints. Prior-turn tokens are not an allowlist. A session follow-up prefix (`y`, `and`, `ese`, …) that is not on the denylist still passes so retrieval can use the composed query (`y ese punto?` in, `y el clima…` out).

### Decision: HTTP vs logs

`GuardrailVerdict` HTTP shape stays. Latency, policy version, survived/dropped ids, and secret redaction live on `chat_turn`. Staff `trust_payload` adds `enforced` and `would_block`.

### Decision: IBM 1–4 take/leave (unchanged)

| Take | Leave |
|---|---|
| Structured JSON; FastAPI; prompt with last_refresh / to_as_of | Flask; model bake-off |
| RAG loop; Gradio | LlamaIndex; LangGraph agent |
| Chroma + metadata filters | Recommender |
| Vector search; parent = get_section | Second index |

### Decision: Slip order

Never cut: decide-then-apply, model cite-or-abstain, retrieve drop-on-original, scope/no-advice on latest, unit tests, coverage >= 80%.

Slip-first: deontic scan, embedding advice backend, extra secret shapes.

## Risks / Trade-offs

- [Empty model citations → silencio] → intended; messy named ids still pass.
- [Speech-act false positives on “liquidar dólares”] → deontic veto on the same utterance.
- [CJK jailbreak + BCRA bait] → residual; no language model on input.
- [Shadow sanitize no longer strips in shadow] → intended; enforce to strip.

## Migration Plan

No dump rebuild. Next API start loads packaged policy (injection before hygiene). Rollback: revert the change. Archive `improve-guardrails` separately so main specs are not stuck on v1.

## Open Questions

None.
