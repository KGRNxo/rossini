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
              cover=True, body_repeat=40):
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
