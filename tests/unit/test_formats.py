import os
import shutil
import tempfile
import unittest
import zipfile

from rossini.library.db import Library
from rossini.reader import formats, mobi, paged
from rossini.reader.layout import IMAGE
from rossini.reader.rtf import rtf_to_text
from rossini.reader.session import ReaderSession
from tests import fixtures as F

SIZE = (600, 800)
HAS_DJVU = bool(shutil.which("c44") and shutil.which("ddjvu"))
HAS_BSDTAR = bool(shutil.which("bsdtar"))


class FormatsTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.d = self.tmp.name
        self.lib = Library(":memory:")
        self.addCleanup(self.lib.close)

    def open(self, path, **settings):
        self.lib.scan(path)
        bid = self.lib.books(sort="added")[0]["id"]
        return ReaderSession(self.lib, bid, SIZE, settings)

    def test_pdf_metadata_pages_toc_search_crop_zoom(self):
        p = F.make_pdf(self.d + "/a.pdf")
        r = self.lib.scan(p)
        self.assertEqual(r.added, 1)
        b = self.lib.books()[0]
        self.assertEqual((b["title"], b["author"]), ("PDF Titel", "Petra Autor"))
        self.assertTrue(self.lib.book(b["id"])["cover"])
        s = ReaderSession(self.lib, b["id"], SIZE, {"reader.pdf_crop": False})
        self.assertEqual((s.page_count, s.chapters()), (3, [("Anfang", 0), ("Ende", 2)]))
        self.assertEqual(s.search("seite 2"), [1])
        full = s.render()
        self.assertEqual(full.size, SIZE)
        s.reflow({"reader.pdf_crop": True})
        cropped = s._page()
        self.assertGreater(cropped.width / cropped.height, 3)  # only the text line remains
        s.set_zoom(+1); s.set_zoom(+1)
        self.assertEqual(s.zoom, 2.0)
        c, r = s.tiles()
        self.assertGreater(c * r, 1)
        for _ in range(c * r):
            s.next_page()
        self.assertEqual((s.page, s.tile), (1, 0))
        s.prev_page()
        self.assertEqual((s.page, s.tile), (0, c * r - 1))
        s.close()
        self.assertEqual(self.lib.get_progress(b["id"])["kind"], "page")

    def test_pdf_reflow_switch_keeps_place(self):
        s = self.open(F.make_pdf(self.d + "/a.pdf", pages=20))
        s.goto_page(10)
        s.reflow({"reader.pdf_reflow": True})
        self.assertTrue(s.flowing)
        self.assertIn("Leuchtturm", s.doc.text)
        self.assertAlmostEqual(s.percent(), 11 / 20, delta=0.15)
        s.close()
        s2 = ReaderSession(self.lib, s.book_id, SIZE, {})  # back to page mode: mapped through percent
        self.assertEqual(s2.page, s2._page_from_percent(s.percent()))

    def test_mobi_decoding_metadata_images_and_trailing_entries(self):
        p = F.make_mobi(self.d + "/m.mobi")
        m = mobi.Mobi(p)
        self.assertEqual((m.title, m.author), ("Mobi Titel", "Max Mobi"))
        self.assertTrue(m.cover())
        doc = formats.open_document(p)
        self.assertIn("Nr. 29", doc.text)
        self.assertNotIn("XY", doc.text)  # trailing record entries stripped
        self.assertEqual([t for t, _ in doc.toc], ["Erstes Kapitel", "Zweites Kapitel"])
        self.assertEqual(len(doc.images), 1)
        self.assertEqual(doc.text.split("\n").count(IMAGE), 1)
        s = self.open(p)
        s.goto_page(s.page_count - 1)
        self.assertEqual(s.render().size, SIZE)
        self.assertEqual(self.lib.books()[0]["author"], "Max Mobi")

    def test_mobi_uncompressed_and_drm(self):
        self.assertIn("Nr. 3", formats.open_document(F.make_mobi(self.d + "/u.azw3", compress=False)).text)
        r = self.lib.scan(F.make_mobi(self.d + "/e.mobi", encrypted=True))
        self.assertEqual(r.broken[0][1], "drm")

    def test_palmdoc_codes(self):
        self.assertEqual(mobi.palmdoc_decompress(b"ab\x02\xff\x01" + bytes([0xC1]) + b"\x80\x18"), b"ab\xff\x01 A\x01 A")
        data = (F.LOREM * 3).encode()
        self.assertEqual(mobi.palmdoc_decompress(F.palmdoc_compress(data)), data)
        with self.assertRaises(Exception):
            mobi.palmdoc_decompress(b"\x80\x40")  # distance beyond output

    @unittest.skipUnless(HAS_DJVU, "djvulibre missing")
    def test_djvu(self):
        s = self.open(F.make_djvu(self.d + "/d.djvu"))
        self.assertEqual(s.page_count, 2)
        im = s.render()
        self.assertLess(min(im.getdata()), 30)
        s.next_page()
        self.assertEqual(s.page, 1)

    @unittest.skipUnless(HAS_BSDTAR, "bsdtar missing")
    def test_cbr_as_7z_and_as_zip(self):
        s = self.open(F.make_cbr_7z(self.d + "/c.cbr"))
        self.assertEqual(s.page_count, 2)
        self.assertEqual(s.render().size, SIZE)
        z = self.d + "/z.cbr"
        F.make_cbz(z)
        self.assertEqual(paged.ComicDoc(z).page_count, 3)

    def test_rtf_and_html(self):
        txt = rtf_to_text(F.RTF)
        self.assertIn("Erster Absatz mit ä und € Euro.", txt)
        self.assertIn("Zweiter fetter Absatz.", txt)
        self.assertNotIn("Times", txt); self.assertNotIn("Versteckt", txt); self.assertNotIn("Test;", txt)
        F._w(self.d + "/r.rtf", F.RTF.decode())
        self.assertIn("Zweiter fetter Absatz.", formats.open_document(self.d + "/r.rtf").text)
        F._w(self.d + "/h.html", "<html><head><title>Seite X</title><script>evil()</script></head><body><h2>Teil</h2><p>Hallo &amp; tschüss</p></body></html>")
        doc = formats.open_document(self.d + "/h.html")
        self.assertEqual((doc.title, doc.toc), ("Seite X", [("Teil", 0)]))
        self.assertIn("Hallo & tschüss", doc.text)
        self.assertNotIn("evil", doc.text)
        self.lib.scan(self.d + "/h.html")
        self.assertEqual(self.lib.books()[0]["title"], "Seite X")

    def test_epub_and_fb2_images_are_laid_out_and_drawn(self):
        doc = formats.open_document(F.make_epub(self.d + "/img.epub", chapters=2, body_repeat=3, inline_image=True))
        self.assertEqual(len(doc.images), 1)   # cover.png resolved; ../../escape.png outside the book is dropped
        off = next(iter(doc.images))
        self.assertEqual(doc.text[off], IMAGE)
        self.assertTrue(doc.images[off]().startswith(b"\x89PNG"))
        fb = formats.open_document(F.make_fb2(self.d + "/b.fb2"))
        self.assertEqual(fb.images, {})  # coverpage image is metadata, not body content
        # FB2 body image
        F._w(self.d + "/i.fb2", open(self.d + "/b.fb2", encoding="utf-8").read().replace("<p>Zweiter Absatz.</p>", '<image l:href="#c.png"/><p>Zweiter Absatz.</p>'))
        fb = formats.open_document(self.d + "/i.fb2")
        self.assertEqual(len(fb.images), 1)
        s = self.open(self.d + "/i.fb2")
        line = next(l for pg in s.paginator.pages for l in pg.lines if l.height)
        self.assertGreater(line.height, 0)
        s.goto_offset(line.start)
        im = s.render()
        self.assertIn(200, set(im.getdata()))  # the gray (200) test image is on the page

    def test_night_mode_and_word_hit_testing(self):
        s = self.open(F.make_txt(self.d + "/Karl - Wort.txt"))
        im = s.render()
        x0, y0, x1, y1, a, b = s.word_boxes[0]
        self.assertEqual(s.word_at((x0 + x1) / 2, (y0 + y1) / 2), (a, b))
        self.assertEqual(s.doc.text[a:b], "Der")
        self.assertIsNone(s.word_at(-5, -5))
        s.reflow({"reader.invert": True})
        inv = s.render()
        self.assertEqual(inv.getpixel((1, 1)), 0)
        self.assertEqual(im.getpixel((1, 1)), 255)


if __name__ == "__main__":
    unittest.main()


class DictionaryTest(unittest.TestCase):
    def test_lookup_with_inflection_and_two_dictionaries(self):
        from rossini.reader.dictionary import Dictionaries
        with tempfile.TemporaryDirectory() as d:
            F.make_stardict(d + "/de", "de")
            F.make_stardict(d + "/en", "en", {"Moon": "Mond", "harbour": "Hafen"}, compress=False)
            F._w(d + "/broken.ifo", "garbage")
            ds = Dictionaries(d)
            self.assertEqual(len(ds.dicts), 2)
            self.assertEqual(len(ds.errors), 1)
            self.assertEqual(ds.lookup("Mond,")[0][1:], ("Mond", "Erdtrabant; moon"))
            self.assertEqual(ds.lookup("Hafens")[0][1], "Hafen")
            self.assertEqual(ds.lookup("moon")[0][2], "Mond")
            self.assertEqual(ds.lookup("Unbekannt"), [])
