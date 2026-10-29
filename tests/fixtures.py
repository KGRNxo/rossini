"""Builders for small, valid sample books used across tests."""
import base64
import io
import zipfile

from PIL import Image


def png(color=128, size=(60, 90)):
    b = io.BytesIO()
    Image.new("L", size, color).save(b, "PNG")
    return b.getvalue()


def _w(path, text):
    with open(path, "w", encoding="utf-8") as f:
        f.write(text)


LOREM = ("Der Mond stand hoch über dem Hafen und niemand wusste, wer die Laterne angezündet hatte. "
         "Sie gingen langsam an den Booten vorbei, jeder in seine Gedanken versunken. ")


def make_epub(path, title="Das Hafenlicht", author="Anna Beispiel", chapters=3, series=None, encrypted=False,
              cover=True, body_repeat=40, inline_image=False):
    items, spine, nav = [], [], []
    with zipfile.ZipFile(path, "w") as z:
        z.writestr("mimetype", "application/epub+zip")
        z.writestr("META-INF/container.xml",
                   '<?xml version="1.0"?><container xmlns="urn:oasis:names:tc:opendocument:xmlns:container" version="1.0">'
                   '<rootfiles><rootfile full-path="OEBPS/content.opf" media-type="application/oebps-package+xml"/></rootfiles></container>')
        if encrypted:
            z.writestr("META-INF/encryption.xml",
                       '<encryption xmlns="urn:oasis:names:tc:opendocument:xmlns:container"><EncryptedData>'
                       '<EncryptionMethod Algorithm="http://www.w3.org/2001/04/xmlenc#aes128-cbc"/></EncryptedData></encryption>')
        for i in range(1, chapters + 1):
            body = "".join(f"<p>{LOREM}</p>" for _ in range(body_repeat))
            if inline_image and i == 1:
                body += '<p><img src="cover.png" alt=""/></p><img src="../../escape.png"/><p>Nach dem Bild.</p>'
            z.writestr(f"OEBPS/c{i}.xhtml",
                       f'<?xml version="1.0"?><html xmlns="http://www.w3.org/1999/xhtml"><head><title>x</title><style>p{{}}</style></head>'
                       f"<body><h1>Kapitel {i}</h1>{body}</body></html>")
            items.append(f'<item id="c{i}" href="c{i}.xhtml" media-type="application/xhtml+xml"/>')
            spine.append(f'<itemref idref="c{i}"/>')
            nav.append(f'<navPoint id="n{i}"><navLabel><text>Kapitel {i}</text></navLabel><content src="c{i}.xhtml"/></navPoint>')
        z.writestr("OEBPS/toc.ncx", '<ncx xmlns="http://www.daisy.org/z3986/2005/ncx/"><navMap>' + "".join(nav) + "</navMap></ncx>")
        items.append('<item id="ncx" href="toc.ncx" media-type="application/x-dtbncx+xml"/>')
        extra = ""
        if cover:
            z.writestr("OEBPS/cover.png", png())
            items.append('<item id="cov" href="cover.png" media-type="image/png" properties="cover-image"/>')
        if series:
            extra = f'<meta name="calibre:series" content="{series}"/><meta name="calibre:series_index" content="2"/>'
        z.writestr("OEBPS/content.opf",
                   '<?xml version="1.0"?><package xmlns="http://www.idpf.org/2007/opf" version="3.0">'
                   f'<metadata xmlns:dc="http://purl.org/dc/elements/1.1/"><dc:title>{title}</dc:title>'
                   f"<dc:creator>{author}</dc:creator><dc:language>de</dc:language>{extra}</metadata>"
                   f'<manifest>{"".join(items)}</manifest><spine toc="ncx">{"".join(spine)}</spine></package>')
    return path


def make_fb2(path, title="Die Sternkarte", first="Bernd", last="Fiktiv"):
    cover = base64.b64encode(png(200)).decode()
    _w(path,
        '<?xml version="1.0" encoding="utf-8"?><FictionBook xmlns="http://www.gribuser.ru/xml/fictionbook/2.0" '
        'xmlns:l="http://www.w3.org/1999/xlink"><description><title-info><author><first-name>%s</first-name>'
        '<last-name>%s</last-name></author><book-title>%s</book-title><lang>de</lang>'
        '<sequence name="Sterne" number="3"/><coverpage><image l:href="#c.png"/></coverpage></title-info></description>'
        '<body><section><title><p>Anfang</p></title><p>%s</p><p>Zweiter Absatz.</p></section></body>'
        '<binary id="c.png" content-type="image/png">%s</binary></FictionBook>' % (first, last, title, LOREM * 5, cover))
    return path


def make_cbz(path, pages=3):
    with zipfile.ZipFile(path, "w") as z:
        for i in range(pages):
            z.writestr(f"p{i:03d}.png", png(40 * i + 20, (200, 300)))
    return path


def make_txt(path, text=None):
    _w(path, text or (LOREM * 30 + "\n\n") * 5)
    return path


def make_pdf(path, pages=3, title="PDF Titel", author="Petra Autor"):
    import pymupdf
    d = pymupdf.open()
    for i in range(pages):
        p = d.new_page(width=420, height=595)
        p.insert_text((72, 300), f"Seite {i + 1}: Der Leuchtturm am Kai.", fontsize=12)
    d.set_metadata({"title": title, "author": author})
    d.set_toc([[1, "Anfang", 1], [1, "Ende", pages]])
    d.save(path)
    d.close()
    return path


def palmdoc_compress(data):
    """Greedy LZ77 in PalmDOC format (literal runs and distance/length pairs) for test files."""
    out, i = bytearray(), 0
    while i < len(data):
        best = (0, 0)
        for dist in range(1, min(i, 2047) + 1):
            n = 0
            while n < 10 and i + n < len(data) and data[i + n - dist] == data[i + n]:
                n += 1
            if n >= 3 and n > best[1]:
                best = (dist, n)
        if best[1]:
            pair = 0x8000 | (best[0] << 3) | (best[1] - 3)
            out += pair.to_bytes(2, "big")
            i += best[1]
        else:
            run = data[i:i + 1]
            c = run[0]
            if c == 0 or 0x09 <= c <= 0x7F:
                out += run
            else:
                out += b"\x01" + run
            i += 1
    return bytes(out)


def make_mobi(path, title="Mobi Titel", author="Max Mobi", paragraphs=30, compress=True, encrypted=False):
    import struct
    html = ("<html><body><h1>Erstes Kapitel</h1>" + "".join(f"<p>{LOREM} Nr. {i}</p>" for i in range(paragraphs))
            + '<p><img recindex="00001"/></p><h1>Zweites Kapitel</h1><p>Schluss.</p></body></html>').encode("utf-8")
    recs_text = []
    for i in range(0, len(html), 4096):
        chunk = html[i:i + 4096]
        body = palmdoc_compress(chunk) if compress else chunk
        recs_text.append(body + b"\x00" + b"XY\x83")  # multibyte byte + one trailing entry of size 3
    name = title.encode()
    exth_recs = [(100, author.encode()), (201, struct.pack(">I", 0))]
    exth = b"".join(struct.pack(">II", t, len(v) + 8) + v for t, v in exth_recs)
    exth = b"EXTH" + struct.pack(">II", 12 + len(exth), len(exth_recs)) + exth
    first_image = 1 + len(recs_text)
    mobi = bytearray(232)
    mobi[0:4] = b"MOBI"
    struct.pack_into(">II", mobi, 4, 232, 2)
    struct.pack_into(">I", mobi, 12, 65001)
    struct.pack_into(">I", mobi, 92, first_image)          # header offset 0x5C -> record offset 108
    struct.pack_into(">I", mobi, 112, 0x40)                 # EXTH present (record offset 128)
    struct.pack_into(">H", mobi, 0xF2 - 16, 0b11)           # extra flags (record offset 0xF2)
    rec0 = bytearray(struct.pack(">HHIHHHH", 2 if compress else 1, 0, len(html), len(recs_text), 4096, 1 if encrypted else 0, 0))
    rec0 += mobi + exth
    struct.pack_into(">II", rec0, 84, len(rec0), len(name))
    rec0 += name + b"\0\0"
    records = [bytes(rec0)] + recs_text + [png(30, (50, 80))]
    header = bytearray(78)
    header[:len(title[:31])] = title[:31].encode()
    header[60:68] = b"BOOKMOBI"
    struct.pack_into(">H", header, 76, len(records))
    off = 78 + 8 * len(records) + 2
    table = b""
    for i, r in enumerate(records):
        table += struct.pack(">II", off, i)
        off += len(r)
    with open(path, "wb") as f:
        f.write(bytes(header) + table + b"\0\0" + b"".join(records))
    return path


def make_djvu(path, pages=2):
    import os
    import subprocess
    import tempfile
    from PIL import ImageDraw
    with tempfile.TemporaryDirectory() as d:
        parts = []
        for i in range(pages):
            im = Image.new("L", (400, 560), 255)
            ImageDraw.Draw(im).rectangle((60, 80, 340, 480 - i * 40), fill=0)
            im.save(f"{d}/p{i}.pgm")
            subprocess.run(["c44", f"{d}/p{i}.pgm", f"{d}/p{i}.djvu"], check=True, capture_output=True)
            parts.append(f"{d}/p{i}.djvu")
        subprocess.run(["djvm", "-c", path] + parts, check=True, capture_output=True)
    return path


def make_cbr_7z(path, pages=2):
    import subprocess
    import tempfile
    with tempfile.TemporaryDirectory() as d:
        for i in range(pages):
            with open(f"{d}/p{i:02d}.png", "wb") as f:
                f.write(png(60 * i + 30, (200, 300)))
        subprocess.run(["bsdtar", "--format", "7zip", "-cf", path, "-C", d, "."], check=True, capture_output=True)
    return path


RTF = (rb"{\rtf1\ansi\ansicpg1252\deff0{\fonttbl{\f0 Times;}}{\colortbl;\red0\green0\blue0;}"
       rb"{\info{\title Versteckt}}\f0\fs24 Erster Absatz mit \'e4 und \u8364? Euro.\par "
       rb"{\*\generator Test;}Zweiter \b fetter\b0  Absatz.\par}")


def make_stardict(directory, name="test", entries=None, compress=True):
    import gzip
    import os
    import struct
    entries = entries or {"Mond": "Erdtrabant; moon", "Hafen": "Anlegestelle für Schiffe; harbour", "Laterne": "Lampe; lantern"}
    os.makedirs(directory, exist_ok=True)
    data, idx = b"", b""
    for w in sorted(entries, key=str.casefold):
        d = entries[w].encode()
        idx += w.encode() + b"\0" + struct.pack(">II", len(data), len(d))
        data += d
    base = os.path.join(directory, name)
    with open(base + ".ifo", "w") as f:
        f.write(f"StarDict's dict ifo file\nversion=2.4.2\nbookname=Test {name}\nwordcount={len(entries)}\n"
                f"idxfilesize={len(idx)}\nsametypesequence=m\n")
    with open(base + ".idx", "wb") as f:
        f.write(idx)
    if compress:
        with gzip.open(base + ".dict.dz", "wb") as f:
            f.write(data)
    else:
        with open(base + ".dict", "wb") as f:
            f.write(data)
    return base + ".ifo"
