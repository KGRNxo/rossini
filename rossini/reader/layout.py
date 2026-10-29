"""Pagination: greedy line breaking with real font metrics, optional hyphenation, inline image blocks.
Reading positions are character offsets, so changing font/size/margins re-flows to the same place.
An image is a paragraph consisting of the single character IMAGE (U+FFFC)."""
import bisect
from dataclasses import dataclass

IMAGE = "￼"


@dataclass
class Line:
    start: int  # char offset of first char of the line in the document text
    text: str
    para_start: bool
    last_in_para: bool
    hyphen: bool = False   # draw a trailing '-' (word continues on the next line)
    height: int = 0        # >0: image block of this height instead of text


@dataclass
class Page:
    start: int
    end: int
    lines: list


class Paginator:
    def __init__(self, text, font, width, height, line_height, para_gap=0.5, indent=0, hyphenator=None, image_size=None):
        """hyphenator: object with positions(word) (pyphen.Pyphen); image_size(offset) -> (w, h) in source pixels."""
        self.text, self.font, self.width, self.height = text, font, width, height
        self.lh, self.gap, self.indent = line_height, int(line_height * para_gap), indent
        self.hyph, self.image_size = hyphenator, image_size
        self._w = {}
        self.pages = self._paginate()
        self._starts = [p.start for p in self.pages]

    def _len(self, s):
        v = self._w.get(s)
        if v is None:
            v = self._w[s] = self.font.getlength(s)
        return v

    def _split(self, w, room):
        """Longest hyphenation prefix of w that fits into room (with the hyphen), or 0."""
        if not self.hyph or len(w) < 5 or not w.isalpha():
            return 0
        for p in sorted(self.hyph.positions(w), reverse=True):
            if p >= 2 and len(w) - p >= 2 and self._len(w[:p] + "-") <= room:
                return p
        return 0

    def _break(self, para, offset, first_indent):
        """Yield (start, text, hyphen) lines for one paragraph beginning at text[offset]."""
        words, pos = [], 0
        for w in para.split(" "):
            words.append((offset + pos, w))
            pos += len(w) + 1
        line, line_start, cur_w, space = [], None, 0.0, self._len(" ")
        avail = self.width - first_indent
        for ws, w in words:
            ww = self._len(w)
            while ww > self.width:  # unbreakable word wider than the page: hard split
                k = max(1, int(len(w) * self.width / ww))
                while k > 1 and self._len(w[:k]) > self.width:
                    k -= 1
                if line:
                    yield line_start, " ".join(line), False
                    line, cur_w, avail = [], 0.0, self.width
                yield ws, w[:k], False
                w, ws = w[k:], ws + k
                ww = self._len(w)
                avail = self.width
            add = ww + (space if line else 0)
            if line and cur_w + add > avail:
                p = self._split(w, avail - cur_w - space)
                if p:
                    line.append(w[:p])
                    yield line_start, " ".join(line), True
                    w, ws, ww = w[p:], ws + p, self._len(w[p:])
                else:
                    yield line_start, " ".join(line), False
                line, cur_w, avail = [], 0.0, self.width
                add = ww
            if not line:
                line_start = ws
            line.append(w)
            cur_w += add
        if line:
            yield line_start, " ".join(line), False

    def _image_height(self, off):
        w, h = self.image_size(off) if self.image_size else (0, 0)
        if not w or not h:
            return 0
        k = min(1.0 * self.width / w, self.height * 0.9 / h, 2.0)
        return max(self.lh, int(h * k))

    def _paginate(self):
        pages, cur, y, off = [], [], 0, 0

        def flush(next_start):
            nonlocal cur, y
            pages.append(Page(cur[0].start, next_start, cur))
            cur, y = [], 0

        for para in self.text.split("\n"):
            if para == IMAGE:
                ih = self._image_height(off)
                if ih:
                    if cur and y + ih > self.height:
                        flush(off)
                    cur.append(Line(off, "", True, True, height=ih))
                    y += ih + self.gap
            elif para:
                lines = list(self._break(para, off, self.indent))
                for n, (s, t, hy) in enumerate(lines):
                    need = self.lh + (self.gap if n == len(lines) - 1 else 0)
                    if cur and y + self.lh > self.height:
                        flush(s)
                    cur.append(Line(s, t, n == 0, n == len(lines) - 1, hy))
                    y += need
            off += len(para) + 1
        if cur or not pages:
            pages.append(Page(cur[0].start if cur else 0, len(self.text), cur))
        return pages

    def page_for(self, offset):
        return max(0, bisect.bisect_right(self._starts, offset) - 1)
