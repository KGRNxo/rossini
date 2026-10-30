#!/bin/bash
# Builds Amazon's published Linux kernels with a modern ARM cross compiler. The sources are third-party GPL-2.0; they are
# fetched, never copied into this repository. Our fixes for GCC 13 / binutils 2.42 live in kernel/patches/.
#   wario  Lab126 3.0.35, i.MX6SL: Kindle PW2/PW3/KV/KT2      (imx60_wario_defconfig)
#   duet   Lab126 3.0.35, i.MX6SL: Kindle Oasis (KOA)          (imx60_duet_defconfig)
#   kt6    Amazon 4.9, MediaTek MT8512: Kindle 2024 "Rossini"  (mt8110-bellatrix_defconfig, dtb mt8110-cava)
# Usage: tools/build-kernel.command [wario|duet|kt6]      CROSS_COMPILE=arm-linux- must be on PATH (Buildroot host/bin works)
# Output: build/kernel/<variant>/{zImage,.config,modules/} (+ dtbs for kt6) and build/kernel/hdr for wario (user headers)
set -euo pipefail
cd "$(dirname "$0")/.."
VARIANT="${1:-wario}"
if [ "$VARIANT" = kt6 ]; then exec "$(dirname "$0")/build-kt6-kernel.sh"; fi
PIN=7ac2585f384573da8cbdcc987a3503e2e6ff1fb4
SRC=build/kernel/src
OUT="$PWD/build/kernel/$VARIANT"
CC="${CROSS_COMPILE:-arm-linux-}"
command -v "${CC}gcc" >/dev/null || { echo "Kein ARM-Cross-Compiler (${CC}gcc) im PATH. Beispiel: PATH=build/arm/host/bin:\$PATH"; exit 1; }
if [ ! -d "$SRC/.git" ]; then
    mkdir -p build/kernel
    git clone --depth 1 https://github.com/katadelos/linux-3.0.35-lab126 "$SRC"
fi
[ "$(git -C "$SRC" rev-parse HEAD)" = "$PIN" ] || { echo "Quelle ist nicht der geprüfte Commit $PIN"; exit 1; }
if ! git -C "$SRC" diff --quiet; then :; else
    for p in kernel/patches/lab126-3.0.35/*.patch; do git -C "$SRC" apply "$PWD/$p"; done
fi
mkdir -p "$OUT"
M="make -C $SRC ARCH=arm CROSS_COMPILE=$CC O=$OUT -j$(nproc 2>/dev/null || sysctl -n hw.ncpu)"
$M "imx60_${VARIANT}_defconfig"
$M zImage modules
$M INSTALL_MOD_PATH="$OUT/modules" modules_install
$M INSTALL_HDR_PATH="$PWD/build/kernel/hdr" headers_install
sha256sum "$OUT/arch/arm/boot/zImage" | tee "$OUT/zImage.sha256"
cp "$OUT/arch/arm/boot/zImage" "$OUT/zImage"
echo "Fertig: $OUT/zImage (NICHT auf einem Gerät getestet)"
