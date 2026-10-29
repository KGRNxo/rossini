#!/bin/bash
# One-time setup of the Rossini development environment on macOS (Apple Silicon or Intel).
# Installs Homebrew packages and a Python venv. The Linux image build runs inside a container
# (Colima + Docker), because busybox/squashfs/cpio tooling and the QEMU kernel are Linux-only.
set -euo pipefail
cd "$(dirname "$0")/.."
say() { printf '\033[1m==> %s\033[0m\n' "$*"; }
command -v brew >/dev/null || { echo "Homebrew fehlt. Installation: https://brew.sh"; exit 1; }
say "Homebrew-Pakete"
brew install python@3.13 qemu colima docker git e2fsprogs 2>&1 | tail -n 3
say "Python-Umgebung (.venv)"
/opt/homebrew/bin/python3.13 -m venv .venv 2>/dev/null || python3 -m venv .venv
.venv/bin/pip install --quiet --upgrade pip
.venv/bin/pip install --quiet -r requirements.txt
say "Linux-Buildumgebung (Colima, x86_64-Container für QEMU-Images)"
colima status >/dev/null 2>&1 || colima start --cpu 4 --memory 6 --disk 30
docker build --platform linux/amd64 -t rossini-build -f tools/Dockerfile.build . 2>&1 | tail -n 3
say "Fertig. Weiter mit ./tools/build-all.command"
