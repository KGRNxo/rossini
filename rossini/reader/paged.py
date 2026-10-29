"""Fixed-layout documents (PDF, DjVu, comic archives). Each backend renders one page to a gray image;
optional automatic margin crop. Zoom/pan is handled by the reading session."""
import io
import os
import shutil
import subprocess
import zipfile

from PIL import Image, ImageOps

from ..library import meta as M

try:
    import pymupdf
except ImportError:  # older PyMuPDF (e.g. Buildroot) only provides the 'fitz' name
    try:
        import fitz as pymupdf
    except ImportError:
        pymupdf = None

TIMEOUT = 60


def content_bbox(im, threshold=235, pad=8):
    """Bounding box of the non-blank area of a page (for margin cropping), or None if blank."""
    mask = im.point(lambda v: 255 if v < threshold else 0)
    bb = mask.getbbox()
    if not bb:
        return None
    return (max(0, bb[0] - pad), max(0, bb[1] - pad), min(im.width, bb[2] + pad), min(im.height, bb[3] + pad))


def fit(im, w, h, zoom=1.0):
    """zoom 1: whole page fits the box. zoom >1: page width = zoom * box width (taller than the box)."""
    k = min(w / im.width, h / im.height) if zoom == 1.0 else w * zoom / im.width
    return im.resize((max(1, int(im.width * k)), max(1, int(im.height * k))), Image.LANCZOS)


class PagedDoc:
    title = ""
    toc = []          # (label, page index)
    language = None
    images = {}

    def raw_page(self, i, longest):
        raise NotImplementedError

    def page_image(self, i, box, zoom=1.0, crop=False):
        w, h = box
        im = self.raw_page(i, int(max(w, h) * max(1.0, zoom) * 1.3))
        if crop:
            bb = content_bbox(im)
            if bb:
                im = im.crop(bb)
        return fit(im, w, h, zoom)


class PdfDoc(PagedDoc):
    def __init__(self, path):
        if pymupdf is None:
            raise M.Broken("PDF-Unterstützung (PyMuPDF) ist nicht installiert")
        try:
            self.doc = pymupdf.open(path)
        except Exception as e:
            raise M.Broken(f"PDF nicht lesbar: {type(e).__name__}") from e
        if self.doc.needs_pass:
            raise M.Broken("drm")
        md = self.doc.metadata or {}
        self.title = md.get("title") or M.from_filename(path).title
        self.author = md.get("author") or ""
        self.page_count = self.doc.page_count
        self.toc = [(t, max(0, p - 1)) for _, t, p, *rest in self.doc.get_toc()]

    def raw_page(self, i, longest):
        page = self.doc[i]
        k = longest / max(page.rect.width, page.rect.height)
        pix = page.get_pixmap(matrix=pymupdf.Matrix(k, k), colorspace=pymupdf.csGRAY, alpha=False)
        return Image.frombytes("L", (pix.width, pix.height), pix.samples)

    def search_pages(self, needle, limit=50):
        n, out = needle.casefold(), []
        for i, p in enumerate(self.doc):
            if n in p.get_text().casefold():
                out.append(i)
                if len(out) >= limit:
                    break
        return out

    def text(self):
        """Plain text for reflow mode, plus the char offset where each page starts."""
        parts, starts, total = [], [], 0
        for p in self.doc:
            starts.append(total)
            paras = [" ".join(b[4].split()) for b in p.get_text("blocks") if b[6] == 0 and b[4].strip()]
            t = "\n".join(paras) + "\n" if paras else ""
            parts.append(t)
            total += len(t)
        return "".join(parts), starts


class DjvuDoc(PagedDoc):
    def __init__(self, path):
        if not (shutil.which("ddjvu") and shutil.which("djvused")):
            raise M.Broken("DjVu-Unterstützung (djvulibre) ist nicht installiert")
        self.path = path
        r = subprocess.run(["djvused", "-e", "n", path], capture_output=True, text=True, timeout=TIMEOUT)
        if r.returncode or not r.stdout.strip().isdigit():
            raise M.Broken("DjVu nicht lesbar")
        self.page_count = int(r.stdout.strip())
        self.title = M.from_filename(path).title

    def raw_page(self, i, longest):
        r = subprocess.run(["ddjvu", "-format=pgm", f"-page={i + 1}", f"-size={longest}x{longest}", self.path],
                           capture_output=True, timeout=TIMEOUT)
        if r.returncode:
            raise M.Broken("DjVu-Seite nicht darstellbar")
        return Image.open(io.BytesIO(r.stdout)).convert("L")


class ComicDoc(PagedDoc):
    """cbz, and cbr (RAR/7z via bsdtar; many .cbr files are actually zip)."""
    def __init__(self, path):
        self.path, self.title = path, M.from_filename(path).title
        self.zip = zipfile.is_zipfile(path)
        if self.zip:
            with zipfile.ZipFile(path) as z:
                self.pages = M.cbz_pages(z)
        else:
            if not shutil.which("bsdtar"):
                raise M.Broken("CBR-Unterstützung (bsdtar) ist nicht installiert")
            r = subprocess.run(["bsdtar", "-tf", path], capture_output=True, text=True, timeout=TIMEOUT)
            if r.returncode:
                raise M.Broken("Archiv nicht lesbar")
            self.pages = sorted(n for n in r.stdout.splitlines() if n.lower().endswith(M.IMG_EXT))
        if not self.pages:
            raise M.Broken("Archiv enthält keine Bilder")
        self.page_count = len(self.pages)

    def raw_bytes(self, i):
        name = self.pages[i]
        if self.zip:
            with zipfile.ZipFile(self.path) as z:
                info = z.getinfo(name)
                if info.file_size > M.MAX_ENTRY:
                    raise M.Broken("Bild zu groß")
                return z.read(info)
        r = subprocess.run(["bsdtar", "-xOf", self.path, "--", name], capture_output=True, timeout=TIMEOUT)
        if r.returncode or len(r.stdout) > M.MAX_ENTRY:
            raise M.Broken("Bild nicht lesbar")
        return r.stdout

    def raw_page(self, i, longest):
        im = Image.open(io.BytesIO(self.raw_bytes(i)))
        im.draft("L", (longest, longest))
        return ImageOps.exif_transpose(im).convert("L")
