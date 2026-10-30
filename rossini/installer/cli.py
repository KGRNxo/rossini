"""Installation assistant (called by tools/install.command). Steps follow docs/installation/README.md.
Unsupported or unreleased devices get a diagnose report and are refused. There is no --force."""
import argparse
import json
import os
import sys
import time

from ..updater import package
from . import gate, probe


def main(argv=None):
    ap = argparse.ArgumentParser(prog="rossini-install")
    ap.add_argument("--mount", required=True, help="mount point of the connected reader")
    ap.add_argument("--image", help="signed Rossini update package")
    ap.add_argument("--pubkey", help="trusted public key file (hex)")
    ap.add_argument("--backup-dir", default=os.path.expanduser("~/RossiniBackups"))
    ap.add_argument("--report-dir", default=".")
    ap.add_argument("--board-id", help="board_id read on the device (cat /proc/idme/board_id); USB storage alone cannot reveal it")
    a = ap.parse_args(argv)

    print("1/6 Gerät lesen …")
    facts = probe.read_facts(a.mount)
    if a.board_id:
        facts["board_id"] = a.board_id.strip()
    profiles = gate.load_profiles()
    image_ok, image_board = False, None
    if a.image and a.pubkey:
        print("2/6 Image prüfen …")
        try:
            with open(a.pubkey) as f:
                key = bytes.fromhex(f.read().strip())
            import tempfile
            with tempfile.TemporaryDirectory() as st:
                # board check happens in the gate; accept any board here and report which one the image names
                man, _ = package.verify(a.image, [key], next(iter(json_boards(a.image)), ""), 0, st)
            image_ok, image_board = True, man["boards"][0]
        except (package.PackageError, ValueError, OSError) as e:
            print(f"   Image abgelehnt: {e}")
    print("3/6 Eignung prüfen …")
    dec = gate.evaluate(facts, profiles, image_ok, image_board, backup_done=False)
    if dec.board is None or any(not r.startswith("Datensicherung") for r in dec.reasons):
        return refuse(dec, facts, a.report_dir)
    print("4/6 Datensicherung …")
    manifest = probe.backup(a.mount, os.path.join(a.backup_dir, time.strftime("%Y%m%d-%H%M%S")))
    print(f"   Sicherung geprüft: {manifest}")
    dec = gate.evaluate(facts, profiles, image_ok, image_board, backup_done=True)
    if not dec.allowed:
        return refuse(dec, facts, a.report_dir)
    print("5/6 Installation …")
    # Unreachable until a board profile is `released` with an install_method; no flashing code exists yet.
    raise NotImplementedError("Installationsverfahren fehlt: " + dec.board)


def json_boards(image):
    import tarfile
    with tarfile.open(image) as t:
        yield json.load(t.extractfile("manifest.json"))["boards"][0]


def refuse(dec, facts, report_dir):
    path = os.path.join(report_dir, time.strftime("rossini-diagnose-%Y%m%d-%H%M%S.json"))
    with open(path, "w") as f:
        json.dump({"decision": "refused", "board": dec.board, "reasons": dec.reasons, "facts": facts}, f, indent=1, ensure_ascii=False)
    print("INSTALLATION VERWEIGERT:")
    for r in dec.reasons:
        print("  -", r)
    print(f"Diagnosebericht: {path}")
    return 3


if __name__ == "__main__":
    sys.exit(main())
