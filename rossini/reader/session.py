"""A reading session: opens a book, restores/saves the position, renders pages."""
import os
import time

from PIL import Image, ImageDraw

from ..fonts import load_font

from . import formats
from .layout import Paginator

class ReaderSession:
    def __init__(self, library, book_id, size, settings=None, file_format=None, clock=time.time):
        self.lib, self.book_id, self.size, self.clock = library, book_id, size, clock
        self.s = settings or {}
        book = library.book(book_id)
        files = [f for f in book["files"] if not f["broken"] and os.path.exists(f["path"])]
        if file_format:
            files = [f for f in files if f["format"] == file_format]
        if not files:
            raise FileNotFoundError("no readable file for this book")
        order = {"epub": 0, "fb2": 1, "txt": 2, "cbz": 3}
        self.file = min(files, key=lambda f: order.get(f["format"], 9))
        self.doc = formats.open_document(self.file["path"])
        self.title = book["title"]
        self.page = 0
        self.opened = clock()
        self.pages_turned = 0
        self.margin, self.footer_h = 40, 70
        if isinstance(self.doc, formats.TextDoc):
            self._layout()
            pr = library.get_progress(book_id)
            self.page = self.paginator.page_for(pr["position"]) if pr else 0
        else:
            pr = library.get_progress(book_id)
            self.page = min(len(self.doc.pages) - 1, int(pr["position"])) if pr else 0

    # --- layout -------------------------------------------------------------
    def _layout(self):
        w, h = self.size
        s = self.s
        margin = int(s.get("reader.margin", 60))
        self.margin = margin
        self.font = load_font(s.get("reader.font", "serif"), int(s.get("reader.font_size", 36)))
        lh = int(self.font.size * float(s.get("reader.line_spacing", 1.35)))
        self.footer_h = 70
        self.paginator = Paginator(self.doc.text, self.font, w - 2 * margin, h - 2 * margin - self.footer_h, lh,
                                   indent=int(self.font.size * 1.2) if s.get("reader.indent", True) else 0)
        self.justify = bool(s.get("reader.justify", True))

    def reflow(self, settings):
        """Apply new reader settings, staying at the same text position."""
        if not isinstance(self.doc, formats.TextDoc):
            return
        pos = self.position()
        self.s = settings
        self._layout()
        self.page = self.paginator.page_for(pos)

    # --- navigation ---------------------------------------------------------
    @property
    def page_count(self):
        return len(self.paginator.pages) if isinstance(self.doc, formats.TextDoc) else len(self.doc.pages)

    def position(self):
        if isinstance(self.doc, formats.TextDoc):
            return self.paginator.pages[self.page].start
        return self.page

    def percent(self):
        return (self.page + 1) / self.page_count if self.page_count else 0.0

    def goto_page(self, n):
        n = max(0, min(self.page_count - 1, n))
        if n != self.page:
            self.pages_turned += 1
        self.page = n
        self.save()

    def next_page(self):
        self.goto_page(self.page + 1)

    def prev_page(self):
        self.goto_page(self.page - 1)

    def goto_offset(self, off):
        self.goto_page(self.paginator.page_for(off))

    def chapters(self):
        return self.doc.toc if isinstance(self.doc, formats.TextDoc) else []

    def goto_chapter(self, i):
        self.goto_offset(self.chapters()[i][1])

    def chapter_index(self):
        toc = self.chapters()
        end = self.paginator.pages[self.page].end
        return max([i for i, (_, o) in enumerate(toc) if o < end], default=-1)

    def search(self, needle, limit=50):
        if not isinstance(self.doc, formats.TextDoc) or not needle:
            return []
        t, n, i, out = self.doc.text.casefold(), needle.casefold(), 0, []
        while len(out) < limit and (i := t.find(n, i)) >= 0:
            out.append(i)
            i += len(n)
        return out

    def save(self):
        self.lib.set_progress(self.book_id, self.position(), self.percent(), self.clock())

    def close(self, log_stats=False):
        self.save()
        if log_stats:
            self.lib.log_reading(self.book_id, int(self.clock() - self.opened), self.pages_turned)

    # --- annotations ----------------------------------------------------------
    def bookmark(self):
        return self.lib.add_annotation(self.book_id, "bookmark", self.position(), text=f"Seite {self.page + 1}")

    def highlight(self, start, end, note=None):
        text = self.doc.text[start:end]
        return self.lib.add_annotation(self.book_id, "note" if note else "highlight", start, end, text, note)

    # --- rendering ------------------------------------------------------------
    def render(self, image=None):
        w, h = self.size
        im = image or Image.new("L", (w, h), 255)
        d = ImageDraw.Draw(im)
        if isinstance(self.doc, formats.ImageDoc):
            pg = self.doc.page_image(self.page)
            pg.thumbnail((w, h - self.footer_h))
            im.paste(pg, ((w - pg.width) // 2, 0))
            self._footer(d, w, h, self.footer_h)
            return im
        page = self.paginator.pages[self.page]
        marks = [(a["start"], a["end"] or a["start"]) for a in self.lib.annotations(self.book_id)
                 if a["kind"] != "bookmark"]
        y = self.margin
        for ln in page.lines:
            x = self.margin + (self.paginator.indent if ln.para_start else 0)
            avail = self.paginator.width - (self.paginator.indent if ln.para_start else 0)
            if self.justify and not ln.last_in_para and " " in ln.text:
                words = ln.text.split(" ")
                extra = (avail - sum(self.font.getlength(w) for w in words)) / (len(words) - 1)
                for wd in words:
                    d.text((x, y), wd, font=self.font, fill=0)
                    x += self.font.getlength(wd) + extra
            else:
                d.text((x, y), ln.text, font=self.font, fill=0)
            for a, b in marks:  # highlights: underline the covered part of the line
                lo, hi = max(a, ln.start), min(b, ln.start + len(ln.text))
                if lo < hi:
                    x0 = self.margin + self.font.getlength(self.doc.text[ln.start:lo]) + (self.paginator.indent if ln.para_start else 0)
                    x1 = x0 + self.font.getlength(self.doc.text[lo:hi])
                    d.line((x0, y + self.font.size + 4, x1, y + self.font.size + 4), fill=0, width=3)
            y += self.paginator.lh
            if ln.last_in_para:
                y += self.paginator.gap
        self._footer(d, w, h, self.footer_h)
        return im

    def _footer(self, d, w, h, fh):
        f = load_font("sans", 26)
        y = h - fh + 10
        d.line((self.margin if hasattr(self, "margin") else 40, y - 8, w - self.margin, y - 8), fill=170, width=2)
        d.text((self.margin, y), self.title[:40], font=f, fill=90)
        label = f"{self.page + 1} / {self.page_count}"
        d.text((w - self.margin - f.getlength(label), y), label, font=f, fill=90)
