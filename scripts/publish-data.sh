#!/usr/bin/env bash
# Publish local data/ over SSH to the production data directory.
# Standalone operator command: rsync over SSH only. Does not restart services.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
LOCAL_OVERLAY="$SCRIPT_DIR/publish-data.local"
DEFAULT_DIR="/srv/bcra-mini-rag/production/current/data"

usage() {
  cat <<EOF >&2
usage: $0 [user@host] [--dry-run]

rsync the contents of the local data directory to:
  ${DEFAULT_DIR}

  user@host     SSH target (overrides PUBLISH_HOST)
  --dry-run     show the transfer plan; write nothing on the remote

env:
  PUBLISH_HOST  SSH target if not passed as argv
  PUBLISH_DIR   remote destination (default: ${DEFAULT_DIR})
  PUBLISH_SRC   local source directory (default: <repo>/data)
  PUBLISH_CHOWN remote owner:group after a sudo copy
                (default: existing dest owner, else the SSH login user)

A gitignored ${LOCAL_OVERLAY} may set those variables.
EOF
}

_keep_host="${PUBLISH_HOST-}"
_keep_dir="${PUBLISH_DIR-}"
_keep_src="${PUBLISH_SRC-}"
_keep_chown="${PUBLISH_CHOWN-}"
if [ -f "$LOCAL_OVERLAY" ]; then
  set -a
  # shellcheck disable=SC1090
  . "$LOCAL_OVERLAY"
  set +a
fi
[ -n "$_keep_host" ] && PUBLISH_HOST="$_keep_host"
[ -n "$_keep_dir" ] && PUBLISH_DIR="$_keep_dir"
[ -n "$_keep_src" ] && PUBLISH_SRC="$_keep_src"
[ -n "$_keep_chown" ] && PUBLISH_CHOWN="$_keep_chown"

DRY_RUN=0
ARGV_HOST=""
while [ $# -gt 0 ]; do
  case "$1" in
  --dry-run) DRY_RUN=1 ;;
  -h | --help)
    usage
    exit 0
    ;;
  --)
    shift
    if [ $# -gt 0 ]; then
      usage
      echo "unknown argument: $1" >&2
      exit 2
    fi
    break
    ;;
  -*)
    usage
    echo "unknown argument: $1" >&2
    exit 2
    ;;
  *)
    if [ -n "$ARGV_HOST" ]; then
      usage
      echo "unknown argument: $1" >&2
      exit 2
    fi
    ARGV_HOST="$1"
    ;;
  esac
  shift
done

if [ -n "$ARGV_HOST" ]; then
  PUBLISH_HOST="$ARGV_HOST"
fi

PUBLISH_DIR="${PUBLISH_DIR:-$DEFAULT_DIR}"
if [ -z "${PUBLISH_SRC:-}" ]; then
  if [ -d "$REPO_ROOT/data" ]; then
    PUBLISH_SRC="$REPO_ROOT/data"
  elif [ -d "$PWD/data" ]; then
    PUBLISH_SRC="$PWD/data"
  else
    usage
    echo "cannot find local data directory (set PUBLISH_SRC)" >&2
    exit 2
  fi
fi
PUBLISH_SRC="$(cd "$PUBLISH_SRC" && pwd)"

if [ -z "${PUBLISH_HOST:-}" ]; then
  usage
  echo "PUBLISH_HOST is required (argv, env, or ${LOCAL_OVERLAY})" >&2
  exit 2
fi

case "$PUBLISH_DIR" in
/*) ;;
*)
  echo "PUBLISH_DIR must be an absolute path: $PUBLISH_DIR" >&2
  exit 2
  ;;
esac

if [ "$PUBLISH_DIR" = "/" ]; then
  echo "refusing to publish to /" >&2
  exit 2
fi

if [[ "$PUBLISH_DIR" == *"'"* ]] || [[ "$PUBLISH_HOST" == *"'"* ]]; then
  echo "PUBLISH_HOST and PUBLISH_DIR must not contain single quotes" >&2
  exit 2
fi

if [ ! -d "$PUBLISH_SRC" ]; then
  echo "missing local data directory: $PUBLISH_SRC" >&2
  exit 2
fi

if ! command -v rsync >/dev/null 2>&1; then
  echo "rsync is required on this machine" >&2
  exit 1
fi

remote() {
  ssh "$PUBLISH_HOST" "$@"
}

echo "publish $PUBLISH_SRC/ -> ${PUBLISH_HOST}:${PUBLISH_DIR}/"

if ! remote 'test -d .'; then
  echo "cannot ssh to $PUBLISH_HOST" >&2
  exit 1
fi

if ! remote 'command -v rsync >/dev/null 2>&1'; then
  echo "rsync is required on $PUBLISH_HOST" >&2
  exit 1
fi

RSYNC_PATH="rsync"
OWNER="${PUBLISH_CHOWN:-}"

if [ "$DRY_RUN" -eq 0 ]; then
  if remote "mkdir -p -- '$PUBLISH_DIR' && test -w '$PUBLISH_DIR'"; then
    RSYNC_PATH="rsync"
  else
    if ! remote 'sudo -n true'; then
      echo "cannot write $PUBLISH_DIR on $PUBLISH_HOST (need write access or passwordless sudo)" >&2
      exit 1
    fi
    remote "sudo -n mkdir -p -- '$PUBLISH_DIR'"
    RSYNC_PATH="sudo -n rsync"
    if [ -z "$OWNER" ]; then
      OWNER="$(remote "sudo -n stat -c '%U:%G' -- '$PUBLISH_DIR'")"
      if [ "$OWNER" = "root:root" ]; then
        OWNER="$(remote 'printf %s "$(id -un):$(id -gn)"')"
      fi
    fi
  fi
fi

RSYNC_ARGS=(
  -a
  --delete
  --no-owner
  --no-group
  --human-readable
  --info=progress2
)
if [ "$DRY_RUN" -eq 1 ]; then
  RSYNC_ARGS+=(--dry-run)
fi

rsync "${RSYNC_ARGS[@]}" \
  --rsync-path="$RSYNC_PATH" \
  "${PUBLISH_SRC}/" \
  "${PUBLISH_HOST}:${PUBLISH_DIR}/"

if [ "$DRY_RUN" -eq 0 ] && [ -n "$OWNER" ]; then
  if [[ "$OWNER" == *"'"* ]]; then
    echo "PUBLISH_CHOWN must not contain single quotes" >&2
    exit 2
  fi
  remote "sudo -n chown -R -- '$OWNER' '$PUBLISH_DIR'"
  echo "remote owner $OWNER"
fi

if [ "$DRY_RUN" -eq 1 ]; then
  echo "dry-run only; remote data was not changed"
else
  echo "published to ${PUBLISH_HOST}:${PUBLISH_DIR}/"
fi
