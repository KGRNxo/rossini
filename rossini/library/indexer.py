"""Boot-time indexer: scans <data>/books into <data>/rossini/library.db. Usage: python -m rossini.library.indexer <data_dir>"""
import os
import sys

from .db import Library


def main(argv=None):
    data = (argv or sys.argv[1:])[0]
    os.makedirs(os.path.join(data, "books"), exist_ok=True)
    lib = Library(os.path.join(data, "rossini", "library.db"))
    r = lib.scan(os.path.join(data, "books"))
    print(f"indexer: added={r.added} updated={r.updated} unchanged={r.unchanged} broken={len(r.broken)} ignored={r.ignored}", flush=True)
    lib.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
