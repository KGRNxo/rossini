import os
import tempfile
import time
import unittest

from rossini.library.db import Library
from rossini.reader import formats
from rossini.reader.session import ReaderSession
from tests import fixtures as F

SIZE = (600, 800)


class ReaderTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.d = self.tmp.name
        F.make_epub(self.d + "/a.epub")
        F.make_fb2(self.d + "/b.fb2")
        F.make_cbz(self.d + "/c.cbz")
        F.make_txt(self.d + "/d.txt")
        self.lib = Library(":memory:")
        self.addCleanup(self.lib.close)
        self.lib.scan(self.d)
        self.id = lambda q: self.lib.books(query=q)[0]["id"]

    def test_epub_text_and_toc(self):
        doc = formats.open_document(self.d + "/a.epub")
        self.assertIn("Laterne", doc.text)
        self.assertNotIn("<p>", doc.text)
        self.assertEqual([t for t, _ in doc.toc], ["Kapitel 1", "Kapitel 2", "Kapitel 3"])
        self.assertTrue(doc.toc[0][1] < doc.toc[1][1] < doc.toc[2][1])
        self.assertTrue(doc.text[doc.toc[1][1]:].startswith("Kapitel 2"))

    def test_fb2_and_txt(self):
        self.assertIn("Zweiter Absatz", formats.open_document(self.d + "/b.fb2").text)
        self.assertEqual(formats.open_document(self.d + "/b.fb2").toc[0][0], "Anfang")
        self.assertIn("Mond", formats.open_document(self.d + "/d.txt").text)

    def test_unknown_and_broken_files_are_refused(self):
        with self.assertRaises(formats.Unsupported):
            formats.open_document("/x/book.lit")
        F._w(self.d + "/junk.mobi", "not a mobi")
        with self.assertRaises(formats.Unsupported):
            formats.open_document(self.d + "/junk.mobi")

    def test_pages_progress_and_restore(self):
        s = ReaderSession(self.lib, self.id("Hafenlicht"), SIZE)
        self.assertGreater(s.page_count, 5)
        s.next_page(); s.next_page()
        pos = s.position()
        s.close()
        s2 = ReaderSession(self.lib, self.id("Hafenlicht"), SIZE)
        self.assertEqual(s2.page, 2)
        self.assertEqual(s2.position(), pos)
        self.assertAlmostEqual(self.lib.get_progress(self.id("Hafenlicht"))["percent"], 3 / s2.page_count)

    def test_reflow_keeps_position(self):
        s = ReaderSession(self.lib, self.id("Hafenlicht"), SIZE)
        s.goto_chapter(1)
        off = s.position()
        s.reflow({"reader.font_size": 24})
        self.assertLessEqual(s.position(), off)
        self.assertGreater(s.paginator.pages[s.page].end, off)
        self.assertEqual(s.chapter_index(), 1)

    def test_pages_cover_whole_text_without_overlap(self):
        s = ReaderSession(self.lib, self.id("Hafenlicht"), SIZE)
        pages = s.paginator.pages
        for a, b in zip(pages, pages[1:]):
            self.assertLess(a.start, b.start)
        self.assertEqual(pages[0].start, 0)
        joined = "".join(l.text + ("" if l.hyphen else " ") for p in pages for l in p.lines)
        self.assertEqual(joined.split(), s.doc.text.split())
        self.assertTrue(any(l.hyphen for p in pages for l in p.lines))  # German hyphenation is active

    def test_search_bookmark_highlight_render(self):
        s = ReaderSession(self.lib, self.id("Hafenlicht"), SIZE)
        hits = s.search("laterne")
        self.assertGreater(len(hits), 10)
        s.goto_offset(hits[3])
        s.bookmark()
        s.highlight(hits[3], hits[3] + 7)
        im = s.render()
        self.assertEqual(im.size, SIZE)
        self.assertLess(min(im.getdata()), 50)
        self.assertEqual(len(self.lib.annotations(self.id("Hafenlicht"))), 2)

    def test_cbz_paging(self):
        s = ReaderSession(self.lib, self.id("c"), SIZE)
        self.assertEqual(s.page_count, 3)
        s.next_page()
        self.assertEqual(s.render().size, SIZE)
        s.close()
        self.assertEqual(ReaderSession(self.lib, self.id("c"), SIZE).page, 1)

    def test_stats_are_opt_in(self):
        t = [1000.0]
        s = ReaderSession(self.lib, self.id("d"), SIZE, clock=lambda: t[0])
        s.next_page()
        t[0] += 90
        s.close(log_stats=False)
        self.assertEqual(self.lib.stats()["seconds"], 0)
        s.close(log_stats=True)
        self.assertEqual(self.lib.stats()["seconds"], 90)

    def test_pagination_speed_on_large_text(self):
        F.make_txt(self.d + "/big.txt", (F.LOREM * 20 + "\n") * 400)  # ~1.5 MB
        self.lib.scan(self.d)
        t = time.time()
        s = ReaderSession(self.lib, self.id("big"), SIZE)
        self.assertGreater(s.page_count, 500)
        self.assertLess(time.time() - t, 15)


if __name__ == "__main__":
    unittest.main()
