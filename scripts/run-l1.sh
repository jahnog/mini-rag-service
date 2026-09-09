#!/usr/bin/env bash
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

usage() {
  echo "usage: DEPLOY_HOST=user@dump-host $0 [evals/run_l1.py flags]" >&2
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

ssh -t "$DEPLOY_HOST" sudo "$DEPLOY_DIR/deploy/l1.sh" "$@"
