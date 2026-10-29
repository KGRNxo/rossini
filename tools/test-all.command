#!/bin/bash
# Runs all tests: unit + integration on the host, QEMU boot-chain tests in the Linux environment.
# Usage: ./tools/test-all.command [--no-qemu]
set -uo pipefail
cd "$(dirname "$0")/.."
PY=python3; [ -x .venv/bin/python ] && PY=.venv/bin/python
fail=0
echo "== Unit- und Integrationstests"
$PY -m unittest discover -s tests -t . -p 'test_*.py' -k unit -k integration 2>&1 | tail -n 6 || fail=1
if [ "${1:-}" != "--no-qemu" ]; then
    echo "== QEMU-Bootkette (dauert einige Minuten)"
    if [ "$(uname)" = "Darwin" ]; then
        docker run --rm --platform linux/amd64 -v "$PWD":/rossini -w /rossini rossini-build \
            sh -c "python3 tools/build_images.py && python3 -m unittest tests.qemu.test_qemu" 2>&1 | tail -n 8 || fail=1
    else
        [ -f build/out/vmlinuz ] || python3 tools/build_images.py
        $PY -m unittest tests.qemu.test_qemu 2>&1 | tail -n 8 || fail=1
    fi
fi
[ $fail = 0 ] && echo "ALLE AUSGEFÜHRTEN TESTS BESTANDEN (Hardwaretests: tests/hardware/README.md, nicht automatisierbar)" || { echo "FEHLER"; exit 1; }
