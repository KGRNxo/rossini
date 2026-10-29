"""Pagination: greedy line breaking with real font metrics. Reading positions are character
offsets, so changing font/size/margins re-flows to the same place."""
import bisect
from dataclasses import dataclass


@dataclass
class Line:
    start: int  # char offset of first char of the line in the document text
    text: str
    para_start: bool
    last_in_para: bool


@dataclass
class Page:
    start: int
    end: int
    lines: list


class Paginator:
    def __init__(self, text, font, width, height, line_height, para_gap=0.5, indent=0):
        self.text, self.font, self.width, self.height = text, font, width, height
        self.lh, self.gap, self.indent = line_height, int(line_height * para_gap), indent
        self._w = {}
        self.pages = self._paginate()
        self._starts = [p.start for p in self.pages]

    def _len(self, s):
        v = self._w.get(s)
        if v is None:
            v = self._w[s] = self.font.getlength(s)
        return v

    def _break(self, para, offset, first_indent):
        """Yield (start, text) lines for one paragraph beginning at text[offset]."""
        words, pos, i = [], 0, 0
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
                    yield line_start, " ".join(line)
                    line, cur_w, avail = [], 0.0, self.width
                yield ws, w[:k]
                w, ws = w[k:], ws + k
                ww = self._len(w)
                avail = self.width
            add = ww + (space if line else 0)
            if line and cur_w + add > avail:
                yield line_start, " ".join(line)
                line, cur_w, avail = [], 0.0, self.width
                add = ww
            if not line:
                line_start = ws
            line.append(w)
            cur_w += add
        if line:
            yield line_start, " ".join(line)

    def _paginate(self):
        pages, cur, y, off = [], [], 0, 0
        for para in self.text.split("\n"):
            if para:
                lines = list(self._break(para, off, self.indent))
                for n, (s, t) in enumerate(lines):
                    need = self.lh + (self.gap if n == len(lines) - 1 else 0)
                    if cur and y + self.lh > self.height:
                        pages.append(Page(cur[0].start, s, cur))
                        cur, y = [], 0
                    cur.append(Line(s, t, n == 0, n == len(lines) - 1))
                    y += need
            off += len(para) + 1
        if cur or not pages:
            pages.append(Page(cur[0].start if cur else 0, len(self.text), cur))
        return pages

    def page_for(self, offset):
        return max(0, bisect.bisect_right(self._starts, offset) - 1)
