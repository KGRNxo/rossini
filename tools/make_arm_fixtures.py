#!/usr/bin/env python3
"""Throw-away signed packages for the ARM boot test (good + tampered) in build/work/armtest."""
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
from rossini.updater import package  # noqa: E402

d = os.path.join(ROOT, "build", "work", "armtest")
os.makedirs(d, exist_ok=True)
priv, pub = package.generate_keypair()
open(d + "/update.pub", "w").write(pub.hex())
payload = os.urandom(50000)
open(d + "/payload", "wb").write(payload)
package.build(d + "/good.pkg", "0.4.0-dev", 1, ["qemu-armv7-vexpress"], {"rootfs": d + "/payload"}, priv, created=1700000000)
b = bytearray(open(d + "/good.pkg", "rb").read())
b[b.index(payload[:32]) + 100] ^= 1
open(d + "/tampered.pkg", "wb").write(b)
