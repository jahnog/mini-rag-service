## Why

Cited CAMEX clauses with visible guardrails and L1 numbers need the dump and index on the deploy host, not on GitHub. The repo already runs locally via `uv` and Docker, but there is no operator path to install the API and jobs on a Linux dump host with the runtime we chose (uv + systemd, not Docker).

## What Changes

Nothing is **BREAKING**.

- Add a workstation operator command that copies the application over SSH to a configured dump host into an operator-supplied install dir, bootstraps poppler/`uv`, syncs a frozen venv, installs process units and a daily refresh schedule, and restarts a single serving worker.
- A second run updates application code and process config, restarts the serving worker, and does not delete the dump, the index, or existing secrets.
- Commit host files in-repo: systemd unit templates for the API, oneshot units and helpers for ingest and refresh, a cron.d file for daily refresh, and a remote env seed (embeddings at a configured OpenAI-compatible URL / `qwen3-embedding-0.6b`, chat LLM xAI Grok).
- Document first deploy, update, SSH local-forward to the bound loopback UI, and on-demand ingest/refresh in README `## How to run`. Keep existing local Docker commands.
- Unit-test the unit files, helpers, cron line, deploy excludes, and README command strings.

## Capabilities

### New Capabilities

- `host-deploy`: Operator SSH deploy and update of a one-worker serving process on the dump host; persistent host dump shared by ingest, refresh, and chat; daily scheduled refresh and on-demand one-shot jobs that do not run concurrently with the serving process; OpenAI-compatible LLM and embedding endpoints that are not hosted on the dump host.

### Modified Capabilities

- None. Existing `platform` shared-dump and empty-index health contracts stay; this change adds the operator host path rather than changing those requirements.

## Non-goals

- Banxico or any non-`bcra.gob.ar` corpus.
- Next.js v1.
- LlamaIndex.
- Redis.
- Filling the 1990–97 CAMEX catalog hole.
- GitHub-hosted vector index.
- Docker on the remote host (Dockerfile/compose stay for local/dev).
- TLS/Caddy, publishing port 8000, k8s/Ansible, systemd timers.
- Running llama.cpp or any embedding/chat model on the dump host.
- Copying a laptop Chroma tree as the source of truth.
- Starting or reverse-tunnelling the embedding server from the deploy command.
- Changing chat, retrieval, or ingest Python.

## Impact

- New `scripts/deploy.sh` and `deploy/` units, helpers, cron.d file, and remote env seed.
- README `## How to run` (deploy, update, local-forward, ingest/refresh host jobs).
- Tests under `tests/` for those files and README strings. `src` coverage stays >= 80%.
- No change to the five ports, composition root, chat API shape, or Gradio UI.
- External: SSH to the dump host; outbound HTTPS to `api.x.ai` and `bcra.gob.ar`; embeddings HTTP to the configured embedding endpoint.
