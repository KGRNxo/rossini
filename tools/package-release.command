#!/bin/bash
# Packs build/out into releases/rossini-<version>/ with checksums. Only development (QEMU) artifacts exist today;
# there is no device image, and none will be released before a board profile reaches status "released".
set -euo pipefail
cd "$(dirname "$0")/.."
ver=$(python3 -c "import rossini; print(rossini.VERSION)")
dest="releases/rossini-$ver"
[ -f build/out/SHA256SUMS ] || { echo "Zuerst ./tools/build-all.command ausführen."; exit 1; }
rm -rf "$dest"; mkdir -p "$dest"
for f in rootfs-"$ver".squashfs initramfs.cpio.gz recovery.cpio.gz update-"$ver".pkg BUILDINFO.json; do cp "build/out/$f" "$dest/"; done
cp docs/STATUS.md CHANGELOG.md "$dest/"
(cd "$dest" && shasum -a 256 * > SHA256SUMS)
tar -C releases -czf "releases/rossini-$ver-dev.tar.gz" "rossini-$ver"
(cd releases && shasum -a 256 "rossini-$ver-dev.tar.gz" > "rossini-$ver-dev.tar.gz.sha256")
echo "Release (nur QEMU-Entwicklungsimages): releases/rossini-$ver-dev.tar.gz"
