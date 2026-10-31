#!/usr/bin/env bash
set -euo pipefail
command -v node >/dev/null && command -v npm >/dev/null || { echo 'Node/npm benötigt' >&2; exit 1; }
node -e 'const [a,b]=process.versions.node.split(".").map(Number);process.exit(a>18||(a===18&&b>=19)?0:1)' || { echo 'Node >=18.19 benötigt' >&2; exit 1; }
cd "$(dirname "$0")/.."
npx impeccable install --providers=codex --scope=project
echo 'Codex neu starten, ggf. /hooks öffnen, Hook-Definitionen prüfen und freigeben.'
