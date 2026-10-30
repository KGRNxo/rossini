#!/bin/sh
# Boot test on ARMv7 (cross-compiled userland): the same self-test checks as on x86_64, plus verification of a signed
# update package with the pure-Python Ed25519 implementation, on a 32-bit ARM CPU.
export PYTHONPATH=/opt/rossini PYTHONDONTWRITEBYTECODE=1 ROSSINI_FONT_DIR=/opt/rossini/assets/fonts
mkdir -p /run/rossini /tmp/data
echo "ROSSINI-ARM: kernel $(uname -r) $(uname -m)"
python3 -m rossini.system.selftest /tmp/data /tmp/selftest-work && echo "ROSSINI-ARM: selftest PASS" || echo "ROSSINI-ARM: selftest FAIL"
python3 - <<'PY'
import sys, tempfile
from rossini.updater import package
pub = bytes.fromhex(open("/opt/rossini-test/update.pub").read().strip())
with tempfile.TemporaryDirectory() as d:
    man, staged = package.verify("/opt/rossini-test/good.pkg", [pub], "qemu-armv7-vexpress", 0, d)
    print("ROSSINI-ARM: signed package verified, version", man["version"])
    try:
        package.verify("/opt/rossini-test/tampered.pkg", [pub], "qemu-armv7-vexpress", 0, d)
        print("ROSSINI-ARM: tampered package ACCEPTED (bug)")
    except package.PackageError as e:
        print("ROSSINI-ARM: tampered package rejected:", e)
PY
echo "ROSSINI-ARM: done"
poweroff -f
