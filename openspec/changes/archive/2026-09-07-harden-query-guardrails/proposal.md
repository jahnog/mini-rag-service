## Why

Cited CAMEX clauses with visible guardrails still rest on rails that mutate the turn before the log, bless hit-prefilled citations as grounding, strip retrieve poison then scan the cleaned text, and match advice or jailbreaks with Spanish/English regexes that prior-turn CAMEX tokens and a multilingual model can walk around.

## What Changes

- Rails return a decision plus a patch; the pipeline applies the patch only when the rule is enforced. Shadow stays `pass` + `would_block` and MUST NOT change the visible answer, citations, finding, or retrieved hits. Unicode normalize always runs before the other input rails.
- **BREAKING**: a non-silencio answer MUST use citations the model produced for this turn (dump id in this turn’s hits; quote a whitespace-normalized substring of that hit). Empty snippets fail. Hit-prefilled citations MUST NOT satisfy cite-or-abstain. Messy JSON that still names a dump id remains usable; omitting usable ids becomes silencio and the draft is hidden.
- Retrieve injection runs on the original chunk and drops on hit. Hygiene only strips leftover role markup on survivors.
- No-advice is a speech-act check with a deontic CAMEX veto, on the latest user utterance and on the answer. Cue lists cover Spanish, English, and close Portuguese / French / Italian / German cognates. Input still short-circuits. Output also blocks a recommendation that is not a quoted span from a this-turn hit.
- Scope is evaluated on the latest user utterance. Prior-turn CAMEX tokens MUST NOT launder an off-topic follow-up. An off-topic denylist hit on that utterance wins even if the same message contains a CAMEX keyword. `punto` alone is not a scope pass. Injection and secrets still run on the composed follow-up used for retrieval.
- Injection stays deterministic. The pattern set includes the specified Spanish/English paraphrases. Chunks use the same backend on original text.
- **BREAKING** (log only): `chat_turn` includes policy version, per-row latency, survived and dropped dump ids, and MUST NOT store secret-shaped tokens in `message`, `answer`, or details.
- Staff trust chips show `enforced` and `would_block`. Usuario still hides the panel.

## Capabilities

### New Capabilities

- `query-logging`: Durable `chat_turn` record already exists in the product; main specs do not yet name it. This change adds completeness and secret-redaction.

### Modified Capabilities

- `guardrails`: decide-then-apply; model-grounded cite-or-abstain; retrieve drop-on-original; speech-act no-advice; scope on latest utterance; always-on normalize; injection paraphrases.
- `query-answering`: stop prefilling hit citations as a pass; messy citation JSON still parses when it names a dump id; omit usable ids → silencio; compose follow-ups for retrieval without laundering scope or no-advice.
- `assistant-ui`: Staff trust panel shows enforced and would-block; Usuario unchanged.

## Non-goals

- Banxico or any non-`bcra.gob.ar` corpus.
- Next.js v1.
- LlamaIndex.
- Redis.
- Filling the 1990–97 CAMEX catalog hole.
- GitHub-hosted vector index.
- Embedding or classifier backends, Llama Guard / Prompt Guard, LLM-as-judge on input, CJK/Arabic language detection, Presidio, a sixth port, markdown/HTML sanitizer rewrite, extra secret shapes beyond the existing `sk-` / `ghp_` detector.

## Impact

- Guardrail pipeline, cite-or-abstain, retrieve rails, no-advice/scope/injection, AnswerQuery citation merge, `chat_turn` payload, staff trust chips.
- Behavior change on empty model citations (today they inherit dump hits).
- No new runtime dependencies. Tests stay offline. Coverage stays >= 80%.
- Sibling change `improve-guardrails` is implemented in the tree and not archived; this change is on that runtime.
