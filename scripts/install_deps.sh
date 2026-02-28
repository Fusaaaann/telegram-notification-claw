#!/usr/bin/env bash
set -euo pipefail

# Mock install script (DO NOT auto-run).
# Creates a venv and installs requirements.

PY=${PYTHON:-python3}
VENV_DIR=${VENV_DIR:-.venv}
REQ=${REQ:-requirements.txt}

"$PY" -m venv "$VENV_DIR"
"$VENV_DIR/bin/pip" install --upgrade pip
"$VENV_DIR/bin/pip" install -r "$REQ"

echo "Done: dependencies installed into $VENV_DIR"
