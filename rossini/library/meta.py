"""Metadata extraction for every format the reader can open. Formats whose decoder is missing on this system
(PyMuPDF for PDF, djvulibre for DjVu) are not offered at all. All input is untrusted: size limits, no path
traversal, no entity expansion; external decoders run as separate processes."""
import base64
import io
import os
import posixpath
import re
import zipfile
from dataclasses import dataclass, field

from ..common import local, safe_xml

import importlib.util
import shutil

FORMATS = {".epub": "epub", ".fb2": "fb2", ".cbz": "cbz", ".cbr": "cbr", ".txt": "txt", ".mobi": "mobi",
           ".azw3": "azw3", ".azw": "azw", ".prc": "mobi", ".rtf": "rtf", ".html": "html", ".htm": "html", ".xhtml": "html"}
if importlib.util.find_spec("pymupdf") or importlib.util.find_spec("fitz"):
    FORMATS[".pdf"] = "pdf"
if shutil.which("ddjvu") and shutil.which("djvused"):
    FORMATS[".djvu"] = "djvu"
MAX_ENTRY = 32 * 1024 * 1024
IMG_EXT = (".jpg", ".jpeg", ".png", ".gif", ".webp")
FONT_OBFUSCATION = ("http://www.idpf.org/2008/embedding", "http://ns.adobe.com/pdf/enc#RC")


class Broken(Exception):
    """File is unreadable or protected; str(e) is the reason stored in the library."""


@dataclass
class Meta:
    title: str
    author: str = ""
    series: str = None
    series_index: float = None
    language: str = None
    cover: bytes = None  # JPEG thumbnail
    extra: dict = field(default_factory=dict)


def thumbnail(raw):
    from PIL import Image
    try:
        im = Image.open(io.BytesIO(raw))
        im.draft("RGB", (800, 1200))
        im = im.convert("L")
        im.thumbnail((480, 640))
        out = io.BytesIO()
        im.save(out, "JPEG", quality=82)
        return out.getvalue()
    except Exception:
        return None


def _read(z, name):
    name = posixpath.normpath(name)
    if name.startswith(("/", "..")):
        raise Broken("unsafe path in archive")
    info = z.getinfo(name)
    if info.file_size > MAX_ENTRY:
        raise Broken("archive entry too large")
    return z.read(info)


def from_filename(path):
    stem = os.path.splitext(os.path.basename(path))[0].replace("_", " ").strip()
    if " - " in stem:
        a, t = stem.split(" - ", 1)
        return Meta(title=t.strip() or stem, author=a.strip())
    return Meta(title=stem or "Untitled")


def _epub(path):
    try:
        z = zipfile.ZipFile(path)
    except zipfile.BadZipFile as e:
        raise Broken("not a valid zip/epub") from e
    with z:
        if "META-INF/encryption.xml" in z.namelist():
            enc = _read(z, "META-INF/encryption.xml").decode("utf-8", "replace")
            algos = re.findall(r'Algorithm="([^"]+)"', enc)
            if any(a not in FONT_OBFUSCATION for a in algos):
                raise Broken("drm")
        try:
            cont = safe_xml(_read(z, "META-INF/container.xml"))
            rootfile = next(e.get("full-path") for e in cont.iter() if local(e.tag) == "rootfile")
            opf = safe_xml(_read(z, rootfile))
        except (KeyError, StopIteration, ValueError, Exception) as e:
            if isinstance(e, Broken):
                raise
            raise Broken("epub container/opf unreadable") from e
        base = posixpath.dirname(rootfile)
        dc, metas, manifest = {}, {}, {}
        for e in opf.iter():
            t = local(e.tag)
            if t in ("title", "creator", "language") and (e.text or "").strip():
                dc.setdefault(t, []).append(e.text.strip())
            elif t == "meta":
                if e.get("name"):
                    metas[e.get("name")] = e.get("content")
                elif e.get("property") == "belongs-to-collection" and e.text:
                    metas.setdefault("calibre:series", e.text.strip())
                elif e.get("property") == "group-position" and e.text:
                    metas.setdefault("calibre:series_index", e.text.strip())
            elif t == "item":
                manifest[e.get("id")] = (e.get("href"), e.get("properties") or "")
        m = Meta(title=(dc.get("title") or [None])[0] or from_filename(path).title,
                 author=" & ".join(dc.get("creator", [])),
                 language=(dc.get("language") or [None])[0])
        m.series = metas.get("calibre:series")
        try:
            m.series_index = float(metas["calibre:series_index"])
        except (KeyError, ValueError, TypeError):
            pass
        cover_href = next((h for h, p in manifest.values() if "cover-image" in p.split()), None)
        if not cover_href and metas.get("cover") in manifest:
            cover_href = manifest[metas["cover"]][0]
        if cover_href:
            try:
                m.cover = thumbnail(_read(z, posixpath.join(base, cover_href)))
            except (KeyError, Broken):
                pass
        return m


def _fb2(path):
    try:
        with open(path, "rb") as f:
            data = f.read(MAX_ENTRY + 1)
        if len(data) > MAX_ENTRY:
            raise Broken("file too large")
        root = safe_xml(data)
    except (ValueError, Exception) as e:
        if isinstance(e, Broken):
            raise
        raise Broken("fb2 xml unreadable") from e
    ti = next((e for e in root.iter() if local(e.tag) == "title-info"), None)
    if ti is None:
        raise Broken("fb2 without title-info")
    m = from_filename(path)
    cover_id = None
    for e in ti:
        t = local(e.tag)
        if t == "book-title" and e.text:
            m.title = e.text.strip()
        elif t == "lang" and e.text:
            m.language = e.text.strip()
        elif t == "author" and not m.author:
            parts = {local(c.tag): (c.text or "").strip() for c in e}
            m.author = " ".join(p for p in (parts.get("first-name"), parts.get("last-name")) if p)
        elif t == "sequence":
            m.series = e.get("name")
            try:
                m.series_index = float(e.get("number"))
            except (TypeError, ValueError):
                pass
        elif t == "coverpage":
            for i in e:
                cover_id = (i.get("{http://www.w3.org/1999/xlink}href") or "").lstrip("#")
    if cover_id:
        for b in root.iter():
            if local(b.tag) == "binary" and b.get("id") == cover_id and b.text:
                try:
                    m.cover = thumbnail(base64.b64decode(b.text))
                except ValueError:
                    pass
    return m


def cbz_pages(z):
    return sorted(n for n in z.namelist() if n.lower().endswith(IMG_EXT) and not n.endswith("/"))


def _cbz(path):
    try:
        z = zipfile.ZipFile(path)
    except zipfile.BadZipFile as e:
        raise Broken("not a valid zip/cbz") from e
    with z:
        pages = cbz_pages(z)
        if not pages:
            raise Broken("cbz contains no images")
        m = from_filename(path)
        try:
            m.cover = thumbnail(_read(z, pages[0]))
        except (KeyError, Broken):
            pass
        m.extra["pages"] = len(pages)
        return m


def _txt(path):
    with open(path, "rb") as f:
        head = f.read(4096)
    if b"\x00" in head:
        raise Broken("binary data, not text")
    return from_filename(path)


def _paged(path):
    """pdf, djvu, cbr: open with the reader backend; cover = first page."""
    from ..reader import paged
    ext = os.path.splitext(path)[1].lower()
    doc = {".pdf": paged.PdfDoc, ".djvu": paged.DjvuDoc, ".cbr": paged.ComicDoc}[ext](path)
    m = Meta(title=doc.title or from_filename(path).title, author=getattr(doc, "author", "") or from_filename(path).author)
    m.extra["pages"] = doc.page_count
    try:
        out = io.BytesIO()
        doc.raw_page(0, 640).save(out, "PNG")
        m.cover = thumbnail(out.getvalue())
    except Exception:
        pass
    return m


def _mobi(path):
    from ..reader.mobi import Mobi
    mb = Mobi(path)
    m = Meta(title=mb.title or from_filename(path).title, author=mb.author)
    c = mb.cover()
    if c:
        m.cover = thumbnail(c)
    return m


def _text_title(path):
    with open(path, "rb") as f:
        head = f.read(65536)
    if os.path.splitext(path)[1].lower() == ".rtf":
        if not head.lstrip().startswith(b"{\\rtf"):
            raise Broken("not an RTF file")
        return from_filename(path)
    t = re.search(rb"<title[^>]*>(.*?)</title>", head, re.I | re.S)
    m = from_filename(path)
    if t and t.group(1).strip():
        m.title = " ".join(t.group(1).decode("utf-8", "replace").split())
    return m


EXTRACTORS = {"epub": _epub, "fb2": _fb2, "cbz": _cbz, "txt": _txt, "pdf": _paged, "djvu": _paged, "cbr": _paged,
              "mobi": _mobi, "azw3": _mobi, "azw": _mobi, "rtf": _text_title, "html": _text_title}


def extract(path):
    fmt = FORMATS.get(os.path.splitext(path)[1].lower())
    if not fmt:
        raise Broken("unsupported format")
    return fmt, EXTRACTORS[fmt](path)
