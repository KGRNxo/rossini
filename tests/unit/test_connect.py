import os
import tempfile
import threading
import unittest
import urllib.error
import urllib.request
from http.server import BaseHTTPRequestHandler, HTTPServer

from rossini.connect import opds, sync
from rossini.connect.server import TransferServer
from rossini.library.db import Library
from tests import fixtures as F

FEED = b"""<?xml version="1.0"?><feed xmlns="http://www.w3.org/2005/Atom"><title>Testkatalog</title>
<link rel="next" href="/opds?page=2"/>
<entry><title>Unterkatalog</title><link rel="subsection" type="application/atom+xml;profile=opds-catalog" href="/opds/sub"/></entry>
<entry><title>Das Buch</title><author><name>Eva Autor</name></author>
<link rel="http://opds-spec.org/acquisition" type="application/pdf" href="/b.pdf"/>
<link rel="http://opds-spec.org/acquisition" type="application/epub+zip" href="/b.epub"/></entry>
<entry><title>Nur PDF</title><link rel="http://opds-spec.org/acquisition" type="application/pdf" href="/x.pdf"/></entry>
<entry><title>Kein Link</title></entry></feed>"""


class Srv(BaseHTTPRequestHandler):
    def log_message(self, *a):
        pass

    def do_GET(self):
        if self.path.startswith("/opds"):
            body, ct = FEED, "application/atom+xml"
        elif self.path == "/b.epub":
            F.make_epub("/tmp/_srv.epub", title="Das Buch", author="Eva Autor")
            body, ct = open("/tmp/_srv.epub", "rb").read(), "application/epub+zip"
        else:
            self.send_error(404); return
        self.send_response(200); self.send_header("Content-Length", str(len(body))); self.end_headers(); self.wfile.write(body)


class OpdsTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.srv = HTTPServer(("127.0.0.1", 0), Srv)
        threading.Thread(target=cls.srv.serve_forever, daemon=True).start()
        cls.base = f"http://127.0.0.1:{cls.srv.server_address[1]}"

    @classmethod
    def tearDownClass(cls):
        cls.srv.shutdown(); cls.srv.server_close()

    def test_parse_and_download_into_library(self):
        feed = opds.fetch_feed(self.base + "/opds")
        self.assertEqual(feed.title, "Testkatalog")
        self.assertEqual([e.title for e in feed.entries], ["Unterkatalog", "Das Buch", "Nur PDF"])
        self.assertEqual(feed.entries[0].nav, self.base + "/opds/sub")
        with tempfile.TemporaryDirectory() as d:
            p = opds.download(feed.entries[1], d)
            p2 = opds.download(feed.entries[1], d)
            self.assertNotEqual(p, p2)  # never overwrites
            self.assertEqual(sorted(os.listdir(d)), ["Eva Autor - Das Buch (2).epub", "Eva Autor - Das Buch.epub"])
            lib = Library(":memory:")
            self.assertEqual(lib.scan(d).added, 2)
            self.assertEqual(len(lib.books()), 1)  # same work -> one book
            lib.close()
            with self.assertRaises(opds.FetchError):
                opds.download(feed.entries[2], d)

    def test_rejects_bad_schemes_and_entity_bombs(self):
        for u in ("file:///etc/passwd", "ftp://x/y", "javascript:1"):
            with self.assertRaises(opds.FetchError):
                opds.fetch_feed(u)
        with self.assertRaises(ValueError):
            opds.parse(b'<!DOCTYPE f [<!ENTITY a "x">]><feed xmlns="http://www.w3.org/2005/Atom"><title>&a;</title></feed>', "http://x")

    def test_unreachable_server_raises(self):
        with self.assertRaises(Exception):
            opds.fetch_feed("http://127.0.0.1:9/opds")

    def test_filename_sanitising(self):
        n = opds.safe_name("../../etc/passwd")
        self.assertNotIn("/", n)
        self.assertFalse(n.startswith("."))
        self.assertEqual(opds.safe_name(".."), "book")
        self.assertEqual(opds.safe_name(""), "book")


class TransferTest(unittest.TestCase):
    def test_upload_flow_and_limits(self):
        with tempfile.TemporaryDirectory() as d:
            got = []
            s = TransferServer(d, on_file=got.append, host="127.0.0.1").start()
            self.addCleanup(s.stop)
            base = f"http://127.0.0.1:{s.port}"
            def post(name, data, pin=None):
                req = urllib.request.Request(f"{base}/upload?pin={pin or s.pin}&name={name}", data=data, method="POST")
                try:
                    return urllib.request.urlopen(req).status
                except urllib.error.HTTPError as e:
                    return e.code
            self.assertEqual(post("a.epub", b"PK-data"), 200)
            self.assertEqual(post("a.epub", b"PK-data"), 200)
            self.assertEqual(sorted(os.listdir(d)), ["a (2).epub", "a.epub"])
            self.assertEqual(post("a.exe", b"x"), 415)
            self.assertEqual(post("b.epub", b"x", pin="000000x"), 403)
            self.assertEqual(post("..%2F..%2Fevil.epub", b"x"), 200)
            self.assertFalse(os.path.exists(os.path.join(d, "..", "evil.epub")))
            self.assertEqual(len(got), 3)
            self.assertEqual(urllib.request.urlopen(f"{base}/?pin={s.pin}").status, 200)
            with self.assertRaises(urllib.error.HTTPError):
                urllib.request.urlopen(f"{base}/")
            s.max_bytes = 3
            self.assertEqual(post("big.epub", b"12345"), 413)


class SyncTest(unittest.TestCase):
    def make(self, d, name):
        os.makedirs(f"{d}/{name}")
        F.make_epub(f"{d}/{name}/a.epub")
        lib = Library(f"{d}/{name}.db")
        lib.scan(f"{d}/{name}")
        return lib, lib.books()[0]["id"]

    def test_two_devices_converge_without_loss(self):
        with tempfile.TemporaryDirectory() as d:
            la, ia = self.make(d, "a"); lb, ib = self.make(d, "b")
            shared = f"{d}/share"; os.makedirs(shared)
            la.set_progress(ia, 100, 0.1, when=10); lb.set_progress(ib, 900, 0.9, when=20)
            ua = la.add_annotation(ia, "bookmark", 5, text="a")
            sync.sync_dir(la, shared); sync.sync_dir(lb, shared); sync.sync_dir(la, shared)
            self.assertEqual(la.get_progress(ia)["position"], 900)
            self.assertEqual(lb.get_progress(ib)["position"], 900)
            self.assertEqual([a["uid"] for a in lb.annotations(ib)], [ua])
            lb.delete_annotation(ua)
            sync.sync_dir(lb, shared); sync.sync_dir(la, shared)
            self.assertEqual(la.annotations(ia), [])
            before = open(f"{shared}/{sync.FILE}").read()
            sync.sync_dir(la, shared)
            self.assertEqual(open(f"{shared}/{sync.FILE}").read(), before)  # idempotent
            la.close(); lb.close()

    def test_corrupt_remote_is_not_overwritten(self):
        with tempfile.TemporaryDirectory() as d:
            la, ia = self.make(d, "a")
            os.makedirs(f"{d}/s")
            with open(f"{d}/s/{sync.FILE}", "w") as f:
                f.write("{broken")
            with self.assertRaises(ValueError):
                sync.sync_dir(la, f"{d}/s")
            self.assertEqual(open(f"{d}/s/{sync.FILE}").read(), "{broken")
            la.close()


class Dav(BaseHTTPRequestHandler):
    """Minimal WebDAV file endpoint with ETag preconditions, like Nextcloud for a single file."""
    store = {}
    puts = 0

    def log_message(self, *a):
        pass

    def _auth(self):
        import base64
        if self.headers.get("Authorization") != "Basic " + base64.b64encode(b"kai:pw").decode():
            self.send_response(401); self.end_headers(); return False
        return True

    def do_GET(self):
        if not self._auth():
            return
        if self.path not in self.store:
            self.send_response(404); self.end_headers(); return
        body, tag = self.store[self.path]
        self.send_response(200); self.send_header("ETag", tag); self.send_header("Content-Length", str(len(body))); self.end_headers()
        self.wfile.write(body)

    def do_PUT(self):
        if not self._auth():
            return
        body = self.rfile.read(int(self.headers["Content-Length"]))
        cur = self.store.get(self.path)
        if (self.headers.get("If-None-Match") == "*" and cur) or (self.headers.get("If-Match") and (not cur or cur[1] != self.headers["If-Match"])):
            self.send_response(412); self.end_headers(); return
        Dav.puts += 1
        self.store[self.path] = (body, f'"{Dav.puts}"')
        self.send_response(201); self.end_headers()


class WebDavTest(unittest.TestCase):
    def test_sync_with_etags_auth_and_conflict_retry(self):
        srv = HTTPServer(("127.0.0.1", 0), Dav)
        threading.Thread(target=srv.serve_forever, daemon=True).start()
        self.addCleanup(lambda: (srv.shutdown(), srv.server_close()))
        url = f"http://127.0.0.1:{srv.server_address[1]}/dav/rossini"
        with tempfile.TemporaryDirectory() as d:
            mk = SyncTest.make
            la, ia = mk(self, d, "a"); lb, ib = mk(self, d, "b")
            la.set_progress(ia, 100, 0.1, when=10)
            sync.sync_webdav(la, url, "kai", "pw")
            lb.set_progress(ib, 500, 0.5, when=20)
            # another device writes between our GET and PUT: the first PUT must fail with 412 and be retried
            real = urllib.request.urlopen
            raced = []
            def opener(req):
                if req.get_method() == "PUT" and not raced:
                    raced.append(1)
                    Dav.store["/dav/rossini/" + sync.FILE] = (Dav.store["/dav/rossini/" + sync.FILE][0], '"other"')
                return real(req, timeout=10)
            sync.sync_webdav(lb, url, "kai", "pw", opener=opener)
            sync.sync_webdav(la, url, "kai", "pw")
            self.assertEqual(la.get_progress(ia)["position"], 500)
            with self.assertRaises(urllib.error.HTTPError):
                sync.sync_webdav(la, url, "kai", "falsch")
            la.close(); lb.close()

    def test_credentials_file_is_private(self):
        from rossini.connect.credentials import Credentials
        with tempfile.TemporaryDirectory() as d:
            c = Credentials(d + "/cred.json")
            self.assertEqual(c.get("webdav"), (None, None))
            c.set("webdav", "kai", "pw")
            self.assertEqual(c.get("webdav"), ("kai", "pw"))
            self.assertEqual(os.stat(d + "/cred.json").st_mode & 0o777, 0o600)
            c.delete("webdav")
            self.assertEqual(c.get("webdav"), (None, None))


if __name__ == "__main__":
    unittest.main()
