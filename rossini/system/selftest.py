"""Boot self-test. A freshly updated slot is only confirmed (and thereby made permanent) when this
passes. Every check exercises the real component (no mocks): filesystem durability, library,
reader, shell rendering with the display layer, settings, transfer server, power policy, daemons.
Usage: python -m rossini.system.selftest <data_dir> <work_dir>"""
import json
import os
import shutil
import socket
import sys
import tempfile
import time
import urllib.request

BAD_BUILD_MARKER = os.environ.get("ROSSINI_BAD_MARKER", "/etc/rossini/selftest-fail")  # only present in images built as the 'bad update' test fixture


def check_marker(ctx):
    if os.path.exists(BAD_BUILD_MARKER):
        raise AssertionError(f"build marker {BAD_BUILD_MARKER} present")
    return "no failure marker"


def check_data_fs(ctx):
    p = os.path.join(ctx["data"], ".selftest")
    payload = os.urandom(1 << 20)
    with open(p, "wb") as f:
        f.write(payload)
        f.flush()
        os.fsync(f.fileno())
    with open(p, "rb") as f:
        assert f.read() == payload, "readback mismatch"
    os.unlink(p)
    st = os.statvfs(ctx["data"])
    return f"1 MiB write/fsync/readback ok, {st.f_bavail * st.f_frsize // (1 << 20)} MiB free"


def _books(ctx):
    from tests import fixtures as F
    d = os.path.join(ctx["work"], "books")
    os.makedirs(d, exist_ok=True)
    F.make_epub(f"{d}/hafen.epub", series="Hafen")
    F.make_fb2(f"{d}/stern.fb2")
    F.make_cbz(f"{d}/comic.cbz")
    F.make_txt(f"{d}/Karl Klar - Notizen.txt")
    return d


def check_library_reader(ctx):
    from rossini.library.db import Library
    from rossini.reader.session import ReaderSession
    d = _books(ctx)
    lib = Library(os.path.join(ctx["work"], "lib.db"))
    ctx["lib"] = lib
    r = lib.scan(d)
    assert (r.added, r.broken) == (4, []), r
    s = ReaderSession(lib, lib.books(query="Hafen")[0]["id"], (600, 800))
    s.next_page(); s.close()
    s2 = ReaderSession(lib, lib.books(query="Hafen")[0]["id"], (600, 800))
    assert s2.page == 1, "reading position not restored"
    return f"4 books indexed, epub paginated into {s2.page_count} pages, position restored"


def check_shell(ctx):
    from rossini.display.eink import Display, PngBackend
    from rossini.settings.store import Settings
    from rossini.shell import screens as S
    from rossini.shell.app import App, Ctx
    from rossini.system.hal import Hal
    from rossini.system.power import PowerManager
    lib = ctx["lib"]
    st = Settings(os.path.join(ctx["work"], "settings.json"))
    power = PowerManager(600, 3600, time.time)
    sd = os.path.join(ctx["data"], "screens")
    os.makedirs(sd, exist_ok=True)
    backend = PngBackend(os.path.join(sd, "last.png"))
    disp = Display((1072, 1448), backend)
    app = App(Ctx(lib, st, Hal({"sysfs": {}}), power, ctx["work"], [os.path.join(ctx["work"], "books")], time.time, ctx["version"], ctx["board"]), disp)
    modes = []
    for name, act in (("home", lambda: app.root("start")), ("library", lambda: app.root("library")),
                      ("reader", lambda: app.open_book(lib.books(query="Hafen")[0]["id"])),
                      ("settings", lambda: app.root("settings"))):
        act()
        im = app.render()
        im.save(os.path.join(sd, f"{name}.png"))
        modes.append(disp.present(im))
    assert modes[0] == "full" and all(m in ("full", "partial") for m in modes), modes
    assert disp.present(im) is None, "identical frame was sent to the panel again"
    st.set("display.rotation", 90)
    assert disp.logical_size == (1448, 1072)
    return f"4 screens rendered ({','.join(modes)}), identical frame skipped, rotation applied"


def check_transfer(ctx):
    from rossini.connect.server import TransferServer
    from tests import fixtures as F
    dest = os.path.join(ctx["work"], "inbox")
    srv = TransferServer(dest, host="127.0.0.1").start()
    try:
        F.make_epub(os.path.join(ctx["work"], "up.epub"), title="Hochgeladen", author="Test Autor")
        data = open(os.path.join(ctx["work"], "up.epub"), "rb").read()
        req = urllib.request.Request(f"http://127.0.0.1:{srv.port}/upload?pin={srv.pin}&name=up.epub", data=data, method="POST")
        assert urllib.request.urlopen(req, timeout=10).status == 200
    finally:
        srv.stop()
    r = ctx["lib"].scan(dest)
    assert r.added == 1 and ctx["lib"].books(query="Hochgeladen"), "uploaded book not indexed"
    return "upload over loopback accepted and indexed"


def check_power(ctx):
    from rossini.system.power import PowerManager
    t = [0]
    pm = PowerManager(60, 600, lambda: t[0])
    t[0] = 61
    assert pm.tick() == "suspend"
    assert pm.tick(battery=2, charging=False) == "poweroff_low_battery"
    return "standby and critical-battery policy ok"


def check_connectd(ctx):
    s = socket.create_connection(("127.0.0.1", 8080), timeout=5)
    s.close()
    return "connectd accepts connections on :8080"


CHECKS = [("marker", check_marker), ("data-fs", check_data_fs), ("library+reader", check_library_reader),
          ("shell+display", check_shell), ("transfer", check_transfer), ("power", check_power)]


def run(data, work, version="?", board="?", extra=()):
    ctx = {"data": data, "work": work, "version": version, "board": board}
    results, ok = [], True
    for name, fn in list(CHECKS) + list(extra):
        t = time.time()
        try:
            detail, passed = fn(ctx), True
        except Exception as e:
            detail, passed, ok = f"{type(e).__name__}: {e}", False, False
        results.append({"check": name, "pass": passed, "detail": detail, "seconds": round(time.time() - t, 2)})
        print(f"selftest {'PASS' if passed else 'FAIL'} {name}: {detail}", flush=True)
    if "lib" in ctx:
        ctx["lib"].close()
    return ok, results


def main(argv=None):
    a = argv or sys.argv[1:]
    data, work = a[0], a[1]
    shutil.rmtree(work, ignore_errors=True)  # every run starts clean
    os.makedirs(work, exist_ok=True)
    ver = open("/etc/rossini/version").read().strip() if os.path.exists("/etc/rossini/version") else "dev"
    ok, res = run(data, work, ver, "qemu-x86_64", extra=[("connectd", check_connectd)] if os.path.exists("/run/rossini") else [])
    with open(os.path.join(work, "selftest.json"), "w") as f:
        json.dump({"ok": ok, "version": ver, "results": res}, f, indent=1)
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
