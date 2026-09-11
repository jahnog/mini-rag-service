#!/usr/bin/env bash
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$REPO_ROOT"

usage() {
  echo "usage: PROD_BASE_URL=https://public-origin $0 [pytest flags]" >&2
}

if [ -f "$REPO_ROOT/.env" ]; then
  set -a
  # shellcheck disable=SC1091
  . "$REPO_ROOT/.env"
  set +a
fi

if [ -z "${PROD_BASE_URL:-}" ]; then
  usage
  echo "PROD_BASE_URL is required" >&2
  exit 2
fi

# Pytest Origin/Referer must match the public origin, not a laptop loopback origin.
PROD_BASE_URL="${PROD_BASE_URL%/}"
export PROD_BASE_URL
export AUTH_PUBLIC_ORIGIN="$PROD_BASE_URL"

exec uv run pytest --run-prod-smoke -m prod_smoke -q "$@"
