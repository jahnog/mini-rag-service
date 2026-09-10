#!/usr/bin/env bash
# Publish local data/ and evals/l1.json over SSH to the production state tree.
# Standalone operator command: rsync over SSH only. Does not restart services.
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
LOCAL_OVERLAY="$SCRIPT_DIR/publish-data.local"
DEFAULT_DIR="/var/lib/bcra-mini-rag/production/data"
DEFAULT_L1="$(dirname "$DEFAULT_DIR")/evals/l1.json"

usage() {
  cat <<EOF >&2
usage: $0 [user@host] [--dry-run]

rsync the contents of the local data directory to:
  ${DEFAULT_DIR}
and the local L1 results file to:
  ${DEFAULT_L1}

  user@host     SSH target (overrides PUBLISH_HOST)
  --dry-run     show the transfer plan; write nothing on the remote

env:
  PUBLISH_HOST     SSH target if not passed as argv
  PUBLISH_DIR      remote data destination (default: ${DEFAULT_DIR})
  PUBLISH_SRC      local source directory (default: <repo>/data)
  PUBLISH_L1       remote L1 file path
                   (default: sibling evals/l1.json of PUBLISH_DIR)
  PUBLISH_L1_SRC   local L1 file (default: <repo>/evals/l1.json)
  PUBLISH_CHOWN    remote owner:group after a sudo copy
                   (default: existing dest owner, else the SSH login user)

A gitignored ${LOCAL_OVERLAY} may set those variables.
Does not restart services.
EOF
}

_keep_host="${PUBLISH_HOST-}"
_keep_dir="${PUBLISH_DIR-}"
_keep_src="${PUBLISH_SRC-}"
_keep_l1="${PUBLISH_L1-}"
_keep_l1_src="${PUBLISH_L1_SRC-}"
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
[ -n "$_keep_l1" ] && PUBLISH_L1="$_keep_l1"
[ -n "$_keep_l1_src" ] && PUBLISH_L1_SRC="$_keep_l1_src"
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

strip_trailing_slashes() {
  local v="$1"
  while [ -n "$v" ] && [ "$v" != "/" ] && [[ "$v" == */ ]]; do
    v="${v%/}"
  done
  printf '%s' "$v"
}

PUBLISH_DIR="${PUBLISH_DIR:-$DEFAULT_DIR}"
PUBLISH_DIR="$(strip_trailing_slashes "$PUBLISH_DIR")"
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

if [ -z "${PUBLISH_L1_SRC:-}" ]; then
  if [ -f "$REPO_ROOT/evals/l1.json" ]; then
    PUBLISH_L1_SRC="$REPO_ROOT/evals/l1.json"
  elif [ -f "$PWD/evals/l1.json" ]; then
    PUBLISH_L1_SRC="$PWD/evals/l1.json"
  else
    usage
    echo "cannot find local evals/l1.json (set PUBLISH_L1_SRC)" >&2
    exit 2
  fi
fi
if [ ! -f "$PUBLISH_L1_SRC" ]; then
  echo "missing local L1 file: $PUBLISH_L1_SRC" >&2
  exit 2
fi
PUBLISH_L1_SRC="$(cd "$(dirname "$PUBLISH_L1_SRC")" && pwd)/$(basename "$PUBLISH_L1_SRC")"

if [ -z "${PUBLISH_L1:-}" ]; then
  PUBLISH_L1="$(dirname "$PUBLISH_DIR")/evals/l1.json"
fi
PUBLISH_L1="$(strip_trailing_slashes "$PUBLISH_L1")"
L1_PARENT="$(dirname "$PUBLISH_L1")"

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

case "$PUBLISH_L1" in
/*) ;;
*)
  echo "PUBLISH_L1 must be an absolute path: $PUBLISH_L1" >&2
  exit 2
  ;;
esac

if [ "$PUBLISH_DIR" = "/" ]; then
  echo "refusing to publish to /" >&2
  exit 2
fi

if [ "$PUBLISH_L1" = "/" ] || [ "$L1_PARENT" = "/" ]; then
  echo "refusing to publish L1 to /" >&2
  exit 2
fi

if [[ "$PUBLISH_DIR" == *"'"* ]] || [[ "$PUBLISH_HOST" == *"'"* ]] || [[ "$PUBLISH_L1" == *"'"* ]]; then
  echo "PUBLISH_HOST, PUBLISH_DIR, and PUBLISH_L1 must not contain single quotes" >&2
  exit 2
fi

if [ ! -d "$PUBLISH_SRC" ]; then
  echo "missing local data directory: $PUBLISH_SRC" >&2
  exit 2
fi

if [ ! -f "$PUBLISH_L1_SRC" ]; then
  echo "missing local L1 file: $PUBLISH_L1_SRC" >&2
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
echo "publish $PUBLISH_L1_SRC -> ${PUBLISH_HOST}:${PUBLISH_L1}"

if command -v python3 >/dev/null 2>&1; then
  if python3 -c 'import json,sys; d=json.load(open(sys.argv[1],encoding="utf-8")); sys.exit(0 if isinstance(d,dict) and (d.get("unpublished") or d.get("sample")) else 1)' "$PUBLISH_L1_SRC" 2>/dev/null; then
    echo "warning: local L1 is unpublished/sample; uploading anyway" >&2
  fi
fi

if ! remote 'test -d .'; then
  echo "cannot ssh to $PUBLISH_HOST" >&2
  exit 1
fi

if ! remote 'command -v rsync >/dev/null 2>&1'; then
  echo "rsync is required on $PUBLISH_HOST" >&2
  exit 1
fi

OWNER="${PUBLISH_CHOWN:-}"

prepare_remote_dir() {
  local dest="$1"
  _dest_rsync_path="rsync"
  if [ "$DRY_RUN" -eq 1 ]; then
    return
  fi
  if remote "mkdir -p -- '$dest' && test -w '$dest'"; then
    _dest_rsync_path="rsync"
    return
  fi
  if ! remote 'sudo -n true'; then
    echo "cannot write $dest on $PUBLISH_HOST (need write access or passwordless sudo)" >&2
    exit 1
  fi
  remote "sudo -n mkdir -p -- '$dest'"
  _dest_rsync_path="sudo -n rsync"
  if [ -z "$OWNER" ]; then
    OWNER="$(remote "sudo -n stat -c '%U:%G' -- '$dest'")"
    if [ "$OWNER" = "root:root" ]; then
      OWNER="$(remote 'printf %s "$(id -un):$(id -gn)"')"
    fi
  fi
}

prepare_remote_dir "$PUBLISH_DIR"
RSYNC_PATH="$_dest_rsync_path"

RSYNC_ARGS=(
  -a
  --delete
  --no-owner
  --no-group
  --human-readable
  --info=progress2
)
L1_RSYNC_ARGS=(
  -a
  --no-owner
  --no-group
  --human-readable
  --info=progress2
)
if [ "$DRY_RUN" -eq 1 ]; then
  RSYNC_ARGS+=(--dry-run)
  L1_RSYNC_ARGS+=(--dry-run)
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

prepare_remote_dir "$L1_PARENT"
L1_RSYNC_PATH="$_dest_rsync_path"

rsync "${L1_RSYNC_ARGS[@]}" \
  --rsync-path="$L1_RSYNC_PATH" \
  "$PUBLISH_L1_SRC" \
  "${PUBLISH_HOST}:${PUBLISH_L1}"

if [ "$DRY_RUN" -eq 0 ] && [ -n "$OWNER" ]; then
  if [[ "$OWNER" == *"'"* ]]; then
    echo "PUBLISH_CHOWN must not contain single quotes" >&2
    exit 2
  fi
  remote "sudo -n chown -- '$OWNER' '$PUBLISH_L1'"
fi

if [ "$DRY_RUN" -eq 1 ]; then
  echo "dry-run only; remote data was not changed"
else
  echo "published to ${PUBLISH_HOST}:${PUBLISH_DIR}/"
  echo "published L1 to ${PUBLISH_HOST}:${PUBLISH_L1}"
fi
