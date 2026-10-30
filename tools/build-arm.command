#!/bin/bash
# Cross-builds the ARMv7 (Cortex-A9, QEMU vexpress) Rossini image with Buildroot: kernel 6.12.x, Python, Pillow,
# PyMuPDF, pyphen, wpa_supplicant. Takes 30-60 minutes the first time. Needs a Linux host or the rossini-build container
# (apt: build-essential rsync bc cpio unzip file wget). Output: build/arm/images/{zImage,vexpress-v2p-ca9.dtb,rootfs.ext4}
set -euo pipefail
cd "$(dirname "$0")/.."
BR_VER=2025.02.7
mkdir -p build/arm
[ -d "build/arm/buildroot-$BR_VER" ] || { curl -fsSL "https://buildroot.org/downloads/buildroot-$BR_VER.tar.xz" | tar -xJ -C build/arm; }
# the self-test package fixtures (signed with a throw-away key) are generated on the host
python3 tools/make_arm_fixtures.py
make -C "build/arm/buildroot-$BR_VER" BR2_EXTERNAL="$PWD/build/buildroot" O="$PWD/build/arm" rossini_qemu_armv7_defconfig
make -C build/arm -j"$(nproc 2>/dev/null || sysctl -n hw.ncpu)"
echo "Fertig: build/arm/images"
