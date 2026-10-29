#!/bin/bash
# Reads facts from the connected Kindle's USB volume (read-only). For deeper device facts run tools/hwdiag.sh ON the
# device (needs a shell on it) and attach the output when filling a board profile.
cd "$(dirname "$0")/.."
PY=python3; [ -x .venv/bin/python ] && PY=.venv/bin/python
$PY - "${1:-/Volumes/Kindle}" <<'PYEOF'
import json, sys
from rossini.installer import probe
print(json.dumps(probe.read_facts(sys.argv[1]), indent=1, ensure_ascii=False))
PYEOF
