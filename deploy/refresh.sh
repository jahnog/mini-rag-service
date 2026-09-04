#!/bin/bash
set -euo pipefail
exec 9>/run/bcra-rag-job.lock
flock 9
trap 'systemctl start bcra-rag.service || true' EXIT
systemctl stop bcra-rag.service || true
cd __DEPLOY_DIR__
sudo -u __DEPLOY_USER__ __DEPLOY_DIR__/.venv/bin/python -m bcra_rag.jobs.refresh
