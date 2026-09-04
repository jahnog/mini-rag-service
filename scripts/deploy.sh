#!/usr/bin/env bash
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

usage() {
  echo "usage: DEPLOY_HOST=user@dump-host $0 [--ingest]" >&2
  echo "optional: DEPLOY_USER, DEPLOY_DIR, or deploy/local.env" >&2
}

_keep_host="${DEPLOY_HOST-}"
_keep_user="${DEPLOY_USER-}"
_keep_dir="${DEPLOY_DIR-}"
if [ -f "$REPO_ROOT/deploy/local.env" ]; then
  set -a
  # shellcheck disable=SC1091
  . "$REPO_ROOT/deploy/local.env"
  set +a
fi
[ -n "$_keep_host" ] && DEPLOY_HOST="$_keep_host"
[ -n "$_keep_user" ] && DEPLOY_USER="$_keep_user"
[ -n "$_keep_dir" ] && DEPLOY_DIR="$_keep_dir"

INGEST=0
while [ $# -gt 0 ]; do
  case "$1" in
    --ingest) INGEST=1 ;;
    -h|--help)
      usage
      exit 0
      ;;
    *)
      usage
      echo "unknown argument: $1" >&2
      exit 2
      ;;
  esac
  shift
done

if [ -z "${DEPLOY_HOST:-}" ]; then
  usage
  echo "DEPLOY_HOST is required" >&2
  exit 2
fi

if [ -z "${DEPLOY_USER:-}" ]; then
  if [[ "$DEPLOY_HOST" == *@* ]]; then
    DEPLOY_USER="${DEPLOY_HOST%%@*}"
  else
    usage
    echo "DEPLOY_USER is required when DEPLOY_HOST has no user@" >&2
    exit 2
  fi
fi

remote() {
  ssh "$DEPLOY_HOST" "$@"
}

if [ -z "${DEPLOY_DIR:-}" ]; then
  DEPLOY_DIR="$(remote 'printf %s "$HOME/bcra-mini-rag"')"
fi

remote sudo apt-get update -qq
remote sudo DEBIAN_FRONTEND=noninteractive apt-get install -y --no-install-recommends \
  poppler-utils curl ca-certificates
remote 'if [ ! -x "$HOME/.local/bin/uv" ]; then curl -LsSf https://astral.sh/uv/install.sh | sh; fi'
remote "mkdir -p '$DEPLOY_DIR'"

rsync -a --delete \
  --exclude '.git/' \
  --exclude '.venv/' \
  --exclude 'data/' \
  --exclude '__pycache__/' \
  --exclude '.env' \
  --exclude '.envrc' \
  --exclude 'deploy/local.env' \
  --exclude 'coverage.xml' \
  --exclude '.coverage' \
  "${REPO_ROOT}/" "${DEPLOY_HOST}:${DEPLOY_DIR}/"

remote "cd '$DEPLOY_DIR' && \$HOME/.local/bin/uv sync --frozen --no-dev"

remote "if [ ! -f '$DEPLOY_DIR/.env' ]; then
  cp '$DEPLOY_DIR/deploy/env.remote.example' '$DEPLOY_DIR/.env'
  chmod 600 '$DEPLOY_DIR/.env'
fi"

if ! remote "grep -qE '^LLM_API_KEY=.+' '$DEPLOY_DIR/.env' && grep -qE '^EMBEDDING_API_KEY=.+' '$DEPLOY_DIR/.env'"; then
  echo "Fill LLM_API_KEY and EMBEDDING_API_KEY in ${DEPLOY_DIR}/.env on ${DEPLOY_HOST}, then re-run." >&2
  echo "skip enable/restart when keys empty" >&2
  exit 1
fi

remote "sed -i \
  -e 's|__DEPLOY_DIR__|${DEPLOY_DIR}|g' \
  -e 's|__DEPLOY_USER__|${DEPLOY_USER}|g' \
  '$DEPLOY_DIR/deploy/bcra-rag.service' \
  '$DEPLOY_DIR/deploy/bcra-rag-ingest.service' \
  '$DEPLOY_DIR/deploy/bcra-rag-refresh.service' \
  '$DEPLOY_DIR/deploy/ingest.sh' \
  '$DEPLOY_DIR/deploy/refresh.sh'"

remote "sudo cp '$DEPLOY_DIR/deploy/bcra-rag.service' /etc/systemd/system/bcra-rag.service
sudo cp '$DEPLOY_DIR/deploy/bcra-rag-ingest.service' /etc/systemd/system/bcra-rag-ingest.service
sudo cp '$DEPLOY_DIR/deploy/bcra-rag-refresh.service' /etc/systemd/system/bcra-rag-refresh.service
sudo cp '$DEPLOY_DIR/deploy/bcra-rag-refresh.cron' /etc/cron.d/bcra-rag-refresh
sudo chmod 644 /etc/systemd/system/bcra-rag.service \
  /etc/systemd/system/bcra-rag-ingest.service \
  /etc/systemd/system/bcra-rag-refresh.service \
  /etc/cron.d/bcra-rag-refresh
sudo systemctl daemon-reload
sudo systemctl enable bcra-rag.service
sudo systemctl restart bcra-rag.service"

if [ "$INGEST" -eq 1 ]; then
  remote "sudo systemctl start bcra-rag-ingest.service"
fi
