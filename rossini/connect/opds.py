"""OPDS 1.x client (Calibre content server, Standard Ebooks, ...). Network input is untrusted:
http(s) only, size and time limits, XML entities rejected, filenames sanitised, atomic downloads."""
import hashlib
import os
import re
import urllib.parse
import urllib.request
from dataclasses import dataclass, field

from ..common import local, safe_xml

MAX_FEED = 5 * 1024 * 1024
MAX_BOOK = 200 * 1024 * 1024
TIMEOUT = 20
ACQ = "http://opds-spec.org/acquisition"
MIME_EXT = {"application/epub+zip": ".epub", "application/x-fictionbook+xml": ".fb2", "application/x-cbz": ".cbz",
            "application/vnd.comicbook+zip": ".cbz", "text/plain": ".txt"}


@dataclass
class Entry:
    title: str
    author: str = ""
    nav: str = None          # URL of a sub-catalog
    downloads: list = field(default_factory=list)  # (url, mime)


@dataclass
class Feed:
    title: str
    entries: list
    next: str = None


class FetchError(Exception):
    pass


def check_url(url):
    p = urllib.parse.urlparse(url)
    if p.scheme not in ("http", "https") or not p.netloc:
        raise FetchError("only http(s) URLs are allowed")
    return url


def _get(url, limit, opener=urllib.request.urlopen):
    check_url(url)
    req = urllib.request.Request(url, headers={"User-Agent": "RossiniOS/0.4"})
    with opener(req, timeout=TIMEOUT) as r:
        data = r.read(limit + 1)
    if len(data) > limit:
        raise FetchError("response too large")
    return data


def parse(xml, base):
    root = safe_xml(xml)
    title = next((e.text for e in root if local(e.tag) == "title"), "Katalog") or "Katalog"
    entries, nxt = [], None
    for l in root:
        if local(l.tag) == "link" and l.get("rel") == "next":
            nxt = urllib.parse.urljoin(base, l.get("href"))
    for e in root:
        if local(e.tag) != "entry":
            continue
        t = next((x.text for x in e if local(x.tag) == "title" and x.text), "Ohne Titel")
        author = next((n.text for a in e if local(a.tag) == "author" for n in a if local(n.tag) == "name" and n.text), "")
        ent = Entry(title=t.strip(), author=author.strip())
        for l in e:
            if local(l.tag) != "link" or not l.get("href"):
                continue
            href, rel, typ = urllib.parse.urljoin(base, l.get("href")), l.get("rel") or "", l.get("type") or ""
            if rel.startswith(ACQ):
                ent.downloads.append((href, typ.split(";")[0]))
            elif "opds-catalog" in typ and rel in ("", "subsection", "http://opds-spec.org/sort/new", "alternate") and not ent.nav:
                ent.nav = href
        if ent.nav or ent.downloads:
            entries.append(ent)
    return Feed(title.strip(), entries, nxt)


def fetch_feed(url, opener=urllib.request.urlopen):
    return parse(_get(url, MAX_FEED, opener), url)


def safe_name(s, fallback="book"):
    s = re.sub(r"[^\w .,()\-]+", "_", s, flags=re.UNICODE).strip(" .")[:100]
    return s or fallback


def download(entry, dest_dir, opener=urllib.request.urlopen):
    """Download the best DRM-free format; returns the final path. Never overwrites existing files."""
    pref = [d for d in entry.downloads if d[1] in MIME_EXT]
    if not pref:
        raise FetchError("kein unterstütztes Format (EPUB, FB2, CBZ oder TXT) verfügbar")
    pref.sort(key=lambda d: list(MIME_EXT).index(d[1]))
    url, mime = pref[0]
    check_url(url)
    os.makedirs(dest_dir, exist_ok=True)
    base = safe_name(f"{entry.author} - {entry.title}" if entry.author else entry.title)
    final = os.path.join(dest_dir, base + MIME_EXT[mime])
    n = 1
    while os.path.exists(final):
        n += 1
        final = os.path.join(dest_dir, f"{base} ({n}){MIME_EXT[mime]}")
    tmp = final + ".part"
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "RossiniOS/0.4"})
        size = 0
        with opener(req, timeout=TIMEOUT) as r, open(tmp, "wb") as f:
            while chunk := r.read(1 << 16):
                size += len(chunk)
                if size > MAX_BOOK:
                    raise FetchError("file too large")
                f.write(chunk)
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp, final)
    finally:
        if os.path.exists(tmp):
            os.unlink(tmp)
    return final
