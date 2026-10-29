"""Drawing primitives for the E-Ink shell. Design units (u) scale with screen width so the same
layout fits 6"-10" panels: 1u = width/1072 px at ui_scale 1."""
import io

from PIL import Image, ImageDraw

from ..fonts import load_font

INK, PAPER, RULE, MUTE, SOFT = 0, 255, 187, 102, 238  # 102 on 255 = 6.0:1 contrast


class Canvas:
    def __init__(self, size, scale=1.0):
        self.w, self.h = size
        self.k = size[0] / 1072 * scale
        self.im = Image.new("L", size, PAPER)
        self.d = ImageDraw.Draw(self.im)
        self.hits = []

    def u(self, n):
        return int(round(n * self.k))

    def font(self, size, bold=False, serif=False):
        return load_font("serif" if serif else "sans", self.u(size), bold)

    # --- text ---------------------------------------------------------------
    def fit(self, text, font, maxw):
        if font.getlength(text) <= maxw:
            return text
        while text and font.getlength(text + "…") > maxw:
            text = text[:-1]
        return text.rstrip() + "…"

    def text(self, x, y, s, size, bold=False, serif=False, fill=INK, maxw=None, anchor="l"):
        f = self.font(size, bold, serif)
        if maxw:
            s = self.fit(s, f, maxw)
        if anchor == "r":
            x -= f.getlength(s)
        elif anchor == "m":
            x -= f.getlength(s) / 2
        self.d.text((x, y), s, font=f, fill=fill)
        return f.size

    def wrap(self, s, size, maxw, lines, bold=False, serif=False):
        f = self.font(size, bold, serif)
        out, cur = [], ""
        words = s.split()
        for i, w in enumerate(words):
            t = (cur + " " + w).strip()
            if f.getlength(t) <= maxw or not cur:
                cur = t
            else:
                out.append(cur)
                cur = w
            if len(out) == lines:
                break
        else:
            out.append(cur)
        out = out[:lines]
        if len(out) == lines and " ".join(out) != " ".join(words):
            out[-1] = self.fit(out[-1] + " …", f, maxw) if f.getlength(out[-1] + " …") > maxw else out[-1] + " …"
        return out

    def paragraph(self, x, y, s, size, maxw, lines=99, bold=False, serif=False, fill=INK, gap=1.35):
        f = self.font(size, bold, serif)
        for ln in self.wrap(s, size, maxw, lines, bold, serif):
            self.d.text((x, y), ln, font=f, fill=fill)
            y += int(f.size * gap)
        return y

    # --- shapes ---------------------------------------------------------------
    def rule(self, y, x0=None, x1=None, fill=RULE, w=2):
        self.d.line((x0 if x0 is not None else self.u(56), y, x1 if x1 is not None else self.w - self.u(56), y),
                    fill=fill, width=w)

    def hit(self, rect, fn):
        self.hits.append((rect, fn))

    def button(self, rect, label, fn=None, primary=False, enabled=True, size=34):
        x0, y0, x1, y1 = rect
        r = self.u(14)
        if primary:
            self.d.rounded_rectangle(rect, r, fill=INK if enabled else RULE)
            fg = PAPER
        else:
            self.d.rounded_rectangle(rect, r, outline=INK if enabled else RULE, width=max(2, self.u(3)))
            fg = INK if enabled else RULE
        f = self.font(size, bold=True)
        self.d.text(((x0 + x1) / 2, (y0 + y1) / 2), label, font=f, fill=fg, anchor="mm")
        if fn and enabled:
            self.hit(rect, fn)

    def progress(self, x, y, w, frac, h=None):
        h = h or self.u(10)
        self.d.rounded_rectangle((x, y, x + w, y + h), h // 2, fill=SOFT, outline=RULE)
        if frac > 0:
            self.d.rounded_rectangle((x, y, x + max(h, int(w * frac)), y + h), h // 2, fill=INK)

    def cover(self, rect, blob, title=""):
        x0, y0, x1, y1 = rect
        bw, bh = x1 - x0, y1 - y0
        if blob:
            try:
                im = Image.open(io.BytesIO(blob)).convert("L")
                k = min(bw / im.width, bh / im.height)
                im = im.resize((max(1, int(im.width * k)), max(1, int(im.height * k))))
                px, py = x0 + (bw - im.width) // 2, y1 - im.height
                self.im.paste(im, (px, py))
                self.d.rectangle((px, py, px + im.width - 1, py + im.height - 1), outline=MUTE, width=2)
                return
            except Exception:
                pass
        self.d.rectangle(rect, fill=SOFT, outline=MUTE, width=2)
        self.d.text(((x0 + x1) / 2, (y0 + y1) / 2), (title[:1] or "?").upper(), font=self.font(int(bh / self.k * 0.35), True, True),
                    fill=MUTE, anchor="mm")

    def icon(self, name, cx, cy, s, fill=INK):
        """Line icons drawn with one stroke weight."""
        d, w = self.d, max(3, self.u(4))
        a = s // 2
        if name == "home":
            d.line((cx - a, cy, cx, cy - a, cx + a, cy), fill=fill, width=w, joint="curve")
            d.line((cx - a + 6, cy, cx - a + 6, cy + a, cx + a - 6, cy + a, cx + a - 6, cy), fill=fill, width=w, joint="curve")
        elif name == "library":
            for i, h in enumerate((a * 2, a * 2 - 8, a * 2)):
                x = cx - a + i * (s // 3) + 2
                d.rectangle((x, cy + a - h, x + s // 3 - 8, cy + a), outline=fill, width=w)
        elif name == "read":
            d.line((cx, cy - a + 4, cx, cy + a), fill=fill, width=w)
            d.line((cx, cy - a + 4, cx - a, cy - a + 10, cx - a, cy + a - 2, cx, cy + a), fill=fill, width=w, joint="curve")
            d.line((cx, cy - a + 4, cx + a, cy - a + 10, cx + a, cy + a - 2, cx, cy + a), fill=fill, width=w, joint="curve")
        elif name == "discover":
            d.ellipse((cx - a, cy - a, cx + a, cy + a), outline=fill, width=w)
            d.polygon([(cx + a // 2, cy - a // 2), (cx + 3, cy + 3), (cx - a // 2, cy + a // 2), (cx - 3, cy - 3)], outline=fill, width=max(2, w - 1))
        elif name == "settings":
            for i, off in enumerate((-a // 2 - 2, 4, a // 2 + 6)):
                y = cy + off - 2
                d.line((cx - a, y, cx + a, y), fill=fill, width=w)
                kx = cx + (-a // 3 if i != 1 else a // 3)
                d.ellipse((kx - 7, y - 7, kx + 7, y + 7), fill=PAPER, outline=fill, width=w)
        elif name == "back":
            d.line((cx + a // 2, cy - a, cx - a // 2, cy, cx + a // 2, cy + a), fill=fill, width=w, joint="curve")
        elif name == "wifi":
            for r in (a, a * 2 // 3, a // 3):
                d.arc((cx - r, cy - r + a // 2, cx + r, cy + r + a // 2), 225, 315, fill=fill, width=w)
        elif name == "chevron":
            d.line((cx - a // 2, cy - a, cx + a // 2, cy, cx - a // 2, cy + a), fill=fill, width=w, joint="curve")

    def battery(self, x, y, pct, charging=False):
        w, h = self.u(40), self.u(20)
        self.d.rounded_rectangle((x, y, x + w, y + h), 4, outline=INK, width=2)
        self.d.rectangle((x + w, y + h // 4, x + w + 4, y + h - h // 4), fill=INK)
        if pct is not None:
            self.d.rectangle((x + 4, y + 4, x + 4 + int((w - 8) * pct / 100), y + h - 4), fill=INK)
        return w + 6
