## Why

Cited CAMEX clauses with visible guardrails and L1 numbers. L1 already scores offline from a gold set, but the only operator entry is a laptop command: a dump-host run is undocumented, and a host code update replaces an operator results document with the shipped unpublished sample, so staff Calidad L1 cannot defend dump numbers. A dump-host run before ingest would look like dump quality unless the unpublished/sample banner stays.

## What Changes

Nothing is **BREAKING** for `POST /chat` or for the laptop L1 command.

- A dump-host operator path runs the **same** L1 evaluation against the dump index (not a laptop FakeIndex). It forwards the existing suite flags. It is not a second scorer.
- A host code update MUST NOT replace an operator L1 results document with the shipped unpublished sample. First install MAY seed that unpublished sample when no results file exists and MUST NOT seed a published run from another machine.
- After a dump-host L1 run, the serving process MUST reload so staff Calidad L1 shows the stored document. The unpublished/sample banner SHALL remain when that document is labeled unpublished or sample. The browser still MUST NOT compute scores.
- Dump-host L1 stops the serving process for the duration of the run. In-process sessions do not survive. The serving process MUST be running again after the run finishes or fails.
- Refresh still MUST NOT run L1 unless the operator opts in. No HTTP evaluation endpoint. No scheduled L1.
- Judged metrics on the dump host remain optional (skip with a reason when the extra or key is missing). The dump-host helper does not install the judge extra. Code metrics still publish.
- README `## How to run`, the local-dev command catalog, and the remote env seed document laptop vs dump-host L1 in the same change.

## Capabilities

### New Capabilities

(none)

### Modified Capabilities

- `evals-l1`: published staff L1 numbers (Calidad L1 without the unpublished/sample banner) come from an operator run on that dump whose index was ready; the static results document survives a host code update; first install may seed only the unpublished sample.
- `platform`: the dump-host install shares dump and index with L1; an operator MAY run L1 on that host; that run serializes with ingest and refresh, stops serving for its duration, and starts the serving process again on success or failure.
- `assistant-ui`: staff Calidad L1 still reads the static file only; after the serving process reloads it shows that stored document; the unpublished/sample banner follows the file, not the invocation surface.

## Non-goals

- Banxico or any non-`bcra.gob.ar` corpus.
- Next.js v1.
- LlamaIndex.
- Redis.
- Filling the 1990–97 CAMEX catalog hole.
- GitHub-hosted vector index.
- A second evaluation implementation or a distinct “test server” runner. Automated tests stay fakes.
- HTTP evaluation API, Gradio “Run L1”, or scoring in the browser.
- Cron / weekday refresh running L1.
- A paid L1 run as a CI-blocking task.
- A systemd L1 unit (suite flags do not fit a flagless oneshot).
- Moving the static results document off the existing results path.
- Changing chat language-model settings, gold labels, or L1 metric definitions.
- Continuous online evals or scoring live collector traces.
- Installing the judge extra from the dump-host helper.
- A host-provenance field on the results document.

## Impact

- Dump-host helper and laptop SSH wrapper around the existing operator L1 command. Host install templates and rsync excludes. Remote env seed gains commented judge keys. The chat process still MUST NOT load evaluation scoring.
- Chat HTTP API unchanged. Five ports unchanged. Gold file unchanged. Staff accordion still static.
- README How to run, command catalog, and README fence sync. Unit tests with fakes; src coverage stays >= 80%. No paid judge in CI.
