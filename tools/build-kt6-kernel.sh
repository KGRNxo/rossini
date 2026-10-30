#!/bin/bash
# Kindle 2024 "Rossini" kernel (Linux 4.9-lab126, MediaTek). Called by build-kernel.command kt6.
set -euo pipefail
cd "$(dirname "$0")/.."
URL=https://s3.amazonaws.com/kindledownloads/Kindle_src_5.19.6_4832540042.tar.gz
SHA=e5acecaf45a2ec133e41aa49531e883ffb4bf79b57e1754ec09828395e354040
W=build/kernel/kt6
CC="${CROSS_COMPILE:-arm-linux-}"
command -v lzop >/dev/null || { echo "lzop fehlt (apt install lzop / brew install lzop): der Kernel wird LZO-komprimiert."; exit 1; }
command -v "${CC}gcc" >/dev/null || { echo "Kein ARM-Cross-Compiler (${CC}gcc) im PATH."; exit 1; }
mkdir -p "$W"
if [ ! -f "$W/source.tar.gz" ]; then curl -fL -o "$W/source.tar.gz" "$URL"; fi
echo "$SHA  $W/source.tar.gz" | sha256sum -c - 2>/dev/null || echo "$SHA  $W/source.tar.gz" | shasum -a 256 -c -
if [ ! -d "$W/src/.git" ]; then
    tar -xzf "$W/source.tar.gz" -C "$W" --wildcards 'gplrelease/linux-4.9.tar.gz' 'gplrelease/uboot.tar.gz'
    mkdir -p "$W/src" "$W/uboot" && tar -xzf "$W/gplrelease/linux-4.9.tar.gz" -C "$W/src" && tar -xzf "$W/gplrelease/uboot.tar.gz" -C "$W/uboot"
    git -C "$W/src" init -q && git -C "$W/src" add -A >/dev/null && git -C "$W/src" -c user.email=b@b -c user.name=b commit -qm "Amazon source release 5.19.6 (Kindle 2024)"
    for p in kernel/patches/amazon-rossini-4.9/*.patch; do git -C "$W/src" apply "$PWD/$p"; done
    # The tree enables -Werror in ~120 Makefiles; GCC 13 flags code written for GCC 5-7. Behaviour is unchanged by dropping it.
    grep -rlP -- "-Werror(?![=\\w-])" "$W/src" --include="Makefile*" --include="Kbuild*" --include="*.mk" | grep -v "/Documentation/" \
        | xargs sed -i -E 's/(^|[[:space:]])-Werror([[:space:]]|$)/\1\2/g; s/\+=-Werror/+=/'
fi
OUT="$PWD/$W/out"
mkdir -p "$OUT"
export KCFLAGS="-Wno-error -Wno-attribute-alias -Wno-array-compare -Wno-int-to-pointer-cast -Wno-maybe-uninitialized"
M="make -C $W/src ARCH=arm CROSS_COMPILE=$CC HOSTCC='gcc -fcommon' O=$OUT -j$(nproc 2>/dev/null || sysctl -n hw.ncpu)"
eval "$M mt8110-bellatrix_defconfig"
eval "$M zImage mediatek/mt8110-cava.dtb modules"
cp "$W/src/include/linux/hwtcon_ioctl_cmd.h" "$W/hwtcon_ioctl_cmd.h"
sha256sum "$OUT/arch/arm/boot/zImage" | tee "$OUT/zImage.sha256"
echo "Fertig: $OUT/arch/arm/boot/zImage, dtb: $OUT/arch/arm/boot/dts/mediatek/mt8110-cava.dtb (NICHT auf einem Gerät getestet; ein gesperrtes KT6 bootet es nicht)"
