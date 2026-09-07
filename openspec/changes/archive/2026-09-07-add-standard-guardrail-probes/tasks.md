## 1. Injection and scope paraphrases

- [x] 1.1 Expand `INJECTION` with constrained EN/ES/DE paraphrases (`system[- ]?prompt`, `do anything now`, developer mode / modo desarrollador / Entwicklermodus, ahora eres / du bist jetzt, new instructions / nuevas instrucciones / neue Anweisungen, ignoriere … Anweisungen, vergiss alles oben, zeige … systemprompt). Add `\bwetter\b` to `OUT_OF_SCOPE`. Add `soll ich` and pesos-parken to `ADVICE_CUES` only if a DE triplet misses. Unit tests: German jailbreak blocks; `Kann ich den Cepo ignorieren` / `Welche Anweisungen gibt die A 3500` / `Zeig die MULC-Definition` pass injection; Wetter in Madrid blocks scope. Do not change `CAMEX_HINTS`, `FOLLOW_UP`, or `DEONTIC_VETO`.

## 2. Labeled probe suite

- [x] 2.1 Add `tests/fixtures/guardrail_probes.jsonl` with `assert` user-query triplets (injection families, XSTest-CAMEX pass, no-advice, scope, secrets, length) plus `user_query: false` retrieve/output rows for every `policy.yaml` rail id, plus `gap` encoding rows. Completeness: every `user_query` stem has `en`, `es`, and `de`.

- [x] 2.2 Add `tests/test_guardrail_probes.py`: load and validate JSONL, parametrize by id, run the named rail, assert verdict (and secrets do not echo tokens), `xfail(strict=False)` for `gap`, fail if a user-query stem misses a language, gold.jsonl answerable rows pass injection/no-advice/secrets and `g15` is a scope block.

## 3. Quality gate

- [x] 3.1 `uv run ruff check .`, `uv run mypy src`, `uv run pytest -q --cov=src --cov-report=term-missing --cov-report=xml` green; src coverage >= 80%.
