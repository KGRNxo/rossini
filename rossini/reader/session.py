"""A reading session: opens a book, restores/saves the position, renders pages.
Flowing documents (TextDoc) are paginated with the user's typography; fixed-layout documents (PagedDoc)
are shown page by page with optional margin crop and zoom (the zoomed page is walked tile by tile)."""
import io
import math
import os
import time

from PIL import Image, ImageDraw, ImageOps

from ..fonts import load_font
from . import formats
from .layout import IMAGE, Paginator
from .paged import PagedDoc

ZOOMS = (1.0, 1.5, 2.0, 3.0)
ORDER = {"epub": 0, "azw3": 1, "mobi": 2, "fb2": 3, "html": 4, "rtf": 5, "txt": 6, "pdf": 7, "djvu": 8, "cbz": 9, "cbr": 10}


def hyphenator(lang):
    """pyphen dictionary for the book language (fallback German); None if pyphen is unavailable."""
    try:
        import pyphen
    except ImportError:
        return None
    lang = (lang or "de").replace("_", "-")
    for cand in (lang, lang.split("-")[0], "de_DE"):
        try:
            return pyphen.Pyphen(lang=cand)
        except KeyError:
            continue
    return None


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
        self.file = min(files, key=lambda f: ORDER.get(f["format"], 99))
        self.doc = formats.open_document(self.file["path"], reflow=bool(self.s.get("reader.pdf_reflow")))
        self.title = book["title"]
        self.language = book.get("language")
        self.page, self.tile, self.zoom = 0, 0, 1.0
        self._page_cache = None
        self.opened = clock()
        self.pages_turned = 0
        self.margin, self.footer_h = 40, 70
        self.word_boxes = []
        pr = library.get_progress(book_id)
        if self.flowing:
            self._layout()
            if pr:
                self.page = self.paginator.page_for(pr["position"]) if pr.get("kind") in (None, "text") \
                    else self._page_from_percent(pr["percent"])
        elif pr:
            self.page = min(self.doc.page_count - 1, int(pr["position"])) if pr.get("kind") in (None, "page") \
                else self._page_from_percent(pr["percent"])

    @property
    def flowing(self):
        return isinstance(self.doc, formats.TextDoc)

    @property
    def kind(self):
        return "text" if self.flowing else "page"

    def _page_from_percent(self, pct):
        return max(0, min(self.page_count - 1, int(round(pct * self.page_count)) - 1))

    # --- layout -------------------------------------------------------------
    def _layout(self):
        w, h = self.size
        s = self.s
        self.margin = margin = int(s.get("reader.margin", 60))
        self.font = load_font(s.get("reader.font", "serif"), int(s.get("reader.font_size", 36)))
        lh = int(self.font.size * float(s.get("reader.line_spacing", 1.35)))
        self.footer_h = 70
        hy = hyphenator(self.doc.language or self.language) if s.get("reader.hyphenation", True) else None
        self.paginator = Paginator(self.doc.text, self.font, w - 2 * margin, h - 2 * margin - self.footer_h, lh,
                                   indent=int(self.font.size * 1.2) if s.get("reader.indent", True) else 0,
                                   hyphenator=hy, image_size=self._image_size)
        self.justify = bool(s.get("reader.justify", True))

    def _image(self, off):
        loader = self.doc.images.get(off)
        if not loader:
            return None
        try:
            im = Image.open(io.BytesIO(loader()))
            return im
        except Exception:
            return None

    def _image_size(self, off):
        im = self._image(off)
        return im.size if im else (0, 0)

    def reflow(self, settings):
        """Apply new reader settings, staying at the same position."""
        reflow_changed = bool(settings.get("reader.pdf_reflow")) != bool(self.s.get("reader.pdf_reflow")) and self.file["format"] == "pdf"
        if reflow_changed:
            pct = self.percent()
            self.s = settings
            self.doc = formats.open_document(self.file["path"], reflow=bool(settings.get("reader.pdf_reflow")))
            self.page, self.tile, self._page_cache = 0, 0, None
            if self.flowing:
                self._layout()
            self.page = self._page_from_percent(pct)
            return
        if not self.flowing:
            self.s, self._page_cache = settings, None
            return
        pos = self.position()
        self.s = settings
        self._layout()
        self.page = self.paginator.page_for(pos)

    # --- navigation ---------------------------------------------------------
    @property
    def page_count(self):
        return len(self.paginator.pages) if self.flowing else self.doc.page_count

    def position(self):
        return self.paginator.pages[self.page].start if self.flowing else self.page

    def percent(self):
        return (self.page + 1) / self.page_count if self.page_count else 0.0

    def goto_page(self, n, tile=0):
        n = max(0, min(self.page_count - 1, n))
        if n != self.page:
            self.pages_turned += 1
        self.page, self.tile = n, tile
        self.save()

    def tiles(self):
        """(columns, rows) of the zoomed page; (1, 1) when not zoomed."""
        if self.flowing or self.zoom == 1.0:
            return 1, 1
        im = self._page()
        w, h = self.size
        return max(1, math.ceil(im.width / w)), max(1, math.ceil(im.height / (h - self.footer_h)))

    def next_page(self):
        c, r = self.tiles()
        if self.tile < c * r - 1:
            self.tile += 1
        else:
            self.goto_page(self.page + 1)

    def prev_page(self):
        if self.tile > 0:
            self.tile -= 1
        elif self.page > 0:
            self.goto_page(self.page - 1)
            c, r = self.tiles()
            self.tile = c * r - 1

    def set_zoom(self, step):
        """step +1/-1 through ZOOMS (fixed-layout documents only)."""
        i = max(0, min(len(ZOOMS) - 1, ZOOMS.index(self.zoom) + step))
        self.zoom, self.tile, self._page_cache = ZOOMS[i], 0, None

    def goto_offset(self, off):
        self.goto_page(self.paginator.page_for(off) if self.flowing else off)

    def chapters(self):
        """(label, position): position is a char offset (flowing) or a page index (fixed layout)."""
        return self.doc.toc

    def goto_chapter(self, i):
        self.goto_offset(self.chapters()[i][1])

    def chapter_index(self):
        toc = self.chapters()
        end = self.paginator.pages[self.page].end if self.flowing else self.page + 1
        return max([i for i, (_, o) in enumerate(toc) if o < end], default=-1)

    def search(self, needle, limit=50):
        """Char offsets (flowing) or page indices (PDF) of matches."""
        if not needle:
            return []
        if not self.flowing:
            return self.doc.search_pages(needle, limit) if hasattr(self.doc, "search_pages") else []
        t, n, i, out = self.doc.text.casefold(), needle.casefold(), 0, []
        while len(out) < limit and (i := t.find(n, i)) >= 0:
            out.append(i)
            i += len(n)
        return out

    def save(self):
        self.lib.set_progress(self.book_id, self.position(), self.percent(), self.clock(), kind=self.kind)

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

    def word_at(self, x, y):
        """(start, end) char offsets of the word under a point of the last rendered page, or None."""
        for x0, y0, x1, y1, a, b in self.word_boxes:
            if x0 <= x <= x1 and y0 <= y <= y1:
                return a, b
        return None

    # --- rendering ------------------------------------------------------------
    def _page(self):
        key = (self.page, self.zoom, bool(self.s.get("reader.pdf_crop", True)))
        if not self._page_cache or self._page_cache[0] != key:
            w, h = self.size
            self._page_cache = (key, self.doc.page_image(self.page, (w, h - self.footer_h), self.zoom, key[2]))
        return self._page_cache[1]

    def render(self, image=None):
        w, h = self.size
        im = image or Image.new("L", (w, h), 255)
        d = ImageDraw.Draw(im)
        self.word_boxes = []
        if not self.flowing:
            pg = self._page()
            c, r = self.tiles()
            if (c, r) == (1, 1):
                im.paste(pg, ((w - pg.width) // 2, (h - self.footer_h - pg.height) // 2))
            else:
                th = h - self.footer_h
                cx, cy = self.tile % c, self.tile // c
                x0 = min(cx * w, max(0, pg.width - w))
                y0 = min(cy * th, max(0, pg.height - th))
                im.paste(pg.crop((x0, y0, x0 + w, y0 + th)), (0, 0))
            self._footer(d, w, h, self.footer_h)
            return self._finish(im)
        page = self.paginator.pages[self.page]
        marks = [(a["start"], a["end"] or a["start"]) for a in self.lib.annotations(self.book_id)
                 if a["kind"] != "bookmark"]
        y, f = self.margin, self.font
        for ln in page.lines:
            if ln.height:
                pic = self._image(ln.start)
                if pic:
                    pic = ImageOps.exif_transpose(pic).convert("L")
                    k = ln.height / pic.height
                    pic = pic.resize((max(1, int(pic.width * k)), ln.height), Image.LANCZOS)
                    im.paste(pic, ((w - pic.width) // 2, y))
                y += ln.height + self.paginator.gap
                continue
            indent = self.paginator.indent if ln.para_start else 0
            x = self.margin + indent
            words = ln.text.split(" ")
            extra = 0.0
            if self.justify and not ln.last_in_para and len(words) > 1:
                avail = self.paginator.width - indent - (f.getlength("-") if ln.hyphen else 0)
                extra = (avail - sum(f.getlength(wd) for wd in words)) / (len(words) - 1) - f.getlength(" ")
            off = ln.start
            for i, wd in enumerate(words):
                shown = wd + ("-" if ln.hyphen and i == len(words) - 1 else "")
                d.text((x, y), shown, font=f, fill=0)
                ww = f.getlength(shown)
                self.word_boxes.append((x, y, x + ww, y + self.paginator.lh, off, off + len(wd)))
                for a, b in marks:  # highlights: underline the covered part of the word
                    lo, hi = max(a, off), min(b, off + len(wd))
                    if lo < hi:
                        x0 = x + f.getlength(wd[:lo - off])
                        x1 = x + f.getlength(wd[:hi - off])
                        d.line((x0, y + f.size + 4, x1 + (f.getlength(" ") if hi == off + len(wd) and b > hi and i < len(words) - 1 else 0),
                                y + f.size + 4), fill=0, width=3)
                x += ww + f.getlength(" ") + extra
                off += len(wd) + 1
            y += self.paginator.lh
            if ln.last_in_para:
                y += self.paginator.gap
        self._footer(d, w, h, self.footer_h)
        return self._finish(im)

    def _finish(self, im):
        return ImageOps.invert(im) if self.s.get("reader.invert") else im

    def _footer(self, d, w, h, fh):
        f = load_font("sans", 26)
        y = h - fh + 10
        d.line((self.margin, y - 8, w - self.margin, y - 8), fill=170, width=2)
        d.text((self.margin, y), self.title[:40], font=f, fill=90)
        c, r = self.tiles()
        label = f"{self.page + 1} / {self.page_count}" + (f"  ·  {self.tile + 1}/{c * r}" if c * r > 1 else "")
        d.text((w - self.margin - f.getlength(label), y), label, font=f, fill=90)
