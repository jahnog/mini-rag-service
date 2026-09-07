## 1. Pipeline core

- [x] 1.1 Add `domain/guardrails/` types (`Rail`, `RailContext`, `RailResult`, policy models), `GuardrailPipeline`, `ChunkMappingRail`, `TracedRail`, `NoOpTracer`, `InjectionBackend` + `RegexBackend`. Unit tests: order, short-circuit, shadow `would_block`, unknown id fails at build. AnswerQuery still on v1.
- [x] 1.2 Package `src/bcra_rag/guardrails/policy.yaml` (hatch force-include). Adapter `load_policy`. `RAIL_BUILDERS` + `build_guardrails` in composition. Settings: `guardrails_policy_path`, `max_context_chars`, `llm_timeout_s`.

## 2. Migrate v1

- [x] 2.1 Move no-advice, injection, scope, cite-or-abstain, freeze-honesty onto Strategies. Delete `V1_RULES` / `complete_v1_log` / `_all_pass`. Hang one pipeline on `ChatApp`; `handle_turn` passes it into `AnswerQuery`. Gherkin and existing rail tests green.

## 3. Retrieve stage

- [x] 3.1 `ChunkHygieneRail`, `ChunkInjectionRail`, `ContextBudgetRail`. Drop-one vs drop-all silencio. Fake chunk rail test. Delimited data-only prompt on survivors; retrieved text not in system prompt. Unit tests for planted SYSTEM: and empty survivors.

## 4. New turn rails

- [x] 4.1 Length on raw, normalize, compose, then secrets / no-advice / injection / scope on composed text. Secrets + no-advice on the answer. This-turn + quote cite. Prompt-leak fingerprints (not schema key names). Unsafe-output (ANSI, tool-shaped tags). Markdown sanitize (HTML, javascript/data, non-bcra.gob.ar images/links). `llm_timeout_s` on `LlmAdapter`. Unit tests for each; benign pass on answerable gold rows.

## 5. Log and staff UI

- [x] 5.1 Extend `GuardrailVerdict` (stage, enforced, would_block, redact, skipped). Emit retrieve + generate steps. Enrich `chat_turn` (policy version, latency, survived/dropped ids, llm_called). Never fake-pass skipped work; never echo secrets.
- [x] 5.2 Staff trust panel grouped by stage; CSS for redact/skipped. Jailbreak: injection block, retrieve/generate skipped, freeze/sanitize ran on refusal. Usuario hide unchanged. Update Gherkin.

## 6. Collector and How to run

- [x] 6.1 Optional `otel` extra; fail-open register; OpenAI instrumentor; fake-exporter test. No live collector in default pytest.
- [x] 6.2 README How to run + `.env.example` collector keys. Sibling Phoenix serve documented as `uvx`. Keep the live tree free of container-runtime artifacts.

## 7. Quality gate

- [x] 7.1 `uv run ruff check .`, `uv run mypy src`, `uv run pytest -q --cov=src --cov-report=term-missing --cov-report=xml` green; src coverage >= 80%.

