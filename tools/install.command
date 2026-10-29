#!/bin/bash
# Rossini installation assistant (macOS). Identifies the connected reader, backs up user data and installs ONLY if
# the device model is released. Currently no model is released: the assistant refuses and writes a diagnose report.
set -euo pipefail
cd "$(dirname "$0")/.."
PY=python3; [ -x .venv/bin/python ] && PY=.venv/bin/python
MOUNT="${1:-}"
if [ -z "$MOUNT" ]; then
    MOUNT=$(ls -d /Volumes/Kindle* 2>/dev/null | head -n1 || true)
fi
[ -n "$MOUNT" ] && [ -d "$MOUNT" ] || { echo "Kein Kindle gefunden. Gerät per USB verbinden oder Pfad angeben: install.command /Volumes/Kindle"; exit 1; }
$PY -m rossini.installer --mount "$MOUNT" ${2:+--image "$2"} ${3:+--pubkey "$3"}
