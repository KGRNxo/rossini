import os
import tempfile
import unittest

from rossini.connect import opds
from rossini.display.input import Gesture
from rossini.shell import screens as S
from rossini.shell.demo import make_app


def tap(app, x, y):
    return app.handle(Gesture("tap", x, y))


def tap_hit(app, label_fn):
    """Tap the first registered hit region whose callback satisfies label_fn."""
    for rect, fn in app.hits:
        if label_fn(fn):
            return tap(app, (rect[0] + rect[2]) // 2, (rect[1] + rect[3]) // 2)
    raise AssertionError("no matching control")


class ShellTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.app, self.rec = make_app(self.tmp.name)
        self.addCleanup(self.app.ctx.lib.close)
        self.app.render()

    def nav(self, i):
        w = self.app.display.logical_size[0]
        h = self.app.display.logical_size[1]
        tap(self.app, w // 5 * i + w // 10, h - 40)
        self.app.render()

    def test_bottom_navigation_reaches_every_area(self):
        for i, cls in enumerate((S.Home, S.LibraryList, S.EmptyReader, S.Discover, S.SettingsMenu)):
            self.nav(i)
            self.assertIsInstance(self.app.stack[-1], cls, i)

    def test_continue_reading_from_home_and_page_turn_persists(self):
        lib = self.app.ctx.lib
        bid = lib.books(query="Hafenlicht")[0]["id"]
        lib.set_progress(bid, 3000, 0.3)
        self.app.root("start"); self.app.render()
        h = self.app.display.logical_size[1]
        rect, _ = next(hit for hit in self.app.hits if hit[0][3] < h - 150)  # first control above the nav bar: "Weiterlesen"
        tap(self.app, (rect[0] + rect[2]) // 2, (rect[1] + rect[3]) // 2)
        self.app.render()
        self.assertIsInstance(self.app.stack[-1], S.ReaderScreen)
        self.assertEqual(self.app.reader.book_id, bid)
        r = self.app.reader
        start = r.page
        w, h = self.app.display.logical_size
        tap(self.app, int(w * 0.9), h // 2)  # right zone = next page
        self.assertEqual(r.page, start + 1)
        self.app.handle(Gesture("swipe", 0, 0, "right"))  # previous
        self.assertEqual(r.page, start)
        tap(self.app, w // 2, h // 2); self.app.render()  # centre = menu
        self.assertTrue(self.app.stack[-1].menu)
        self.app.back(); self.app.shutdown()
        self.assertEqual(lib.get_progress(bid)["position"], r.position())

    def test_every_screen_renders_at_several_sizes(self):
        for size in ((1072, 1448), (758, 1024), (1264, 1680), (1448, 1072)):
            tmp = tempfile.mkdtemp()
            app, _ = make_app(tmp, size=size)
            bid = app.ctx.lib.books(query="Hafenlicht")[0]["id"]
            for screen in (S.Home(), S.LibraryList(), S.BookDetail(bid), S.Discover(), S.SettingsMenu(), S.SettingsGroup("Anzeige"),
                           S.SettingsGroup("Lesen"), S.SettingsGroup("Energie"), S.SettingsGroup("Verbindungen"), S.SettingsGroup("Speicher"),
                           S.SettingsGroup("Datenschutz"), S.SettingsGroup("System"), S.TextInput("Suche", "x", lambda t: None)):
                app.stack = [screen]
                self.assertEqual(app.render().size, size)
            app.open_book(bid)
            self.assertEqual(app.render().size, size)
            app.ctx.lib.close()

    def test_settings_are_wired_to_system_functions(self):
        app = self.app
        st = app.ctx.settings
        st.set("display.rotation", 90)
        self.assertEqual(app.display.logical_size, (1448, 1072))
        self.assertEqual(app.render().size, (1448, 1072))
        st.set("display.rotation", 0)
        st.set("display.full_refresh_every", 4)
        self.assertEqual(app.display.full_every, 4)
        st.set("power.standby_s", 45)
        self.assertEqual(app.ctx.power.standby_s, 45)
        # tapping a stepper changes the real setting
        app.push(S.SettingsGroup("Lesen")); app.render()
        before = st.get("reader.font_size")
        group = app.stack[-1]
        group.set(app, "reader.font_size", before + 2)
        self.assertEqual(st.get("reader.font_size"), before + 2)
        group.set(app, "reader.font_size", 5)  # invalid: ignored
        self.assertEqual(st.get("reader.font_size"), before + 2)

    def test_library_search_sort_filter_and_pages(self):
        self.nav(1)
        lib_screen = self.app.stack[-1]
        lib_screen.set_query("sternkarte", self.app); self.app.stack = [lib_screen]
        self.app.render()
        self.assertEqual(len(self.app.ctx.lib.books(**lib_screen.kwargs())), 1)
        lib_screen.query = ""; lib_screen.cycle_filter(); lib_screen.cycle_filter()  # "Lesend"
        self.assertEqual(lib_screen.flt, 2)
        self.app.render()

    def test_remove_book_asks_first_and_keeps_file(self):
        lib = self.app.ctx.lib
        bid = lib.books(query="Notizen")[0]["id"]
        path = lib.book(bid)["files"][0]["path"]
        self.app.push(S.BookDetail(bid)); self.app.render()
        # third action button is "Entfernen"
        rect, fn = self.app.hits[-1]
        tap(self.app, (rect[0] + rect[2]) // 2, (rect[1] + rect[3]) // 2)
        self.assertIsNotNone(self.app.dialog)
        self.assertIsNotNone(lib.book(bid))  # nothing happened yet
        self.app.render()
        rect, fn = self.app.hits[-1]  # confirm button of the dialog
        tap(self.app, (rect[0] + rect[2]) // 2, (rect[1] + rect[3]) // 2)
        self.assertIsNone(lib.book(bid))
        self.assertTrue(os.path.exists(path))

    def test_discover_offline_error_and_download(self):
        app = self.app
        app.ctx.settings.set("connect.opds_url", "http://catalog.invalid/opds")
        def boom(url):
            raise OSError("offline")
        app.ctx.opds_fetch = boom
        app.root("discover"); app.render()
        self.assertIn("nicht erreichbar", app.stack[-1].error)
        feed = opds.Feed("Kat", [opds.Entry("Buch", "A", None, [("http://x/b.epub", "application/epub+zip")])])
        app.ctx.opds_fetch = lambda url: feed
        app.ctx.opds_download = lambda e, d: __import__("tests.fixtures", fromlist=["x"]).make_epub(os.path.join(d, "dl.epub"), title="Neu Geladen")
        app.stack[-1].error = None; app.stack[-1].feed = None
        app.render()
        app.stack[-1].choose(app, feed.entries[0])
        self.assertTrue(app.ctx.lib.books(query="Neu Geladen"))
        self.assertIn("geladen", app.dialog[0])

    def test_only_changed_region_is_sent_to_panel(self):
        app, rec = self.app, self.rec
        app.display.present(app.render())
        n = len(rec.updates)
        self.assertIsNone(app.display.present(app.render()))
        self.nav(1)
        app.display.present(app.render())
        self.assertEqual(len(rec.updates), n + 1)
        bbox, mode = rec.updates[-1]
        self.assertEqual(mode, "partial")
        self.assertLess((bbox[2] - bbox[0]) * (bbox[3] - bbox[1]), 1072 * 1448)

    def test_empty_library_shows_onboarding(self):
        tmp = tempfile.mkdtemp()
        app, _ = make_app(tmp, books=False)
        self.addCleanup(app.ctx.lib.close)
        app.render()
        self.assertIsInstance(app.stack[-1], S.Home)
        rect, _ = next(hit for hit in app.hits if hit[0][3] < app.display.logical_size[1] - 150)  # "Bibliothek jetzt durchsuchen"
        tap(app, (rect[0] + rect[2]) // 2, (rect[1] + rect[3]) // 2)
        self.assertIn("0 neu", app.dialog[0])  # the scan ran and reported

    def test_keyboard_text_entry(self):
        got = []
        self.app.push(S.TextInput("Suche", "", got.append)); self.app.render()
        kb = self.app.stack[-1]
        kb._add("h"); kb._add("i")
        self.assertEqual(kb.text, "hi")
        kb.shift = True; kb._add("A")
        self.assertEqual((kb.text, kb.shift), ("hiA", False))

    def test_long_press_dictionary_highlight_and_extend(self):
        from tests import fixtures as F
        app = self.app
        F.make_stardict(os.path.join(app.ctx.data_dir, "dictionaries"), "de")
        bid = app.ctx.lib.books(query="Hafenlicht")[0]["id"]
        app.open_book(bid); app.render()
        s = app.reader
        box = next(b for b in s.word_boxes if s.doc.text[b[4]:b[5]] == "Mond")
        app.handle(Gesture("long_press", int((box[0] + box[2]) / 2), int((box[1] + box[3]) / 2)))
        scr = app.stack[-1]
        self.assertEqual(scr.sel, (box[4], box[5]))
        app.render()
        self.assertEqual(app.dictionaries().lookup("Mond")[0][2], "Erdtrabant; moon")
        # extend to a later word, then highlight
        scr.extending = True
        later = next(b for b in s.word_boxes if b[4] > box[5] + 20)
        tap(app, int((later[0] + later[2]) / 2), int((later[1] + later[3]) / 2))
        self.assertEqual(scr.sel, (box[4], later[5]))
        app.render()
        rect, _ = next(h for h in app.hits if h[0][1] > app.display.logical_size[1] - 200)  # "Markieren"
        tap(app, (rect[0] + rect[2]) // 2, (rect[1] + rect[3]) // 2)
        ann = app.ctx.lib.annotations(bid, "highlight")
        self.assertEqual((ann[0]["start"], ann[0]["end"]), (box[4], later[5]))
        self.assertIsNone(scr.sel)

    def test_touch_zone_setting(self):
        app = self.app
        app.open_book(app.ctx.lib.books(query="Hafenlicht")[0]["id"]); app.render()
        w, h = app.display.logical_size
        app.ctx.settings.set("reader.prev_zone", 50)
        app.reader.goto_page(3)
        tap(app, int(w * 0.45), h // 2)
        self.assertEqual(app.reader.page, 2)
        tap(app, int(w * 0.55), h // 2)  # with a 50 % back zone there is no menu zone: forward
        self.assertEqual(app.reader.page, 3)

    def test_pdf_zoom_from_menu(self):
        from tests import fixtures as F
        app = self.app
        p = F.make_pdf(os.path.join(app.ctx.library_dirs[0], "z.pdf"))
        app.ctx.lib.scan(p)
        app.open_book(app.ctx.lib.books(query="PDF Titel")[0]["id"])
        scr = app.stack[-1]
        scr.menu = True
        app.render()
        row = [h[0] for h in app.hits if h[0][1] > app.display.logical_size[1] - 200]
        rect = max((r for r in row if r[1] == row[0][1]), key=lambda r: r[0])  # rightmost of the first row: "Zoom +"
        tap(app, (rect[0] + rect[2]) // 2, (rect[1] + rect[3]) // 2)
        self.assertEqual(app.reader.zoom, 1.5)


if __name__ == "__main__":
    unittest.main()
