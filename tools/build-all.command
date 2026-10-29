#!/bin/bash
# Builds everything that can be built: unit-test-independent image build (squashfs slots, initramfs, recovery,
# signed update packages, checksums). Runs natively on Linux, inside the rossini-build container on macOS.
set -euo pipefail
cd "$(dirname "$0")/.."
if [ "$(uname)" = "Darwin" ]; then
    docker image inspect rossini-build >/dev/null 2>&1 || { echo "Zuerst ./tools/setup-macos.command ausführen."; exit 1; }
    docker run --rm --platform linux/amd64 -v "$PWD":/rossini -w /rossini rossini-build python3 tools/build_images.py "$@"
else
    python3 tools/build_images.py "$@"
fi
echo "Artefakte: build/out (SHA256SUMS prüfen)"
