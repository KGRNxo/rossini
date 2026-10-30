"""Rossini Shell: navigation, screens and dialogs for the E-Ink UI. The App consumes gestures and
produces frames; presentation (partial/full refresh) is the Display's job."""
import os
import time
from dataclasses import dataclass, field
from typing import Callable

from ..reader.session import ReaderSession
from ..reader import formats
from .canvas import INK, MUTE, PAPER, RULE, SOFT, Canvas
from . import screens as S

TABS = [("start", "Start", "home"), ("library", "Bibliothek", "library"), ("reader", "Lesen", "read"),
        ("discover", "Entdecken", "discover"), ("settings", "Einstellungen", "settings")]


@dataclass
class Ctx:
    lib: object
    settings: object
    hal: object
    power: object
    data_dir: str
    library_dirs: list = field(default_factory=list)
    clock: Callable = time.time
    version: str = "dev"
    board: str = "unknown"
    opds_fetch: Callable = None       # url -> connect.opds.Feed
    opds_download: Callable = None    # (entry, dest_dir) -> path
    actions: dict = field(default_factory=dict)   # 'poweroff', 'reboot'
    update_status: Callable = None    # () -> str
    wifi: object = None               # system.networking.Wifi or None
    usb: object = None                # system.usb.UsbExport or None


class App:
    def __init__(self, ctx, display):
        self.ctx, self.display = ctx, display
        self.stack = []
        self.tab = "start"
        self.dialog = None
        self.reader = None
        self.pending_toast = None
        self.hits = []
        st = ctx.settings
        st.subscribe("display.rotation", lambda k, v: display.set_rotation(v))
        st.subscribe("display.full_refresh_every", lambda k, v: setattr(display, "full_every", v))
        st.subscribe("display.frontlight", lambda k, v: ctx.hal.set_frontlight(v))
        st.subscribe("power.", ctx.power.configure)
        display.set_rotation(st.get("display.rotation"))
        display.full_every = st.get("display.full_refresh_every")
        ctx.hal.set_frontlight(st.get("display.frontlight"))
        self.root(self.tab)

    # --- navigation -----------------------------------------------------------
    def root(self, tab):
        self.tab = tab
        self.dialog = None
        screen = {"start": S.Home, "library": S.LibraryList, "discover": S.Discover, "settings": S.SettingsMenu}.get(tab)
        if tab == "reader":
            book = self.ctx.lib.books(sort="recent", limit=1, status="reading")
            if self.reader:
                self.stack = [S.ReaderScreen(self.reader)]
            elif book:
                self.open_book(book[0]["id"])
            else:
                self.stack = [S.EmptyReader()]
            return
        self.stack = [screen()]

    def push(self, screen):
        self.dialog = None
        self.stack.append(screen)

    def back(self):
        if self.dialog:
            self.dialog = None
        elif len(self.stack) > 1:
            top = self.stack.pop()
            if isinstance(top, S.ReaderScreen):
                self.close_reader()
        elif self.tab != "start":
            self.root("start")
        else:
            return False
        return True

    def ask(self, text, *choices):
        self.dialog = (text, choices)

    def toast(self, text):
        self.ask(text, ("OK", lambda: None))

    def dictionaries(self):
        if not hasattr(self, "_dicts"):
            from ..reader.dictionary import Dictionaries
            self._dicts = Dictionaries(os.path.join(self.ctx.data_dir, "dictionaries"))
        return self._dicts

    # --- reader ---------------------------------------------------------------
    def open_book(self, book_id, file_format=None):
        self.close_reader()
        try:
            self.reader = ReaderSession(self.ctx.lib, book_id, self.display.logical_size, self.reader_settings(),
                                        file_format, self.ctx.clock)
        except (formats.Unsupported, FileNotFoundError, Exception) as e:
            self.toast(f"Das Buch kann nicht geöffnet werden: {e}")
            return
        self.tab = "reader"
        self.stack = [S.ReaderScreen(self.reader)]

    def close_reader(self):
        if self.reader:
            self.reader.close(log_stats=self.ctx.settings.get("reader.stats"))
            self.reader = None

    def reader_settings(self):
        return {k: v for k, v in self.ctx.settings.as_dict().items() if k.startswith("reader.")}

    def apply_reader_settings(self):
        if self.reader:
            self.reader.reflow(self.reader_settings())

    # --- rendering --------------------------------------------------------------
    def render(self):
        c = Canvas(self.display.logical_size, self.ctx.settings.get("display.ui_scale"))
        screen = self.stack[-1]
        if screen.fullscreen:
            screen.draw(c, self)
        else:
            self._chrome(c)
            screen.draw(c, self)
        if self.dialog:
            self._dialog(c)
        self.hits = c.hits
        return c.im

    def _chrome(self, c):
        u, ctx = c.u, self.ctx
        c.text(u(56), u(20), time.strftime("%H:%M", time.localtime(ctx.clock())), 30, bold=True)
        x = c.w - u(56)
        pct, charging = ctx.hal.battery_percent(), ctx.hal.charging()
        w = c.battery(x - u(46), u(26), pct, charging)
        x -= w + u(60)
        if pct is not None:
            c.text(x, u(20), f"{pct} %", 28, anchor="r")
            x -= u(90)
        wifi = ctx.hal.wifi_connected()
        if wifi is not None:
            c.icon("wifi", x - u(20), u(34), u(36), fill=INK if wifi else RULE)
        c.rule(u(70), 0, c.w, fill=RULE)
        # bottom navigation
        top = c.h - u(150)
        c.rule(top, 0, c.w, fill=INK, w=2)
        cw = c.w // len(TABS)
        for i, (key, label, icon) in enumerate(TABS):
            cx = i * cw + cw // 2
            on = key == self.tab
            c.icon(icon, cx, top + u(52), u(46), fill=INK if on else MUTE)
            c.text(cx, top + u(94), label, 24, bold=on, fill=INK if on else MUTE, anchor="m", maxw=cw - u(8))
            if on:
                c.d.rectangle((cx - u(36), top + 1, cx + u(36), top + u(6)), fill=INK)
            c.hit((i * cw, top, (i + 1) * cw, c.h), lambda k=key: self.root(k))

    def _dialog(self, c):
        u = c.u
        text, choices = self.dialog
        w, x0 = c.w - u(160), u(80)
        lines = c.wrap(text, 34, w - u(80), 8)
        h = u(80) + len(lines) * u(48) + u(140)
        y0 = (c.h - h) // 2
        c.d.rounded_rectangle((x0, y0, x0 + w, y0 + h), u(18), fill=PAPER, outline=INK, width=u(4))
        c.hits = []  # modal: only the dialog is interactive
        y = y0 + u(40)
        for ln in lines:
            c.text(x0 + u(40), y, ln, 34)
            y += u(48)
        bw = (w - u(80) - u(20) * (len(choices) - 1)) // len(choices)
        for i, (label, fn) in enumerate(choices):
            bx = x0 + u(40) + i * (bw + u(20))
            c.button((bx, y0 + h - u(116), bx + bw, y0 + h - u(36)), label,
                     lambda f=fn: (setattr(self, "dialog", None), f()), primary=(i == len(choices) - 1))

    # --- input -------------------------------------------------------------------
    def handle(self, g):
        """Process one gesture; returns True if the screen needs redrawing."""
        self.ctx.power.activity()
        if g.kind == "key":
            if g.direction == "back":
                return self.back()
            if g.direction == "home":
                self.root("start"); return True
            if g.direction in ("page_down", "right") and isinstance(self.stack[-1], S.ReaderScreen):
                self.reader.next_page(); return True
            if g.direction in ("page_up", "left") and isinstance(self.stack[-1], S.ReaderScreen):
                self.reader.prev_page(); return True
            return False
        if g.kind == "swipe" and not self.dialog:
            return bool(self.stack[-1].swipe(g.direction, self))
        if g.kind in ("tap", "long_press"):
            for rect, fn in self.hits:
                if rect[0] <= g.x < rect[2] and rect[1] <= g.y < rect[3]:
                    fn()
                    return True
            if not self.dialog:
                screen = self.stack[-1]
                return bool(screen.tap_bg(g, self) if g.kind == "tap" else screen.long_press(g, self))
        return False

    def shutdown(self):
        self.close_reader()
        self.ctx.lib.db.commit()
