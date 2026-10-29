"""Screens of the Rossini Shell. Each screen draws into a Canvas and registers hit regions;
state lives on the screen object. German UI strings are the primary language."""
import os
import time

from ..settings.store import SCHEMA
from .canvas import INK, MUTE, PAPER, RULE, SOFT

M = 56  # side margin in design units


class Screen:
    fullscreen = False

    def draw(self, c, app):
        raise NotImplementedError

    def swipe(self, direction, app):
        return False

    def tap_bg(self, g, app):
        return False

    def header(self, c, y, title, back=None, app=None, right=None):
        """Large title; optional back control. Returns y below the header."""
        u = c.u
        x = u(M)
        if back:
            c.icon("back", u(M + 20), y + u(34), u(30))
            c.hit((0, y - u(10), u(160), y + u(90)), back)
            x = u(M + 70)
        c.text(x, y, title, 52, bold=True, maxw=c.w - x - u(M + (230 if right else 0)))
        if right:
            label, fn = right
            c.button((c.w - u(M + 220), y - u(4), c.w - u(M), y + u(76)), label, fn, size=30)
        return y + u(100)


# --- Start -------------------------------------------------------------------
class Home(Screen):
    def draw(self, c, app):
        u, lib = c.u, app.ctx.lib
        y = u(110)
        books = lib.books(sort="recent", limit=4, status="reading")
        if not lib.count():
            c.text(u(M), y, "Noch keine Bücher", 52, bold=True)
            c.paragraph(u(M), y + u(90), "Kopiere EPUB-, FB2-, CBZ- oder TXT-Dateien auf das Gerät "
                        "oder lade sie über Entdecken aus einem OPDS-Katalog. Danach erscheinen sie hier.", 34, c.w - 2 * u(M), gap=1.45)
            if app.ctx.library_dirs:
                c.button((u(M), y + u(330), c.w - u(M), y + u(430)), "Bibliothek jetzt durchsuchen", lambda: S_scan(app), primary=True)
            return
        if books:
            b = lib.book(books[0]["id"])
            pr = lib.get_progress(b["id"])
            c.text(u(M), y, "Weiterlesen", 30, bold=True, fill=MUTE)
            cy = y + u(56)
            c.cover((u(M), cy, u(M + 270), cy + u(400)), b["cover"], b["title"])
            tx = u(M + 310)
            tw = c.w - tx - u(M)
            ty = c.paragraph(tx, cy, b["title"], 46, tw, 3, bold=True, serif=True, gap=1.2)
            c.text(tx, ty + u(8), b["author"] or "Unbekannter Autor", 32, fill=MUTE, maxw=tw)
            pct = pr["percent"] if pr else 0
            c.progress(tx, cy + u(250), tw, pct)
            c.text(tx, cy + u(274), f"{round(pct * 100)} % gelesen", 28, fill=MUTE)
            c.button((tx, cy + u(320), c.w - u(M), cy + u(400)), "Weiterlesen", lambda: app.open_book(b["id"]), primary=True)
            y = cy + u(470)
        else:
            y = self._row(c, app, y, "Zuletzt hinzugefügt", lib.books(sort="added", limit=3))
        c.rule(y - u(24))
        rec = [x for x in lib.books(sort="recent", limit=5, status="reading")][1:4] if books else []
        if rec:
            y = self._row(c, app, y, "Zuletzt geöffnet", rec)
        new = lib.books(sort="added", limit=3, status="unread")
        if new and y < c.h - u(150 + 340):
            y = self._row(c, app, y, "Neue Bücher", new)
        cols = lib.collections()
        if cols and y < c.h - u(150 + 160):
            c.text(u(M), y, "Sammlungen", 30, bold=True, fill=MUTE)
            x = u(M)
            for col in cols[:4]:
                label = f"{col['name']} · {col['n']}"
                w = int(c.font(30).getlength(label)) + u(48)
                if x + w > c.w - u(M):
                    break
                c.button((x, y + u(50), x + w, y + u(120)), label, lambda n=col["name"]: S_open_collection(app, n), size=28)
                x += w + u(16)

    def _row(self, c, app, y, title, books):
        u = c.u
        c.text(u(M), y, title, 30, bold=True, fill=MUTE)
        cw = (c.w - 2 * u(M) - 2 * u(24)) // 3
        for i, b in enumerate(books[:3]):
            x = u(M) + i * (cw + u(24))
            full = app.ctx.lib.book(b["id"])
            c.cover((x, y + u(50), x + cw, y + u(50 + 220)), full["cover"], b["title"])
            c.text(x, y + u(284), b["title"], 28, bold=True, maxw=cw)
            c.hit((x, y + u(50), x + cw, y + u(330)), lambda i=b["id"]: app.push(BookDetail(i)))
        return y + u(370)


def S_scan(app):
    r = app.ctx.lib.scan(*app.ctx.library_dirs)
    msg = f"{r.added} neu, {r.updated} aktualisiert, {r.unchanged} unverändert."
    if r.broken:
        msg += f" {len(r.broken)} nicht lesbar (z. B. {os.path.basename(r.broken[0][0])}: {r.broken[0][1]})."
    app.toast(msg)


def S_open_collection(app, name):
    app.root("library")
    app.stack[0].collection = name


# --- Bibliothek --------------------------------------------------------------
SORT_LABEL = {"title": "Titel", "author": "Autor", "recent": "Zuletzt gelesen", "added": "Hinzugefügt", "series": "Serie"}
FILTERS = [("Alle", {}), ("Ungelesen", {"status": "unread"}), ("Lesend", {"status": "reading"}),
           ("Fertig", {"status": "finished"}), ("Favoriten", {"favorites": True})]


class LibraryList(Screen):
    def __init__(self):
        self.sort, self.flt, self.page, self.query, self.collection = "title", 0, 0, "", None

    def kwargs(self):
        kw = dict(FILTERS[self.flt][1])
        if self.query:
            kw["query"] = self.query
        if self.collection:
            kw["collection"] = self.collection
        return kw

    def draw(self, c, app):
        u, lib = c.u, app.ctx.lib
        y = self.header(c, u(100), "Bibliothek" if not self.collection else self.collection,
                        back=(lambda: setattr(self, "collection", None) or setattr(self, "page", 0)) if self.collection else None)
        sorts = list(SORT_LABEL)
        bw = (c.w - 2 * u(M) - u(32)) // 3
        c.button((u(M), y - u(10), u(M) + bw, y + u(60)), "Sortierung: " + SORT_LABEL[self.sort], self.cycle_sort, size=24)
        c.button((u(M) + bw + u(16), y - u(10), u(M) + 2 * bw + u(16), y + u(60)), "Filter: " + FILTERS[self.flt][0], self.cycle_filter, size=24)
        c.button((u(M) + 2 * bw + u(32), y - u(10), c.w - u(M), y + u(60)), f"Suche: {self.query}" if self.query else "Suche",
                 lambda: app.push(TextInput("Suche in der Bibliothek", self.query, lambda t: self.set_query(t, app))), size=24)
        y += u(90)
        rows = max(1, (c.h - u(150) - y - u(110)) // u(132))
        total = len(lib.books(sort=self.sort, **self.kwargs()))
        pages = max(1, -(-total // rows))
        self.page = min(self.page, pages - 1)
        books = lib.books(sort=self.sort, limit=rows, offset=self.page * rows, **self.kwargs())
        if not books:
            c.text(u(M), y + u(20), "Keine Bücher gefunden." if (self.query or self.flt) else "Die Bibliothek ist leer.", 36, fill=MUTE)
        for b in books:
            full = lib.book(b["id"])
            c.cover((u(M), y, u(M + 82), y + u(114)), full["cover"], b["title"])
            tx = u(M + 112)
            c.text(tx, y + u(4), b["title"], 36, bold=True, serif=True, maxw=c.w - tx - u(M))
            sub = " · ".join(x for x in (b["author"], b["series"] and f"{b['series']} {int(b['series_index'] or 0) or ''}".strip()) if x)
            c.text(tx, y + u(52), sub or "Unbekannter Autor", 28, fill=MUTE, maxw=c.w - tx - u(M))
            st = {"unread": "Ungelesen", "reading": f"{round((b['percent'] or 0) * 100)} %", "finished": "Gelesen"}[b["status"]]
            c.text(tx, y + u(86), f"{st}  ·  {b['formats'].replace(',', ', ').upper()}" + ("  ★" if b["favorite"] else ""), 24, fill=MUTE)
            c.rule(y + u(128), u(M), c.w - u(M), fill=SOFT)
            c.hit((0, y, c.w, y + u(132)), lambda i=b["id"]: app.push(BookDetail(i)))
            y += u(132)
        py = c.h - u(150 + 90)
        c.button((u(M), py, u(M + 150), py + u(70)), "‹", lambda: self.turn(-1), enabled=self.page > 0, size=40)
        c.text(c.w // 2, py + u(14), f"Seite {self.page + 1} von {pages}  ·  {total} Bücher", 28, fill=MUTE, anchor="m")
        c.button((c.w - u(M + 150), py, c.w - u(M), py + u(70)), "›", lambda: self.turn(1), enabled=self.page < pages - 1, size=40)
        self._pages = pages

    def turn(self, d):
        self.page = max(0, self.page + d)

    def swipe(self, direction, app):
        if direction in ("left", "right"):
            self.page = max(0, min(self._pages - 1, self.page + (1 if direction == "left" else -1)))
            return True

    def cycle_sort(self):
        keys = list(SORT_LABEL)
        self.sort, self.page = keys[(keys.index(self.sort) + 1) % len(keys)], 0

    def cycle_filter(self):
        self.flt, self.page = (self.flt + 1) % len(FILTERS), 0

    def set_query(self, t, app):
        self.query, self.page = t.strip(), 0
        app.back()


class BookDetail(Screen):
    def __init__(self, book_id):
        self.id = book_id

    def draw(self, c, app):
        u, lib = c.u, app.ctx.lib
        b = lib.book(self.id)
        if not b:
            app.back()
            return
        y = self.header(c, u(100), "Buch", back=app.back)
        c.cover((u(M), y, u(M + 300), y + u(440)), b["cover"], b["title"])
        tx = u(M + 340)
        tw = c.w - tx - u(M)
        ty = c.paragraph(tx, y, b["title"], 48, tw, 4, bold=True, serif=True, gap=1.2)
        c.text(tx, ty + u(10), b["author"] or "Unbekannter Autor", 34, fill=MUTE, maxw=tw)
        if b["series"]:
            c.text(tx, ty + u(60), f"{b['series']}" + (f" · Band {b['series_index']:g}" if b["series_index"] else ""), 28, fill=MUTE, maxw=tw)
        pr = lib.get_progress(self.id)
        c.progress(tx, y + u(330), tw, pr["percent"] if pr else 0)
        c.text(tx, y + u(354), {"unread": "Ungelesen", "reading": f"{round(pr['percent'] * 100)} % gelesen" if pr else "Begonnen",
                                "finished": "Gelesen"}[b["status"]], 28, fill=MUTE)
        y += u(490)
        files = [f for f in b["files"]]
        readable = [f for f in files if not f["broken"]]
        c.text(u(M), y, "Formate: " + ", ".join(f["format"].upper() + (" (nicht lesbar: " + f["broken"] + ")" if f["broken"] else "")
                                               for f in files), 28, fill=MUTE, maxw=c.w - 2 * u(M))
        y += u(60)
        if readable:
            label = "Lesen" if not pr else "Weiterlesen"
            c.button((u(M), y, c.w - u(M), y + u(96)), label, lambda: app.open_book(self.id), primary=True)
            y += u(116)
            if len(readable) > 1:
                bw = (c.w - 2 * u(M) - u(16) * (len(readable) - 1)) // len(readable)
                for i, f in enumerate(readable):
                    c.button((u(M) + i * (bw + u(16)), y, u(M) + i * (bw + u(16)) + bw, y + u(70)), f"Als {f['format'].upper()} lesen",
                             lambda fm=f["format"]: app.open_book(self.id, fm), size=26)
                y += u(90)
        bw = (c.w - 2 * u(M) - u(32)) // 3
        acts = [("Favorit ✓" if b["favorite"] else "Favorit", lambda: lib.set_favorite(self.id, not b["favorite"])),
                ("Als gelesen" if b["status"] != "finished" else "Als ungelesen",
                 lambda: lib.set_status(self.id, "finished" if b["status"] != "finished" else "unread")),
                ("Entfernen", lambda: app.ask("Buch aus der Bibliothek entfernen? Die Datei bleibt erhalten.",
                                              ("Abbrechen", lambda: None), ("Entfernen", lambda: (lib.remove(self.id), app.back()))))]
        for i, (label, fn) in enumerate(acts):
            c.button((u(M) + i * (bw + u(16)), y, u(M) + i * (bw + u(16)) + bw, y + u(76)), label, fn, size=26)


# --- Lesen ---------------------------------------------------------------------
class EmptyReader(Screen):
    def draw(self, c, app):
        u = c.u
        c.text(u(M), u(110), "Kein Buch geöffnet", 52, bold=True)
        c.paragraph(u(M), u(200), "Wähle ein Buch in der Bibliothek, um mit dem Lesen zu beginnen.", 34, c.w - 2 * u(M))
        c.button((u(M), u(330), c.w - u(M), u(430)), "Zur Bibliothek", lambda: app.root("library"), primary=True)


class ReaderScreen(Screen):
    fullscreen = True

    def __init__(self, session):
        self.s, self.menu, self.mode = session, False, None  # mode: None | 'toc' | 'marks'
        self.toc_page = 0

    def draw(self, c, app):
        u, s = c.u, self.s
        c.im.paste(s.render())
        if self.mode:
            return self._list(c, app)
        if self.menu:
            c.d.rectangle((0, 0, c.w, u(120)), fill=PAPER)
            c.d.line((0, u(120), c.w, u(120)), fill=INK, width=2)
            c.icon("back", u(M + 20), u(60), u(30))
            c.hit((0, 0, u(180), u(120)), app.back)
            c.text(u(M + 80), u(38), s.title, 36, bold=True, maxw=c.w - u(M * 2 + 80))
            base = c.h - u(300)
            c.d.rectangle((0, base, c.w, c.h), fill=PAPER)
            c.d.line((0, base, c.w, base), fill=INK, width=2)
            c.progress(u(M), base + u(40), c.w - 2 * u(M), s.percent())
            c.text(u(M), base + u(64), f"Seite {s.page + 1} von {s.page_count}", 26, fill=MUTE)
            bw = (c.w - 2 * u(M) - 3 * u(16)) // 4
            sz = app.ctx.settings.get("reader.font_size")
            text = hasattr(s, "paginator")
            btns = [("Inhalt", lambda: self._set_mode("toc"), text and bool(s.chapters())),
                    ("Notizen", lambda: self._set_mode("marks"), True),
                    ("A−", lambda: self._font(app, -2), text), ("A+", lambda: self._font(app, 2), text)]
            for i, (label, fn, on) in enumerate(btns):
                c.button((u(M) + i * (bw + u(16)), base + u(120), u(M) + i * (bw + u(16)) + bw, base + u(200)), label, fn, enabled=on, size=28)
            c.button((u(M), base + u(214), u(M) + 2 * bw + u(16), base + u(284)), "Lesezeichen setzen", lambda: self._bookmark(app), size=26)
            c.button((u(M) + 2 * bw + u(32), base + u(214), c.w - u(M), base + u(284)), "Suche",
                     lambda: app.push(TextInput("Im Buch suchen", "", lambda t: self._search(app, t))), enabled=text, size=26)

    def _set_mode(self, m):
        self.mode, self.toc_page = m, 0

    def _font(self, app, d):
        app.ctx.settings.set("reader.font_size", max(18, min(90, app.ctx.settings.get("reader.font_size") + d)))
        app.apply_reader_settings()

    def _bookmark(self, app):
        self.s.bookmark()
        self.menu = False
        app.toast(f"Lesezeichen auf Seite {self.s.page + 1} gesetzt.")

    def _search(self, app, t):
        hits = self.s.search(t)
        app.back()
        if not hits:
            app.toast(f"„{t}“ wurde nicht gefunden.")
        else:
            self.s.goto_offset(hits[0])
            self.menu = False
            app.toast(f"{len(hits)} Treffer. Anzeige: erster Treffer, Seite {self.s.page + 1}.")

    def _list(self, c, app):
        u, s = c.u, self.s
        c.d.rectangle((0, 0, c.w, c.h), fill=PAPER)
        if self.mode == "toc":
            items = [(label, lambda o=off: (s.goto_offset(o), self._close())) for label, off in s.chapters()]
            title = "Inhalt"
        else:
            items = []
            for a in app.ctx.lib.annotations(s.book_id):
                kind = {"bookmark": "Lesezeichen", "highlight": "Markierung", "note": "Notiz"}[a["kind"]]
                text = (a["text"] or "")[:60]
                items.append((f"{kind}: {text}", lambda o=a["start"]: (s.goto_offset(o) if hasattr(s, "paginator") else s.goto_page(o), self._close())))
            title = "Lesezeichen und Markierungen"
        y = self.header(c, u(100), title, back=self._close)
        rows = (c.h - y - u(160)) // u(100)
        pages = max(1, -(-len(items) // rows))
        self.toc_page = min(self.toc_page, pages - 1)
        if not items:
            c.text(u(M), y, "Noch nichts vorhanden.", 34, fill=MUTE)
        for label, fn in items[self.toc_page * rows:(self.toc_page + 1) * rows]:
            c.text(u(M), y + u(24), label, 34, maxw=c.w - 2 * u(M))
            c.rule(y + u(92), fill=SOFT)
            c.hit((0, y, c.w, y + u(100)), fn)
            y += u(100)
        c.button((u(M), c.h - u(140), u(M + 150), c.h - u(70)), "‹", lambda: setattr(self, "toc_page", max(0, self.toc_page - 1)), enabled=self.toc_page > 0)
        c.button((c.w - u(M + 150), c.h - u(140), c.w - u(M), c.h - u(70)), "›", lambda: setattr(self, "toc_page", self.toc_page + 1), enabled=self.toc_page < pages - 1)

    def _close(self):
        self.mode = None
        self.menu = False

    def tap_bg(self, g, app):
        w = app.display.logical_size[0]
        if self.mode:
            return False
        if self.menu:
            self.menu = False
            return True
        if g.x < w * 0.3:
            self.s.prev_page()
        elif g.x > w * 0.7 or g.y > app.display.logical_size[1] * 0.75:
            self.s.next_page()
        else:
            self.menu = True
        return True

    def swipe(self, direction, app):
        if self.mode or self.menu:
            return False
        if direction == "left":
            self.s.next_page()
        elif direction == "right":
            self.s.prev_page()
        elif direction == "down":
            self.menu = True
        return True


# --- Text input ------------------------------------------------------------------
ROWS = ["qwertzuiopü", "asdfghjklöä", "yxcvbnm,.-"]


class TextInput(Screen):
    def __init__(self, title, text, on_submit):
        self.title, self.text, self.submit, self.shift = title, text, on_submit, False

    def draw(self, c, app):
        u = c.u
        y = self.header(c, u(100), self.title, back=app.back)
        c.d.rounded_rectangle((u(M), y, c.w - u(M), y + u(100)), u(14), outline=INK, width=u(3))
        c.text(u(M + 24), y + u(26), self.text or "", 42, maxw=c.w - u(2 * M + 48))
        c.button((u(M), y + u(124), c.w - u(M), y + u(214)), "OK", lambda: self.submit(self.text), primary=True)
        ky = y + u(260)
        kw = (c.w - 2 * u(M)) // 11
        for r, row in enumerate(ROWS):
            for i, ch in enumerate(row):
                lab = ch.upper() if self.shift else ch
                x = u(M) + i * kw + (r * kw // 3)
                c.button((x, ky + r * u(130), x + kw - u(8), ky + r * u(130) + u(116)), lab, lambda l=lab: self._add(l), size=40)
        r = 3
        x = u(M)
        c.button((x, ky + r * u(130), x + 2 * kw, ky + r * u(130) + u(116)), "Aa", lambda: setattr(self, "shift", not self.shift), primary=self.shift, size=34)
        c.button((x + 2 * kw + u(8), ky + r * u(130), x + 8 * kw, ky + r * u(130) + u(116)), "Leerzeichen", lambda: self._add(" "), size=30)
        c.button((x + 8 * kw + u(8), ky + r * u(130), c.w - u(M), ky + r * u(130) + u(116)), "Löschen", lambda: setattr(self, "text", self.text[:-1]), size=30)

    def _add(self, ch):
        self.text += ch
        self.shift = False


# --- Entdecken (OPDS) --------------------------------------------------------------
class Discover(Screen):
    def __init__(self):
        self.feed, self.history, self.error, self.page = None, [], None, 0

    def load(self, app, url):
        try:
            self.feed = app.ctx.opds_fetch(url)
            self.url, self.error, self.page = url, None, 0
        except Exception as e:  # network errors are expected while offline
            self.error = f"Der Katalog ist nicht erreichbar ({type(e).__name__}). Prüfe die WLAN-Verbindung."
            self.url = url

    def draw(self, c, app):
        u = c.u
        base = app.ctx.settings.get("connect.opds_url")
        y = self.header(c, u(100), "Entdecken", back=(lambda: self.go_up(app)) if self.history else None,
                        right=("Neu laden", lambda: self.load(app, self.url or base)) if base else None)
        if not base:
            c.paragraph(u(M), y, "Hier erscheinen Bücher aus deinem OPDS-Katalog, zum Beispiel einem Calibre-Server im Heimnetz. "
                        "Trage zuerst die Adresse unter Einstellungen › Verbindungen ein.", 34, c.w - 2 * u(M), gap=1.45)
            c.button((u(M), y + u(300), c.w - u(M), y + u(400)), "Einstellungen öffnen", lambda: app.root("settings"), primary=True)
            return
        if self.feed is None and not self.error:
            self.load(app, base)
        if self.error:
            c.paragraph(u(M), y, self.error, 34, c.w - 2 * u(M), gap=1.45)
            c.button((u(M), y + u(220), c.w - u(M), y + u(320)), "Erneut versuchen", lambda: self.load(app, self.url), primary=True)
            return
        c.text(u(M), y - u(30), self.feed.title, 30, bold=True, fill=MUTE, maxw=c.w - 2 * u(M))
        rows = (c.h - u(150) - y - u(110)) // u(120)
        entries = self.feed.entries
        pages = max(1, -(-len(entries) // rows))
        self.page = min(self.page, pages - 1)
        for e in entries[self.page * rows:(self.page + 1) * rows]:
            c.text(u(M), y + u(10), e.title, 34, bold=True, maxw=c.w - 2 * u(M + 120))
            c.text(u(M), y + u(58), (e.author or ("Katalog" if e.nav else "")), 26, fill=MUTE, maxw=c.w - 2 * u(M + 120))
            c.icon("chevron" if e.nav else "back", c.w - u(M + 30), y + u(44), u(28), fill=MUTE if e.nav else INK)
            if not e.nav:
                c.text(c.w - u(M), y + u(80), "laden", 22, anchor="r", fill=MUTE)
            c.rule(y + u(112), fill=SOFT)
            c.hit((0, y, c.w, y + u(120)), lambda e=e: self.choose(app, e))
            y += u(120)
        py = c.h - u(150 + 90)
        c.button((u(M), py, u(M + 150), py + u(70)), "‹", lambda: setattr(self, "page", self.page - 1), enabled=self.page > 0, size=40)
        c.text(c.w // 2, py + u(14), f"Seite {self.page + 1} von {pages}", 28, fill=MUTE, anchor="m")
        c.button((c.w - u(M + 150), py, c.w - u(M), py + u(70)), "›", lambda: setattr(self, "page", self.page + 1), enabled=self.page < pages - 1, size=40)

    def choose(self, app, e):
        if e.nav:
            self.history.append(self.url)
            self.load(app, e.nav)
            return
        try:
            path = app.ctx.opds_download(e, app.ctx.library_dirs[0])
            app.ctx.lib.scan(path)
            app.toast(f"„{e.title}“ wurde geladen und der Bibliothek hinzugefügt.")
        except Exception as ex:
            app.toast(f"Download fehlgeschlagen: {ex}")

    def go_up(self, app):
        self.load(app, self.history.pop())

    def swipe(self, direction, app):
        if direction in ("left", "right"):
            self.page = max(0, self.page + (1 if direction == "left" else -1))
            return True


# --- Einstellungen -----------------------------------------------------------------
LABELS = {
    "display.frontlight": ("Frontlicht", "step", 10, "%"),
    "display.rotation": ("Ausrichtung", "choice", {0: "Hochformat", 90: "Quer rechts", 180: "Kopfüber", 270: "Quer links"}),
    "display.full_refresh_every": ("Vollständiger Refresh alle", "step", 1, " Wechsel"),
    "display.ui_scale": ("Oberflächengröße", "step", 0.1, "×"),
    "reader.font": ("Schrift", "choice", {"serif": "Serif", "sans": "Sans"}),
    "reader.font_size": ("Schriftgröße", "step", 2, " px"),
    "reader.line_spacing": ("Zeilenabstand", "step", 0.05, "×"),
    "reader.margin": ("Seitenrand", "step", 10, " px"),
    "reader.justify": ("Blocksatz", "toggle"),
    "reader.indent": ("Absatzeinzug", "toggle"),
    "reader.stats": ("Lesestatistik speichern", "toggle"),
    "power.standby_s": ("Standby nach", "step", 60, " s"),
    "power.off_s": ("Ausschalten nach", "step", 3600, " s"),
    "connect.opds_url": ("OPDS-Katalog", "text"),
    "connect.sync_dir": ("Sync-Ordner", "text"),
    "system.language": ("Sprache", "choice", {"de": "Deutsch", "en": "English"}),
}
GROUPS = ["Anzeige", "Lesen", "Energie", "Verbindungen", "Speicher", "Datenschutz", "System"]


class SettingsMenu(Screen):
    def draw(self, c, app):
        u = c.u
        y = self.header(c, u(100), "Einstellungen")
        for g in GROUPS:
            c.text(u(M), y + u(22), g, 38)
            c.icon("chevron", c.w - u(M + 20), y + u(46), u(28), fill=MUTE)
            c.rule(y + u(100), fill=SOFT)
            c.hit((0, y, c.w, y + u(100)), lambda g=g: app.push(SettingsGroup(g)))
            y += u(106)


class SettingsGroup(Screen):
    def __init__(self, group):
        self.group = group

    def draw(self, c, app):
        u, st = c.u, app.ctx.settings
        y = self.header(c, u(100), self.group, back=app.back)
        if self.group in ("Speicher", "Datenschutz", "System"):
            return getattr(self, "_" + self.group.lower())(c, app, y)
        for key, (_, _, grp) in SCHEMA.items():
            if grp != self.group or key not in LABELS:
                continue
            spec = LABELS[key]
            label, kind, v = spec[0], spec[1], st.get(key)
            c.text(u(M), y + u(22), label, 34)
            right = c.w - u(M)
            if kind == "toggle":
                c.button((right - u(190), y + u(8), right, y + u(84)), "An" if v else "Aus", lambda k=key, v=v: self.set(app, k, not v), primary=bool(v), size=28)
            elif kind == "choice":
                names = spec[2]
                c.button((right - u(280), y + u(8), right, y + u(84)), names[v], lambda k=key, v=v, n=list(names): self.set(app, k, n[(n.index(v) + 1) % len(n)]), size=26)
            elif kind == "step":
                step, unit = spec[2], spec[3]
                txt = f"{v:g}{unit}" if isinstance(v, float) else f"{v}{unit}"
                c.button((right - u(380), y + u(8), right - u(300), y + u(84)), "−", lambda k=key, v=v, s=step: self.set(app, k, self._n(v - s)), size=40)
                c.text(right - u(150), y + u(26), txt, 28, anchor="m", maxw=u(190))
                c.button((right - u(80), y + u(8), right, y + u(84)), "+", lambda k=key, v=v, s=step: self.set(app, k, self._n(v + s)), size=40)
            elif kind == "text":
                c.text(u(M), y + u(64), v or "nicht gesetzt", 24, fill=MUTE, maxw=c.w - 2 * u(M + 20))
                c.button((right - u(190), y + u(8), right, y + u(84)), "Ändern", lambda k=key, v=v: app.push(TextInput(LABELS[k][0], v, lambda t, k=k: (self.set(app, k, t.strip()), app.back()))), size=26)
            c.rule(y + u(112), fill=SOFT)
            y += u(120)

    @staticmethod
    def _n(v):
        return round(v, 2)

    def set(self, app, key, value):
        try:
            app.ctx.settings.set(key, value)
        except ValueError:
            return
        if key.startswith("reader."):
            app.apply_reader_settings()

    def _speicher(self, c, app, y):
        u, lib = c.u, app.ctx.lib
        st = os.statvfs(app.ctx.data_dir)
        size = sum(f["size"] or 0 for b in lib.books(limit=100000) for f in lib.book(b["id"])["files"])
        for label, val in (("Bücher", str(lib.count())), ("Größe der Bibliothek", f"{size / 1e6:.1f} MB"),
                           ("Frei auf dem Gerät", f"{st.f_bavail * st.f_frsize / 1e9:.2f} GB")):
            c.text(u(M), y + u(22), label, 34); c.text(c.w - u(M), y + u(22), val, 34, anchor="r", bold=True); c.rule(y + u(100), fill=SOFT); y += u(106)
        y += u(20)
        for label, fn in (("Bibliothek neu einlesen", lambda: S_scan(app)),
                          ("Fehlende Einträge entfernen", lambda: app.toast(f"{lib.prune_missing()} Einträge entfernt.")),
                          ("Notizen und Fortschritt exportieren", lambda: app.toast("Exportiert nach " + export_user_data(app.ctx)))):
            c.button((u(M), y, c.w - u(M), y + u(90)), label, fn); y += u(110)

    def _datenschutz(self, c, app, y):
        u = c.u
        y = c.paragraph(u(M), y, "Alle Daten bleiben auf diesem Gerät. Rossini OS sendet keine Telemetrie und benötigt kein Konto. "
                        "Netzwerkzugriffe finden nur statt, wenn du einen Katalog öffnest oder Bücher überträgst.", 32, c.w - 2 * u(M), gap=1.45)
        y += u(30)
        c.button((u(M), y, c.w - u(M), y + u(90)), "Einstellungen zurücksetzen",
                 lambda: app.ask("Alle Einstellungen auf Standard zurücksetzen? Bücher und Fortschritt bleiben erhalten.",
                                 ("Abbrechen", lambda: None), ("Zurücksetzen", lambda: (app.ctx.settings.reset(), app.apply_reader_settings()))))

    def _system(self, c, app, y):
        u, ctx = c.u, app.ctx
        info = [("Rossini OS", ctx.version), ("Gerät", ctx.board)]
        if ctx.update_status:
            info.append(("System", ctx.update_status()))
        pct = ctx.hal.battery_percent()
        info.append(("Akku", "nicht verfügbar" if pct is None else f"{pct} %"))
        for label, val in info:
            c.text(u(M), y + u(22), label, 34); c.text(c.w - u(M), y + u(22), val, 30, anchor="r", bold=True, maxw=c.w - u(M * 2 + 220)); c.rule(y + u(100), fill=SOFT); y += u(106)
        y += u(20)
        for label, key in (("Neustart", "reboot"), ("Ausschalten", "poweroff")):
            if key in ctx.actions:
                c.button((u(M), y, c.w - u(M), y + u(90)), label,
                         lambda k=key, l=label: app.ask(f"{l}? Gelesene Position und Einstellungen werden vorher gesichert.",
                                                        ("Abbrechen", lambda: None), (l, lambda: (app.shutdown(), ctx.actions[k]()))))
                y += u(110)


def export_user_data(ctx):
    """Write progress and annotations (not book files) as JSON next to the data partition."""
    lib = ctx.lib
    out = {"exported": time.strftime("%Y-%m-%dT%H:%M:%S", time.localtime(ctx.clock())), "books": []}
    for b in lib.books(limit=100000, archived=False) + lib.books(limit=100000, archived=True):
        out["books"].append({"title": b["title"], "author": b["author"], "status": b["status"],
                             "progress": lib.get_progress(b["id"]), "annotations": lib.annotations(b["id"])})
    os.makedirs(os.path.join(ctx.data_dir, "exports"), exist_ok=True)
    import json
    path = os.path.join(ctx.data_dir, "exports", "rossini-export.json")
    with open(path, "w") as f:
        json.dump(out, f, indent=1, ensure_ascii=False)
    return path
