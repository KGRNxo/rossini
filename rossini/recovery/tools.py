"""Recovery operations. Pure functions over paths so they run identically from the recovery image,
from the running system and in tests. Destructive actions need an explicit confirmation token."""
import hashlib
import json
import os
import shutil
import subprocess
import time

from ..updater.bootctl import BootCtl

RESET_TOKEN = "ERASE-USER-DATA"


def verify_system(root, manifest_path):
    """Compare every file listed in manifest (sha256  path) with the tree at root. Returns problems."""
    problems = []
    with open(manifest_path) as f:
        for line in f:
            digest, _, rel = line.rstrip("\n").partition("  ")
            p = os.path.join(root, rel.lstrip("./"))
            if not os.path.isfile(p):
                problems.append(f"fehlt: {rel}")
                continue
            h = hashlib.sha256()
            with open(p, "rb") as g:
                for c in iter(lambda: g.read(1 << 20), b""):
                    h.update(c)
            if h.hexdigest() != digest:
                problems.append(f"verändert: {rel}")
    return problems


def fsck(device):
    """Read-only ext4 check (e2fsck -n). Returns (ok, output); ok=False also when the tool is missing."""
    try:
        r = subprocess.run(["e2fsck", "-n", device], capture_output=True, text=True, timeout=600)
    except (OSError, subprocess.TimeoutExpired) as e:
        return False, f"e2fsck nicht ausführbar: {e}"
    return r.returncode == 0, r.stdout + r.stderr


def restore_previous(bootctl_path):
    """Make the other slot the confirmed one (used when the active system is bad). Refuses if the
    other slot never held a version."""
    ctl = BootCtl(bootctl_path)
    other = ctl.other(ctl.confirmed)
    if not ctl.v[f"version_{other}"]:
        raise ValueError(f"Slot {other} enthält keine bekannte Version; Wiederherstellung nicht möglich")
    ctl.v.update(confirmed=other, trial="", tries="0")
    ctl.save()
    return other


def export_data(data_dir, dest):
    """Copy user data (books, library DB, settings) to dest; verifies sizes. Never deletes anything."""
    os.makedirs(dest, exist_ok=True)
    target = os.path.join(dest, "rossini-data-" + time.strftime("%Y%m%d-%H%M%S"))
    shutil.copytree(data_dir, target, symlinks=False, ignore=shutil.ignore_patterns("*.part", ".tmp-*"))
    for d, _, fs in os.walk(data_dir):
        for f in fs:
            if f.endswith(".part") or f.startswith(".tmp-"):
                continue
            a = os.path.join(d, f)
            b = os.path.join(target, os.path.relpath(a, data_dir))
            if not os.path.exists(b) or os.path.getsize(a) != os.path.getsize(b):
                raise IOError(f"export check failed: {a}")
    return target


def factory_reset(data_dir, token):
    """Erase the contents of the data directory (not the directory itself, not the system)."""
    if token != RESET_TOKEN:
        raise PermissionError(f"Bestätigung fehlt: '{RESET_TOKEN}' eingeben")
    n = 0
    for name in os.listdir(data_dir):
        p = os.path.join(data_dir, name)
        shutil.rmtree(p) if os.path.isdir(p) and not os.path.islink(p) else os.unlink(p)
        n += 1
    return n


def main(argv=None):
    import argparse
    ap = argparse.ArgumentParser(prog="rossini-recovery")
    s = ap.add_subparsers(dest="cmd", required=True)
    v = s.add_parser("verify"); v.add_argument("root"); v.add_argument("manifest")
    f = s.add_parser("fsck"); f.add_argument("device")
    r = s.add_parser("restore"); r.add_argument("bootctl")
    e = s.add_parser("export"); e.add_argument("data_dir"); e.add_argument("dest")
    z = s.add_parser("reset"); z.add_argument("data_dir"); z.add_argument("--confirm", required=True)
    a = ap.parse_args(argv)
    if a.cmd == "verify":
        probs = verify_system(a.root, a.manifest)
        print("\n".join(probs) or "System unverändert.")
        return 1 if probs else 0
    if a.cmd == "fsck":
        ok, out = fsck(a.device); print(out); return 0 if ok else 1
    if a.cmd == "restore":
        print("Zurückgesetzt auf Slot", restore_previous(a.bootctl)); return 0
    if a.cmd == "export":
        print("Exportiert nach", export_data(a.data_dir, a.dest)); return 0
    if a.cmd == "reset":
        print(factory_reset(a.data_dir, a.confirm), "Einträge gelöscht"); return 0


if __name__ == "__main__":
    raise SystemExit(main())
