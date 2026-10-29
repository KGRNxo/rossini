"""Document decoders. Text formats (epub, fb2, txt) yield one plain-text stream with chapter
offsets so that a reading position is a character offset that survives any font change.
Images inside EPUB/FB2 are not rendered (text only). cbz is paged by image.
Formats without a decoder here (pdf, mobi, azw3, djvu, rtf, html, cbr) raise Unsupported."""
import io
import posixpath
import zipfile
from dataclasses import dataclass, field
from html.parser import HTMLParser

from ..common import local, safe_xml
from ..library import meta as M

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


@dataclass
class ImageDoc:
    title: str
    path: str
    pages: list

    def page_image(self, i):
        from PIL import Image
        with zipfile.ZipFile(self.path) as z:
            info = z.getinfo(self.pages[i])
            if info.file_size > M.MAX_ENTRY:
                raise ValueError("image too large")
            im = Image.open(io.BytesIO(z.read(info)))
            im.load()
            return im.convert("L")


class _Text(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.out, self.skip, self.heads, self._h = [], 0, [], None

    def handle_starttag(self, tag, attrs):
        if tag in SKIP:
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


def _normalize(parts):
    """Collapse whitespace inside paragraphs, keep one blank line between paragraphs."""
    paras = [" ".join(p.split()) for p in "".join(parts).split("\n")]
    return "\n".join(p for p in paras if p)


def _html_to_paras(html):
    p = _Text()
    p.feed(html)
    p.close()
    paras = []
    for line in "".join(p.out).split("\n"):
        line = " ".join(line.split())
        if line:
            paras.append(line)
    return paras, [(" ".join(h[0].split()), h[1]) for h in p.heads]


def _epub(path):
    with zipfile.ZipFile(path) as z:
        cont = safe_xml(M._read(z, "META-INF/container.xml"))
        rootfile = next(e.get("full-path") for e in cont.iter() if local(e.tag) == "rootfile")
        opf = safe_xml(M._read(z, rootfile))
        base = posixpath.dirname(rootfile)
        manifest, spine, title = {}, [], None
        for e in opf.iter():
            t = local(e.tag)
            if t == "item":
                manifest[e.get("id")] = e.get("href")
            elif t == "itemref":
                spine.append(e.get("idref"))
            elif t == "title" and title is None and e.text:
                title = e.text.strip()
        text, starts, headings = [], {}, {}
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
            paras, heads = _html_to_paras(data)
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
        return TextDoc(title or "Untitled", "".join(text), toc)


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
    title = M._fb2(path).title
    paras, toc, total = [], [], 0
    for body in (e for e in root if local(e.tag) == "body"):
        for sec in body.iter():
            if local(sec.tag) == "title":
                label = " ".join("".join(sec.itertext()).split())
                if label:
                    toc.append((label, total))
                    paras.append(label)
                    total += len(label) + 1
            elif local(sec.tag) == "p":
                t = " ".join("".join(sec.itertext()).split())
                if t and not _inside_title(body, sec):
                    paras.append(t)
                    total += len(t) + 1
    return TextDoc(title, "\n".join(paras) + "\n", toc)


def _inside_title(body, p):
    return any(local(t.tag) == "title" and p in list(t.iter()) for t in body.iter())


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


def _cbz(path):
    with zipfile.ZipFile(path) as z:
        pages = M.cbz_pages(z)
    if not pages:
        raise M.Broken("cbz contains no images")
    return ImageDoc(M.from_filename(path).title, path, pages)


DECODERS = {"epub": _epub, "fb2": _fb2, "txt": _txt, "cbz": _cbz}
UNSUPPORTED = ("pdf", "mobi", "azw3", "azw", "djvu", "rtf", "html", "htm", "cbr")


def open_document(path):
    ext = path.rsplit(".", 1)[-1].lower()
    if ext in UNSUPPORTED:
        raise Unsupported(f"no decoder for .{ext}")
    if ext not in DECODERS:
        raise Unsupported(f"unknown format .{ext}")
    return DECODERS[ext](path)
