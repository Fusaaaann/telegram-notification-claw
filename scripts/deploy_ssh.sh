#!/usr/bin/env bash
set -euo pipefail

# Mock SSH deployment script (DO NOT auto-run).
# This is a template you can customize.

REMOTE_HOST=${REMOTE_HOST:-"your.server"}
REMOTE_USER=${REMOTE_USER:-"ubuntu"}
REMOTE_DIR=${REMOTE_DIR:-"/opt/reminder-bot"}
SERVICE_NAME=${SERVICE_NAME:-"reminder-bot"}

echo "[MOCK] Would rsync project to $REMOTE_USER@$REMOTE_HOST:$REMOTE_DIR"
echo "rsync -av --exclude .venv --exclude __pycache__ ./ $REMOTE_USER@$REMOTE_HOST:$REMOTE_DIR"

echo "[MOCK] Would install deps on remote and configure systemd"
cat <<CMD
ssh $REMOTE_USER@$REMOTE_HOST <<'SSH'
  set -e
  cd $REMOTE_DIR
  ./scripts/install_deps.sh
  # TODO: write systemd unit file and enable it
  # sudo systemctl daemon-reload
  # sudo systemctl enable --now $SERVICE_NAME
SSH
CMD
