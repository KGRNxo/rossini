"""Local WLAN transfer: a small HTTP server that accepts book uploads from a browser on the same
network. Protected by a one-time PIN shown on the device. Only supported extensions are accepted,
size is capped, names are sanitised, files are written atomically and never overwrite."""
import hmac
import os
import secrets
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from ..library.meta import FORMATS
from .opds import MAX_BOOK, safe_name

PAGE = ("<!doctype html><meta charset=utf-8><meta name=viewport content='width=device-width'>"
        "<title>Rossini</title><body style='font:18px system-ui;max-width:30em;margin:2em auto;padding:0 1em'>"
        "<h1>Bücher an Rossini senden</h1><form method=post action='/upload?pin={pin}' enctype='application/octet-stream' "
        "onsubmit=\"event.preventDefault();var f=this.f.files[0];fetch('/upload?pin={pin}&name='+encodeURIComponent(f.name),"
        "{{method:'POST',body:f}}).then(r=>r.text()).then(t=>document.getElementById('o').textContent=t)\">"
        "<input type=file name=f accept='.epub,.fb2,.cbz,.txt' required> <button>Senden</button></form><p id=o></p>")


class TransferServer:
    def __init__(self, dest_dir, on_file=None, host="0.0.0.0", port=0, max_bytes=MAX_BOOK):
        self.dest, self.on_file, self.max_bytes = dest_dir, on_file, max_bytes
        self.pin = f"{secrets.randbelow(10**6):06d}"
        outer = self

        class H(BaseHTTPRequestHandler):
            def log_message(self, *a):
                pass

            def _reply(self, code, body, ctype="text/plain; charset=utf-8"):
                b = body.encode()
                self.send_response(code)
                self.send_header("Content-Type", ctype)
                self.send_header("Content-Length", str(len(b)))
                self.end_headers()
                self.wfile.write(b)

            def _pin_ok(self, q):
                return hmac.compare_digest(q.get("pin", [""])[0], outer.pin)

            def do_GET(self):
                from urllib.parse import parse_qs, urlparse
                u = urlparse(self.path)
                if u.path == "/" and self._pin_ok(parse_qs(u.query)):
                    return self._reply(200, PAGE.format(pin=outer.pin), "text/html; charset=utf-8")
                self._reply(403, "PIN erforderlich: /?pin=…")

            def do_POST(self):
                from urllib.parse import parse_qs, urlparse
                u = urlparse(self.path)
                q = parse_qs(u.query)
                if u.path != "/upload" or not self._pin_ok(q):
                    return self._reply(403, "Falsche PIN")
                name = safe_name(os.path.basename(q.get("name", ["upload"])[0]))
                ext = os.path.splitext(name)[1].lower()
                if ext not in FORMATS:
                    return self._reply(415, f"Format {ext or '?'} wird nicht unterstützt (EPUB, FB2, CBZ, TXT).")
                try:
                    n = int(self.headers.get("Content-Length", ""))
                except ValueError:
                    return self._reply(411, "Content-Length fehlt")
                if n > outer.max_bytes:
                    return self._reply(413, "Datei zu groß")
                os.makedirs(outer.dest, exist_ok=True)
                final, k = os.path.join(outer.dest, name), 1
                while os.path.exists(final):
                    k += 1
                    final = os.path.join(outer.dest, f"{os.path.splitext(name)[0]} ({k}){ext}")
                tmp = final + ".part"
                try:
                    with open(tmp, "wb") as f:
                        left = n
                        while left:
                            chunk = self.rfile.read(min(left, 1 << 16))
                            if not chunk:
                                raise ConnectionError("upload interrupted")
                            f.write(chunk)
                            left -= len(chunk)
                        f.flush()
                        os.fsync(f.fileno())
                    os.replace(tmp, final)
                except Exception:
                    if os.path.exists(tmp):
                        os.unlink(tmp)
                    return self._reply(400, "Übertragung unterbrochen")
                if outer.on_file:
                    outer.on_file(final)
                self._reply(200, f"{os.path.basename(final)} empfangen")

        self.httpd = ThreadingHTTPServer((host, port), H)
        self.port = self.httpd.server_address[1]
        self.thread = threading.Thread(target=self.httpd.serve_forever, daemon=True)

    def start(self):
        self.thread.start()
        return self

    def stop(self):
        self.httpd.shutdown()
        self.httpd.server_close()
