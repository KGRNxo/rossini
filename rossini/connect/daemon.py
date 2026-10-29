"""rossini-connectd: WLAN transfer server as a system service. Usage: python -m rossini.connect.daemon <data_dir> [port]"""
import os
import signal
import sys
import threading

from .server import TransferServer


def main(argv=None):
    a = argv or sys.argv[1:]
    data, port = a[0], int(a[1]) if len(a) > 1 else 8080
    srv = TransferServer(os.path.join(data, "books"), port=port).start()
    os.makedirs("/run/rossini" if os.path.isdir("/run") else data, exist_ok=True)
    pinfile = "/run/rossini/transfer-pin" if os.path.isdir("/run") else os.path.join(data, "transfer-pin")
    fd = os.open(pinfile, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(fd, "w") as f:
        f.write(srv.pin)
    print(f"connectd: listening on :{srv.port}", flush=True)
    done = threading.Event()
    for s in (signal.SIGTERM, signal.SIGINT):
        signal.signal(s, lambda *_: done.set())
    done.wait()
    srv.stop()
    return 0


if __name__ == "__main__":
    sys.exit(main())
