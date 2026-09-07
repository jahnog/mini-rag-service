## Why

Cited CAMEX clauses with visible guardrails still only exercise a handful of English and Spanish regex hits, so standard jailbreak paraphrases, German overrides, and CAMEX-looking over-refusal prompts are not in the test contract.

## What Changes

- A labeled, offline probe corpus (OpenAI-eval JSONL shape) covers OWASP LLM Top 10 families that map onto existing rails. Every mocked user query is a language triplet: English, Spanish, and German.
- Injection paraphrases expand to German override/reveal forms and to `do anything now`, developer mode, `ahora eres` / `du bist jetzt`, and new-instructions templates. Encoded payloads (base64, ROT13, leetspeak, homoglyph, split) stay documented misses, not a decoder rail.
- Scope blocks German `Wetter` as weather. CAMEX hint, follow-up, and deontic-veto lists are unchanged.
- XSTest-style over-refusal prompts rewritten for CAMEX (ignore the cepo, instructions of A 3500, show the MULC definition) MUST pass injection in all three languages.

## Capabilities

### New Capabilities

- None.

### Modified Capabilities

- `guardrails`: injection paraphrases in English, Spanish, and German; scope weather includes `Wetter`; labeled probe suite is the regression contract for those paraphrases and for over-refusal.

## Non-goals

- Banxico or any non-`bcra.gob.ar` corpus.
- Next.js v1.
- LlamaIndex.
- Redis.
- Filling the 1990–97 CAMEX catalog hole.
- GitHub-hosted vector index.
- Hugging Face downloads, Garak-in-CI, Llama Guard / Prompt Guard, decoder rail, toxicity/hate/CSAM, German CAMEX lexicon, German follow-up prefixes, CJK/Arabic language detection.

## Impact

- `RegexBackend` injection patterns, scope denylist (`Wetter`), optional German no-advice cues (`soll ich`, pesos parken).
- New `tests/fixtures/guardrail_probes.jsonl` and `tests/test_guardrail_probes.py`. Existing mechanism tests stay.
- No new runtime dependencies. Tests stay offline. Coverage stays >= 80%.
- Sibling changes `improve-guardrails` and `harden-query-guardrails` are implemented in the tree and not archived; this change is on that runtime.
