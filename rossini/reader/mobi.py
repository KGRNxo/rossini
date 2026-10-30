"""MOBI / AZW3 (KF8) reader for DRM-free files: PalmDB container, PalmDOC (LZ77) decompression, trailing
record entries, EXTH metadata, cover image. HUFF/CDIC-compressed and encrypted books are refused.
shortcut: KF8 text is read as one stream of skeleton+fragment HTML in storage order, which matches reading order
for normal books; files with reordered fragments may show sections out of order. Upgrade: parse the FDST/SKEL/FRAG indexes."""
import struct

from ..library.meta import Broken

MAX_RECORDS = 65536


def palmdoc_decompress(data):
    out = bytearray()
    i, n = 0, len(data)
    while i < n:
        c = data[i]; i += 1
        if c == 0 or 0x09 <= c <= 0x7F:
            out.append(c)
        elif c <= 0x08:
            out += data[i:i + c]; i += c
        elif c >= 0xC0:
            out += b" " + bytes([c ^ 0x80])
        else:
            if i >= n:
                break
            pair = (c << 8) | data[i]; i += 1
            dist, length = (pair & 0x3FFF) >> 3, (pair & 7) + 3
            if dist == 0 or dist > len(out):
                raise Broken("corrupt PalmDOC stream")
            for _ in range(length):
                out.append(out[-dist])
    return bytes(out)


def _entry_size(rec, end):
    """Backward-encoded integer ending at rec[end-1] (high bit marks the first byte)."""
    num = 0
    for v in rec[max(0, end - 4):end]:
        if v & 0x80:
            num = 0
        num = (num << 7) | (v & 0x7F)
    return num


def _trailing_size(rec, flags):
    """Size of the trailing entries the MOBI writer appended to a text record."""
    size, f = 0, flags >> 1
    while f:
        if f & 1:
            size += _entry_size(rec, len(rec) - size)
        f >>= 1
    if flags & 1 and len(rec) > size:
        size += (rec[len(rec) - size - 1] & 3) + 1
    return min(size, len(rec))


class Mobi:
    def __init__(self, path):
        with open(path, "rb") as f:
            self.data = data = f.read(64 << 20)
        if len(data) < 78 or data[60:68] not in (b"BOOKMOBI", b"TEXtREAd"):
            raise Broken("not a MOBI/PalmDOC file")
        n = struct.unpack(">H", data[76:78])[0]
        if not 1 <= n <= MAX_RECORDS or 78 + 8 * n > len(data):
            raise Broken("corrupt PalmDB record list")
        offs = [struct.unpack(">I", data[78 + 8 * i:82 + 8 * i])[0] for i in range(n)] + [len(data)]
        if any(b < a for a, b in zip(offs, offs[1:])) or offs[-2] > len(data):
            raise Broken("corrupt PalmDB offsets")
        self.records = [data[offs[i]:offs[i + 1]] for i in range(n)]
        r0 = self.records[0]
        self.compression, self.text_len, self.text_count = struct.unpack(">HxxIH", r0[:10])
        encryption = struct.unpack(">H", r0[12:14])[0]
        if encryption:
            raise Broken("drm")
        if self.compression not in (1, 2):
            raise Broken("unsupported MOBI compression (HUFF/CDIC)")
        self.title, self.author, self.extra_flags, self.encoding = None, "", 0, "cp1252"
        self.first_image, self.cover_offset = None, None
        if r0[16:20] == b"MOBI":
            hlen = struct.unpack(">I", r0[20:24])[0]
            enc = struct.unpack(">I", r0[28:32])[0]
            self.encoding = "utf-8" if enc == 65001 else "cp1252"
            name_off, name_len = struct.unpack(">II", r0[84:92])
            self.title = r0[name_off:name_off + name_len].decode(self.encoding, "replace") or None
            if hlen >= 0x5C:
                self.first_image = struct.unpack(">I", r0[108:112])[0]
            if hlen >= 0xE4:
                self.extra_flags = struct.unpack(">H", r0[0xF2:0xF4])[0]
            exth_flag = struct.unpack(">I", r0[128:132])[0]
            if exth_flag & 0x40:
                self._exth(r0[16 + hlen:])
        elif data[60:68] == b"TEXtREAd":
            self.title = data[:32].split(b"\0")[0].decode("latin-1")

    def _exth(self, b):
        if b[:4] != b"EXTH":
            return
        count = struct.unpack(">I", b[8:12])[0]
        pos, authors = 12, []
        for _ in range(min(count, 1000)):
            typ, ln = struct.unpack(">II", b[pos:pos + 8])
            val = b[pos + 8:pos + ln]
            if typ == 100:
                authors.append(val.decode(self.encoding, "replace"))
            elif typ == 503:
                self.title = val.decode(self.encoding, "replace")
            elif typ == 201 and len(val) == 4:
                self.cover_offset = struct.unpack(">I", val)[0]
            pos += max(ln, 8)
        self.author = " & ".join(authors)

    def html(self):
        out = bytearray()
        for rec in self.records[1:1 + self.text_count]:
            rec = rec[:len(rec) - _trailing_size(rec, self.extra_flags)] if self.extra_flags else rec
            out += palmdoc_decompress(rec) if self.compression == 2 else rec
            if len(out) > 64 << 20:
                raise Broken("text too large")
        return bytes(out[:self.text_len] if self.text_len else out).decode(self.encoding, "replace")

    def cover(self):
        if self.first_image is None or self.cover_offset is None:
            return None
        i = self.first_image + self.cover_offset
        return self.records[i] if i < len(self.records) else None
