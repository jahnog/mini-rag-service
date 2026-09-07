## 1. Pipeline

- [x] 1.1 Add `RailPatch` and attach it to `RailResult`. `GuardrailPipeline.run_named` applies the patch only when enforced. Shadow remaps `block` to `pass` + `would_block` and MUST NOT apply the patch. Remove inner enforce branching in `ChunkMappingRail`. Unit tests: order, short-circuit, shadow does not mutate `ctx`.

- [x] 1.2 Always Unicode-normalize latest `raw`/`text` before remaining input rails even when normalize is not enforced. Keep the normalize log row. Unit test: zero-width jailbreak still blocks when normalize `enforce` is false.

## 2. Cite-or-abstain

- [x] 2.1 `AnswerQuery` sets citations from model-produced ids in this turn’s hits only. Tighten `_quote_ok` (non-empty `quote in body` only). Append `Fuente:` after cite-or-abstain. Sidecar `top_k` still from hits. Retarget `test_empty_model_citations_still_use_dump_hits` and the omit-ids Gherkin/unit path to silencio. Keep messy named-id cases green.

## 3. Retrieve

- [x] 3.1 Policy order: `chunk-injection` then `chunk-hygiene`. Hygiene strips only role markup. Injection scores original text and drops. Unit tests: planted jailbreak plus CAMEX text is dropped; drop-all is silencio and the language model is not called.

## 4. Input rails

- [x] 4.1 Scope and no-advice (input) run on the latest normalized utterance. Injection and secrets run on composed follow-up. Scope: denylist wins over CAMEX hints; drop `punto` as a sufficient hint. Unit tests: weather+BCRA blocks; `y el clima…` after CAMEX blocks; named A / liquidación still pass.

- [x] 4.2 Speech-act no-advice cues (ES/EN + PT/FR/IT/DE cognates) with deontic veto on the same string; same on the answer; output also blocks a recommendation not quoted from a this-turn hit. Expand injection paraphrases on `RegexBackend`. Unit tests: `y si compro`, dolarizar, French cognate block; `deberán liquidar` does not; ignora/disregard/forget/print-prompt block.

## 5. Logging and staff UI

- [x] 5.1 Redact `sk-` / `ghp_` in `chat_turn` `message`, `answer`, and details. Emit policy version, per-row latency, survived and dropped dump ids. Staff trust payload/markdown show `enforced` and `would_block`. Usuario hide unchanged. Unit tests: secret not stored; policy version present; staff chip includes would-block.

## 6. Quality gate

- [x] 6.1 `uv run ruff check .`, `uv run mypy src`, `uv run pytest -q --cov=src --cov-report=term-missing --cov-report=xml` green; src coverage >= 80%.

- [x] 6.2 At least three named unit tests per `policy.yaml` rail, plus extra tests for extra verdicts/fields/triggers. Inter-rail file covers order, short-circuit, shadow, field split, and retrieve/output chains.
