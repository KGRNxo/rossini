"""Builds a self-contained demo environment (sample books, settings, fake hardware) for previews and tests."""
import os
import tempfile

from ..display.eink import Display, Recorder
from ..library.db import Library
from ..settings.store import Settings
from ..system.hal import Hal
from ..system.power import PowerManager
from .app import App, Ctx


def make_app(root, size=(1072, 1448), books=True, clock=lambda: 1_700_000_000.0, **ctx_kw):
    from tests import fixtures as F
    lib_dir = os.path.join(root, "books")
    os.makedirs(lib_dir, exist_ok=True)
    if books:
        F.make_epub(f"{lib_dir}/hafenlicht.epub", series="Hafen")
        F.make_epub(f"{lib_dir}/zweite.epub", title="Die zweite Flut mit einem sehr langen Titel, der umbrechen muss", author="Clara Wellenreiter", cover=False)
        F.make_fb2(f"{lib_dir}/sternkarte.fb2")
        F.make_cbz(f"{lib_dir}/comic.cbz")
        F.make_txt(f"{lib_dir}/Karl Klar - Notizen am Meer.txt")
    lib = Library(os.path.join(root, "library.db"))
    lib.scan(lib_dir)
    st = Settings(os.path.join(root, "settings.json"))
    hal = Hal({"sysfs": {"battery_capacity": "/bat/cap", "battery_status": "/bat/st", "wifi_operstate": "/net/op"}}, os.path.join(root, "sys"))
    for rel, v in (("bat/cap", "82"), ("bat/st", "Discharging"), ("net/op", "up")):
        os.makedirs(os.path.join(root, "sys", os.path.dirname(rel)), exist_ok=True)
        with open(os.path.join(root, "sys", rel), "w") as f:
            f.write(v)
    power = PowerManager(st.get("power.standby_s"), st.get("power.off_s"), clock)
    ctx = Ctx(lib, st, hal, power, root, [lib_dir], clock, "0.4.0-dev", "demo", **ctx_kw)
    rec = Recorder()
    return App(ctx, Display(size, rec)), rec
