#!/usr/bin/env bash
# Laptop cron wrapper for production smoke. Emails PROD_SMOKE_NOTIFY_TO or
# LIVE_EMAIL via AUTH_SMTP_* only when the suite fails or times out.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

LOG_DIR="${ROOT}/data/logs"
mkdir -p "$LOG_DIR"
LOG="${LOG_DIR}/prod-smoke-cron.log"
LOCK="${LOG_DIR}/prod-smoke-cron.lock"
RUN_LOG="${LOG_DIR}/prod-smoke-cron.last.log"

export PATH="${HOME}/.local/bin:/usr/bin:/bin:${PATH:-/usr/bin:/bin}"

if [[ -z "${DBUS_SESSION_BUS_ADDRESS:-}" && -S "/run/user/$(id -u)/bus" ]]; then
  export DBUS_SESSION_BUS_ADDRESS="unix:path=/run/user/$(id -u)/bus"
fi

if command -v direnv >/dev/null && [[ -f "${ROOT}/.envrc" ]]; then
  eval "$(direnv export bash)"
fi

if [[ -f "${ROOT}/.env" ]]; then
  set -a
  # shellcheck disable=SC1091
  . "${ROOT}/.env"
  set +a
fi

_expand() {
  local val="${1:-}"
  if [[ "$val" =~ ^\$\{([A-Za-z_][A-Za-z0-9_]*)\}$ ]]; then
    printf '%s' "${!BASH_REMATCH[1]:-}"
  else
    printf '%s' "$val"
  fi
}

AUTH_SMTP_PASSWORD="$(_expand "${AUTH_SMTP_PASSWORD:-}")"
LIVE_IMAP_PASSWORD="$(_expand "${LIVE_IMAP_PASSWORD:-}")"
PHOENIX_API_KEY="$(_expand "${PHOENIX_API_KEY:-}")"
LLM_API_KEY="$(_expand "${LLM_API_KEY:-}")"
EMBEDDING_API_KEY="$(_expand "${EMBEDDING_API_KEY:-}")"
export AUTH_SMTP_PASSWORD LIVE_IMAP_PASSWORD PHOENIX_API_KEY LLM_API_KEY EMBEDDING_API_KEY

if [[ -z "${PROD_SMOKE_NOTIFY_TO:-}" && -n "${LIVE_EMAIL:-}" ]]; then
  export PROD_SMOKE_NOTIFY_TO="${LIVE_EMAIL}"
fi

exec 9>"$LOCK"
if ! flock -n 9; then
  echo "$(date -Is) skip: already running" | tee -a "$LOG"
  exit 0
fi

START="$(date +%s)"
set +e
timeout --foreground --signal=TERM --kill-after=30s 15m \
  "${ROOT}/scripts/run-prod-smoke.sh" -q >"$RUN_LOG" 2>&1
CODE=$?
set -e
DURATION="$(( $(date +%s) - START ))"
{
  echo "$(date -Is) exit=${CODE} duration=${DURATION}s"
  cat "$RUN_LOG"
} >>"$LOG"

if [[ "$CODE" -eq 0 ]]; then
  exit 0
fi

python3 "${ROOT}/scripts/notify_prod_smoke_failure.py" \
  --exit-code "$CODE" \
  --duration "$DURATION" \
  --log "$RUN_LOG" || echo "$(date -Is) notify failed" >>"$LOG"

exit "$CODE"
