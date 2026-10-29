"""Optional sync of reading position and annotations through a shared folder (USB stick, Syncthing,
a mounted network share) or a self-hosted WebDAV server. No Rossini account, no vendor cloud. Records carry timestamps; merge is
last-writer-wins per record, commutative and idempotent, so devices converge in any order and an
interrupted transfer (atomic file replace) cannot lose data. Deletions are tombstones."""
import json
import os

from ..common import atomic_write

FILE = "rossini-sync.json"


def snapshot(lib):
    out = {"progress": {}, "annotations": {}}
    for b in lib.db.execute("SELECT id,key FROM books"):
        p = lib.get_progress(b["id"])
        if p:
            out["progress"][b["key"]] = {"position": p["position"], "percent": p["percent"], "updated": p["updated"], "kind": p.get("kind")}
        for a in lib.db.execute("SELECT * FROM annotations WHERE book_id=?", (b["id"],)):
            out["annotations"][a["uid"]] = {"key": b["key"], "kind": a["kind"], "start": a["start"], "end": a["end"],
                                            "text": a["text"], "note": a["note"], "created": a["created"],
                                            "updated": a["updated"], "deleted": a["deleted"]}
    return out


def merge(a, b):
    """Pure merge of two snapshots."""
    out = {"progress": dict(a["progress"]), "annotations": dict(a["annotations"])}
    for k, v in b["progress"].items():
        if k not in out["progress"] or v["updated"] > out["progress"][k]["updated"]:
            out["progress"][k] = v
    for k, v in b["annotations"].items():
        if k not in out["annotations"] or v["updated"] > out["annotations"][k]["updated"]:
            out["annotations"][k] = v
    return out


def apply(lib, snap):
    """Write merged state into the library (only for books present locally)."""
    ids = {r["key"]: r["id"] for r in lib.db.execute("SELECT id,key FROM books")}
    for key, p in snap["progress"].items():
        cur = lib.get_progress(ids[key]) if key in ids else None
        if key in ids and (cur is None or p["updated"] > cur["updated"]):
            lib.set_progress(ids[key], p["position"], p["percent"], p["updated"], p.get("kind"))
    for uid, a in snap["annotations"].items():
        if a["key"] not in ids:
            continue
        row = lib.db.execute("SELECT updated FROM annotations WHERE uid=?", (uid,)).fetchone()
        if row is None:
            lib.db.execute("INSERT INTO annotations VALUES(?,?,?,?,?,?,?,?,?,?)",
                           (uid, ids[a["key"]], a["kind"], a["start"], a["end"], a["text"], a["note"], a["created"], a["updated"], a["deleted"]))
        elif a["updated"] > row["updated"]:
            lib.db.execute("UPDATE annotations SET start=?,end=?,text=?,note=?,updated=?,deleted=? WHERE uid=?",
                           (a["start"], a["end"], a["text"], a["note"], a["updated"], a["deleted"], uid))
    lib.db.commit()


class Conflict(Exception):
    """The remote copy changed between read and write."""


def sync_with(lib, load, store, attempts=3):
    """load() -> (snapshot or None, version); store(bytes, version) raises Conflict when the remote changed.
    On a conflict the remote is re-read and merged again, so concurrent devices never overwrite each other."""
    for _ in range(attempts):
        remote, version = load()
        merged = merge(snapshot(lib), remote or {"progress": {}, "annotations": {}})
        apply(lib, merged)
        try:
            store(json.dumps(merged, sort_keys=True).encode(), version)
            return merged
        except Conflict:
            continue
    raise Conflict("Sync abgebrochen: die entfernte Datei ändert sich laufend")


def sync_dir(lib, directory):
    """Merge local state with the shared file in a folder (USB stick, Syncthing, network mount)."""
    path = os.path.join(directory, FILE)

    def load():
        if not os.path.exists(path):
            return None, None
        with open(path) as f:
            return json.load(f), None  # a corrupt remote file raises: refuse to overwrite it blindly

    return sync_with(lib, load, lambda data, _: atomic_write(path, data))


def sync_webdav(lib, url, user=None, password=None, opener=None):
    """WebDAV (Nextcloud, ownCloud, Apache mod_dav, ...): GET with ETag, PUT with If-Match / If-None-Match."""
    import base64
    import urllib.error
    import urllib.request
    from .opds import check_url
    target = check_url(url.rstrip("/") + "/" + FILE)
    headers = {"User-Agent": "RossiniOS/0.4"}
    if user:
        headers["Authorization"] = "Basic " + base64.b64encode(f"{user}:{password or ''}".encode()).decode()
    open_ = opener or (lambda req: urllib.request.urlopen(req, timeout=30))

    def load():
        try:
            with open_(urllib.request.Request(target, headers=headers)) as r:
                return json.loads(r.read(16 << 20)), r.headers.get("ETag")
        except urllib.error.HTTPError as e:
            if e.code == 404:
                return None, None
            raise

    def store(data, etag):
        h = dict(headers, **({"If-Match": etag} if etag else {"If-None-Match": "*"}))
        try:
            with open_(urllib.request.Request(target, data=data, headers=h, method="PUT")):
                pass
        except urllib.error.HTTPError as e:
            if e.code == 412:
                raise Conflict() from e
            raise

    return sync_with(lib, load, store)
