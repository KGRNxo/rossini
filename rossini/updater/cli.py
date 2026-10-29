"""rossini-update: keygen | build | verify | install | status | confirm"""
import argparse
import json
import os
import sys

from ..system.hal import load_profile
from . import package
from .bootctl import BootCtl
from .install import install


def _pub(path):
    with open(path) as f:
        return bytes.fromhex(f.read().strip())


def main(argv=None):
    ap = argparse.ArgumentParser(prog="rossini-update")
    sub = ap.add_subparsers(dest="cmd", required=True)
    k = sub.add_parser("keygen"); k.add_argument("dir")
    b = sub.add_parser("build"); b.add_argument("--out", required=True); b.add_argument("--version", required=True)
    b.add_argument("--rollback-index", type=int, required=True); b.add_argument("--board", action="append", required=True)
    b.add_argument("--key", required=True); b.add_argument("--rootfs", required=True)
    i = sub.add_parser("install"); i.add_argument("pkg"); i.add_argument("--board", required=True)
    i.add_argument("--pubkey", required=True); i.add_argument("--bootctl", required=True)
    s = sub.add_parser("status"); s.add_argument("--bootctl", required=True)
    c = sub.add_parser("confirm"); c.add_argument("--bootctl", required=True); c.add_argument("--slot", required=True)
    a = ap.parse_args(argv)
    if a.cmd == "keygen":
        os.makedirs(a.dir, exist_ok=True)
        priv, pub = package.generate_keypair()
        fd = os.open(os.path.join(a.dir, "update.key"), os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        with os.fdopen(fd, "w") as f:
            f.write(priv.hex())
        with open(os.path.join(a.dir, "update.pub"), "w") as f:
            f.write(pub.hex())
    elif a.cmd == "build":
        with open(a.key) as f:
            priv = bytes.fromhex(f.read().strip())
        m = package.build(a.out, a.version, a.rollback_index, a.board, {"rootfs": a.rootfs}, priv)
        print(json.dumps(m, indent=1))
    elif a.cmd == "install":
        slots = load_profile(a.board)["slots"]
        try:
            m = install(a.pkg, [_pub(a.pubkey)], a.board, slots, a.bootctl)
        except package.PackageError as e:
            print(f"Update abgelehnt: {e}", file=sys.stderr)
            return 2
        print(f"Version {m['version']} installiert; startet beim nächsten Neustart zur Probe.")
    elif a.cmd == "status":
        print(BootCtl(a.bootctl).status())
    elif a.cmd == "confirm":
        return 0 if BootCtl(a.bootctl).confirm(a.slot) else 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
