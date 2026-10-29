import os
import tempfile
import unittest

from rossini.library.db import Library
from tests import fixtures as F


class LibraryTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.d = self.tmp.name
        self.lib = Library(os.path.join(self.d, "lib.db"))
        self.addCleanup(self.tmp.cleanup)
        self.addCleanup(self.lib.close)

    def p(self, name):
        return os.path.join(self.d, "books", name)

    def make(self):
        os.makedirs(self.p(""), exist_ok=True)
        F.make_epub(self.p("a.epub"), series="Hafen")
        F.make_fb2(self.p("b.fb2"))
        F.make_cbz(self.p("c.cbz"))
        F.make_txt(self.p("Karl Klar - Notizen.txt"))
        F._w(self.p("x.odt"), "odt")

    def test_scan_extracts_metadata(self):
        self.make()
        r = self.lib.scan(self.p(""))
        self.assertEqual((r.added, r.ignored, r.broken), (4, 1, []))
        b = {x["title"]: x for x in self.lib.books()}
        self.assertEqual(b["Das Hafenlicht"]["author"], "Anna Beispiel")
        self.assertEqual(b["Das Hafenlicht"]["series"], "Hafen")
        self.assertEqual(b["Die Sternkarte"]["author"], "Bernd Fiktiv")
        self.assertEqual(b["Notizen"]["author"], "Karl Klar")
        self.assertTrue(self.lib.book(b["Das Hafenlicht"]["id"])["cover"])

    def test_rescan_is_incremental_and_never_touches_files(self):
        self.make()
        before = {f: os.stat(self.p(f)).st_mtime_ns for f in os.listdir(self.p(""))}
        self.lib.scan(self.p(""))
        r = self.lib.scan(self.p(""))
        self.assertEqual((r.added, r.unchanged), (0, 4))
        self.assertEqual(before, {f: os.stat(self.p(f)).st_mtime_ns for f in os.listdir(self.p(""))})

    def test_formats_of_same_work_are_one_book(self):
        os.makedirs(self.p(""))
        F.make_epub(self.p("one.epub"), title="Gleich", author="A B")
        F.make_fb2(self.p("two.fb2"), title="Gleich", first="A", last="B")
        self.lib.scan(self.p(""))
        books = self.lib.books()
        self.assertEqual(len(books), 1)
        self.assertEqual(sorted(books[0]["formats"].split(",")), ["epub", "fb2"])

    def test_duplicates_broken_and_drm(self):
        os.makedirs(self.p(""))
        F.make_epub(self.p("a.epub"))
        os.link(self.p("a.epub"), self.p("copy.epub"))
        F._w(self.p("bad.epub"), "not a zip")
        F.make_epub(self.p("drm.epub"), title="Geschützt", encrypted=True)
        r = self.lib.scan(self.p(""))
        self.assertEqual({os.path.basename(p): why for p, why in r.broken},
                         {"bad.epub": "not a valid zip/epub", "drm.epub": "drm"})
        self.assertEqual(len(self.lib.duplicates()), 1)
        self.assertEqual(len(self.lib.books()), 1)

    def test_edit_survives_rescan_until_explicit_reset(self):
        self.make()
        self.lib.scan(self.p(""))
        bid = self.lib.books(query="Hafenlicht")[0]["id"]
        self.lib.edit(bid, title="Neuer Titel")
        os.utime(self.p("a.epub"), (1, 1))
        self.lib.scan(self.p(""))
        self.assertEqual(self.lib.book(bid)["title"], "Neuer Titel")
        self.assertEqual(len(self.lib.books()), 4)
        self.lib.rescan(bid)
        self.assertEqual(self.lib.book(bid)["title"], "Das Hafenlicht")

    def test_search_filter_sort_collections_tags(self):
        self.make()
        self.lib.scan(self.p(""))
        ids = {b["title"]: b["id"] for b in self.lib.books()}
        self.lib.collection_add("Urlaub", ids["Notizen"])
        self.lib.add_tag(ids["Notizen"], "kurz")
        self.lib.set_favorite(ids["Die Sternkarte"])
        self.assertEqual([b["title"] for b in self.lib.books(collection="Urlaub")], ["Notizen"])
        self.assertEqual([b["title"] for b in self.lib.books(query="kurz")], ["Notizen"])
        self.assertEqual([b["title"] for b in self.lib.books(favorites=True)], ["Die Sternkarte"])
        self.assertEqual({b["title"] for b in self.lib.books(fmt="cbz")}, {"c"})
        self.assertEqual(self.lib.books(sort="author")[0]["author"], "")
        self.assertEqual(self.lib.books(query="100%"), [])  # LIKE wildcards are escaped
        self.assertEqual(self.lib.collections(), [{"name": "Urlaub", "n": 1}])

    def test_remove_keeps_files_unless_asked(self):
        self.make()
        self.lib.scan(self.p(""))
        bid = self.lib.books(query="Notizen")[0]["id"]
        self.lib.remove(bid)
        self.assertTrue(os.path.exists(self.p("Karl Klar - Notizen.txt")))
        bid = self.lib.books(query="Sternkarte")[0]["id"]
        self.lib.remove(bid, delete_files=True)
        self.assertFalse(os.path.exists(self.p("b.fb2")))

    def test_progress_and_annotations(self):
        self.make()
        self.lib.scan(self.p(""))
        bid = self.lib.books(query="Hafenlicht")[0]["id"]
        self.lib.set_progress(bid, 1234, 0.4)
        self.assertEqual(self.lib.get_progress(bid)["position"], 1234)
        self.assertEqual(self.lib.books(status="reading")[0]["id"], bid)
        u = self.lib.add_annotation(bid, "highlight", 10, 20, "Mond", "schön")
        self.assertEqual(len(self.lib.annotations(bid)), 1)
        self.lib.delete_annotation(u)
        self.assertEqual(self.lib.annotations(bid), [])
        self.lib.set_progress(bid, 9999, 1.0)
        self.assertEqual(self.lib.book(bid)["status"], "finished")

    def test_prune_missing_is_explicit(self):
        self.make()
        self.lib.scan(self.p(""))
        os.unlink(self.p("c.cbz"))
        self.lib.scan(self.p(""))
        self.assertEqual(len(self.lib.books()), 4)
        self.assertEqual(self.lib.prune_missing(), 1)
        self.assertEqual(len(self.lib.books()), 3)

    def test_entity_bomb_is_rejected(self):
        os.makedirs(self.p(""))
        F._w(self.p("bomb.fb2"), '<?xml version="1.0"?><!DOCTYPE x [<!ENTITY a "aaaa"><!ENTITY b "&a;&a;">]><FictionBook>&b;</FictionBook>')
        r = self.lib.scan(self.p(""))
        self.assertEqual(len(r.broken), 1)


if __name__ == "__main__":
    unittest.main()
