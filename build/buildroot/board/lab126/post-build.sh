#!/bin/sh
# Copies the Rossini userland into the target tree and installs the ARM boot test as the init action.
set -e
TARGET="$1"
REPO="$(cd "$(dirname "$0")/../../../.." && pwd)"
DST="$TARGET/opt/rossini"
rm -rf "$DST"; mkdir -p "$DST/tests"
cp -r "$REPO/rossini" "$REPO/boards" "$REPO/assets" "$DST/"
cp "$REPO/tests/__init__.py" "$REPO/tests/fixtures.py" "$DST/tests/"
find "$DST" -name __pycache__ -prune -exec rm -rf {} +
mkdir -p "$TARGET/etc/rossini"
echo "lab126-wario-family" > "$TARGET/etc/rossini/board"
echo "0.4.0-dev" > "$TARGET/etc/rossini/version"
cp "$(dirname "$0")/../qemu-armv7/arm-selftest.sh" "$TARGET/usr/bin/rossini-arm-selftest"
chmod 755 "$TARGET/usr/bin/rossini-arm-selftest"
# run the self-test at boot, then power off
sed -i '/^::sysinit:\/etc\/init.d\/rcS/a ::sysinit:/usr/bin/rossini-arm-selftest' "$TARGET/etc/inittab"
mkdir -p "$TARGET/opt/rossini-test"
cp "$REPO"/build/work/armtest/update.pub "$REPO"/build/work/armtest/good.pkg "$REPO"/build/work/armtest/tampered.pkg "$TARGET/opt/rossini-test/"
