"""Document decoders. Flowing formats (epub, fb2, txt, html, rtf, mobi/azw3, pdf in reflow mode) yield one
plain-text stream with chapter offsets, so a reading position is a character offset that survives any font
change. Fixed-layout formats (pdf, djvu, cbz/cbr) are PagedDoc objects (see paged.py)."""
import base64
import posixpath
import re
import zipfile
from dataclasses import dataclass, field
from html.parser import HTMLParser

from ..common import local, safe_xml
from ..library import meta as M
from . import paged
from .layout import IMAGE

BLOCK = {"p", "div", "br", "li", "tr", "blockquote", "section", "h1", "h2", "h3", "h4", "h5", "h6", "title", "pre"}
HEAD = {"h1", "h2", "h3", "h4", "h5", "h6"}
SKIP = {"script", "style", "head", "svg"}


class Unsupported(Exception):
    pass


@dataclass
class TextDoc:
    title: str
    text: str
    toc: list = field(default_factory=list)  # (label, char offset)
    images: dict = field(default_factory=dict)  # char offset of an IMAGE paragraph -> callable returning image bytes
    language: str = None


class _Text(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.out, self.skip, self.heads, self._h, self.imgs = [], 0, [], None, []

    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        src = a.get("src") or a.get("xlink:href") or a.get("href") if tag in ("img", "image") else None
        if tag == "img" and a.get("recindex"):
            src = "recindex:" + a["recindex"]  # MOBI image reference
        if src and not self.skip:
            self.out.append(f"\n{IMAGE}\n")
            self.imgs.append(src)
        elif tag in SKIP:
            self.skip += 1
        elif tag in BLOCK:
            self.out.append("\n")
            if tag in HEAD:
                self._h = (len("".join(self.out)), [])

    def handle_endtag(self, tag):
        if tag in SKIP:
            self.skip = max(0, self.skip - 1)
        elif tag in BLOCK:
            self.out.append("\n")
            if tag in HEAD and self._h:
                self.heads.append((" ".join("".join(self._h[1]).split()), self._h[0]))
                self._h = None

    def handle_data(self, d):
        if not self.skip:
            self.out.append(d)
            if self._h:
                self._h[1].append(d)


def _html_to_paras(html, with_images=False):
    """-> paragraphs, headings[, image sources in the order of their IMAGE paragraphs]"""
    p = _Text()
    p.feed(html)
    p.close()
    paras = []
    for line in "".join(p.out).split("\n"):
        line = " ".join(line.split())
        if line:
            paras.append(line)
    heads = [(" ".join(h[0].split()), h[1]) for h in p.heads]
    if not with_images:
        return [x for x in paras if x != IMAGE], heads
    return paras, heads, p.imgs


def _attach_images(paras, srcs, base_offset, resolve, images):
    """Map each IMAGE paragraph's offset to a loader; drops IMAGE paragraphs whose source cannot be resolved."""
    out, off, it = [], base_offset, iter(srcs)
    for para in paras:
        if para == IMAGE:
            loader = resolve(next(it, None))
            if not loader:
                continue
            images[off] = loader
        out.append(para)
        off += len(para) + 1
    return out


def _zip_loader(path, name):
    def load():
        with zipfile.ZipFile(path) as z:
            return M._read(z, name)
    return load


def _epub(path):
    with zipfile.ZipFile(path) as z:
        names = set(z.namelist())
        cont = safe_xml(M._read(z, "META-INF/container.xml"))
        rootfile = next(e.get("full-path") for e in cont.iter() if local(e.tag) == "rootfile")
        opf = safe_xml(M._read(z, rootfile))
        base = posixpath.dirname(rootfile)
        manifest, spine, title, lang = {}, [], None, None
        for e in opf.iter():
            t = local(e.tag)
            if t == "item":
                manifest[e.get("id")] = e.get("href")
            elif t == "itemref":
                spine.append(e.get("idref"))
            elif t == "title" and title is None and e.text:
                title = e.text.strip()
            elif t == "language" and lang is None and e.text:
                lang = e.text.strip()
        text, starts, headings, images = [], {}, {}, {}
        total = 0
        for idref in spine:
            href = manifest.get(idref)
            if not href or not href.lower().endswith((".xhtml", ".html", ".htm", ".xml")):
                continue
            full = posixpath.normpath(posixpath.join(base, href))
            try:
                data = M._read(z, full).decode("utf-8", "replace")
            except (KeyError, M.Broken):
                continue
            paras, heads, srcs = _html_to_paras(data, with_images=True)
            item_dir = posixpath.dirname(full)

            def resolve(src, item_dir=item_dir):
                if not src or ":" in src.split("/")[0]:
                    return None
                name = posixpath.normpath(posixpath.join(item_dir, src.split("#")[0]))
                return _zip_loader(path, name) if name in names else None
            paras = _attach_images(paras, srcs, total, resolve, images)
            if not paras:
                continue
            starts[full] = total
            body = "\n".join(paras) + "\n"
            # heading offsets inside this item: recompute by searching the paragraph text
            first_head = heads[0][0] if heads else None
            if first_head:
                headings[full] = first_head
            text.append(body)
            total += len(body)
        toc = _epub_toc(z, opf, manifest, base, starts)
        if not toc:
            toc = [(headings.get(f) or posixpath.basename(f), o) for f, o in starts.items()]
        return TextDoc(title or "Untitled", "".join(text), toc, images, lang)


def _epub_toc(z, opf, manifest, base, starts):
    toc = []
    ncx = next((h for h in manifest.values() if h and h.endswith(".ncx")), None)
    if not ncx:
        return toc
    try:
        root = safe_xml(M._read(z, posixpath.normpath(posixpath.join(base, ncx))))
    except (KeyError, ValueError, M.Broken):
        return toc
    ncx_dir = posixpath.dirname(posixpath.normpath(posixpath.join(base, ncx)))
    for np_ in root.iter():
        if local(np_.tag) != "navPoint":
            continue
        label = next((t.text for t in np_.iter() if local(t.tag) == "text" and t.text), "").strip()
        src = next((c.get("src") for c in np_ if local(c.tag) == "content"), None)
        if src:
            full = posixpath.normpath(posixpath.join(ncx_dir, src.split("#")[0]))
            if full in starts and label:
                toc.append((label, starts[full]))
    return toc


def _fb2(path):
    with open(path, "rb") as f:
        root = safe_xml(f.read(M.MAX_ENTRY))
    meta = M._fb2(path)
    binaries = {b.get("id"): b.text for b in root.iter() if local(b.tag) == "binary" and b.get("id") and b.text}
    paras, toc, images = [], [], {}
    total = 0

    def add(t):
        nonlocal total
        paras.append(t)
        total += len(t) + 1

    def walk(el):
        for c in el:
            t = local(c.tag)
            if t == "title":
                label = " ".join("".join(c.itertext()).split())
                if label:
                    toc.append((label, total))
                    add(label)
            elif t in ("p", "v", "subtitle", "text-author"):
                txt = " ".join("".join(c.itertext()).split())
                if txt:
                    add(txt)
            elif t == "image":
                ref = (c.get("{http://www.w3.org/1999/xlink}href") or "").lstrip("#")
                if ref in binaries:
                    images[total] = (lambda d=binaries[ref]: base64.b64decode(d))
                    add(IMAGE)
            else:
                walk(c)

    for body in (e for e in root if local(e.tag) == "body"):
        walk(body)
    return TextDoc(meta.title, "\n".join(paras) + "\n", toc, images, meta.language)


def _txt(path):
    with open(path, "rb") as f:
        raw = f.read(M.MAX_ENTRY)
    try:
        s = raw.decode("utf-8")
    except UnicodeDecodeError:
        s = raw.decode("latin-1")
    paras = [" ".join(p.split()) for p in s.replace("\r\n", "\n").split("\n")]
    text = "\n".join(p for p in paras if p) + "\n"
    return TextDoc(M.from_filename(path).title, text, [])


def _toc_from_heads(text, heads):
    toc, pos = [], 0
    for label, _ in heads:  # heading offsets: find each heading paragraph in order
        i = text.find(label + "\n", pos)
        if i >= 0:
            toc.append((label, i))
            pos = i + 1
    return toc


def _html_doc(html, title):
    paras, heads = _html_to_paras(html)
    text = "\n".join(paras) + "\n"
    return TextDoc(title, text, _toc_from_heads(text, heads))


def _html(path):
    # shortcut: images of single HTML files are not shown (only text); upgrade by resolving <img> inside the file's folder
    with open(path, "rb") as f:
        raw = f.read(M.MAX_ENTRY)
    html = raw.decode("utf-8", "replace")
    m = re.search(r"<title[^>]*>(.*?)</title>", html, re.I | re.S)
    return _html_doc(html, " ".join(m.group(1).split()) if m and m.group(1).strip() else M.from_filename(path).title)


def _mobi(path):
    from .mobi import Mobi
    mb = Mobi(path)
    paras, heads, srcs = _html_to_paras(mb.html(), with_images=True)
    images = {}

    def resolve(src):
        if not src or not src.startswith("recindex:") or mb.first_image is None:
            return None
        i = mb.first_image + int(src.split(":")[1]) - 1
        return (lambda i=i: mb.records[i]) if 0 <= i < len(mb.records) else None
    paras = _attach_images(paras, srcs, 0, resolve, images)
    doc = _html_doc("", mb.title or M.from_filename(path).title)
    doc.text = "\n".join(paras) + "\n"
    doc.images = images
    doc.toc = _toc_from_heads(doc.text, heads)
    return doc


def _rtf(path):
    from .rtf import rtf_to_text
    with open(path, "rb") as f:
        text = rtf_to_text(f.read(M.MAX_ENTRY))
    paras = [" ".join(p.split()) for p in text.split("\n")]
    return TextDoc(M.from_filename(path).title, "\n".join(p for p in paras if p) + "\n", [])


def _pdf(path, reflow=False):
    doc = paged.PdfDoc(path)
    if not reflow:
        return doc
    text, starts = doc.text()
    return TextDoc(doc.title, text, [(t, starts[p]) for t, p in doc.toc if p < len(starts)])


DECODERS = {"epub": _epub, "fb2": _fb2, "txt": _txt, "cbz": paged.ComicDoc, "cbr": paged.ComicDoc, "pdf": _pdf,
            "djvu": paged.DjvuDoc, "mobi": _mobi, "azw3": _mobi, "azw": _mobi, "prc": _mobi, "rtf": _rtf,
            "html": _html, "htm": _html, "xhtml": _html}


def open_document(path, reflow=False):
    """reflow: open fixed-layout PDFs as flowing text."""
    ext = path.rsplit(".", 1)[-1].lower()
    if ext not in DECODERS:
        raise Unsupported(f"unknown format .{ext}")
    try:
        return _pdf(path, reflow) if ext == "pdf" else DECODERS[ext](path)
    except M.Broken as e:
        raise Unsupported(str(e)) from e
