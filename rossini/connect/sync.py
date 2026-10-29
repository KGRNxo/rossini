"""Optional sync of reading position and annotations through a shared folder (USB stick, Syncthing,
a mounted network share). No account, no cloud. Records carry timestamps; merge is
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
            out["progress"][b["key"]] = {"position": p["position"], "percent": p["percent"], "updated": p["updated"]}
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
            lib.set_progress(ids[key], p["position"], p["percent"], p["updated"])
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


def sync_dir(lib, directory):
    """Merge local state with the shared file, write the result back, return the merged snapshot."""
    path = os.path.join(directory, FILE)
    remote = {"progress": {}, "annotations": {}}
    if os.path.exists(path):
        with open(path) as f:
            remote = json.load(f)  # a corrupt remote file raises: refuse to overwrite it blindly
    merged = merge(snapshot(lib), remote)
    apply(lib, merged)
    atomic_write(path, json.dumps(merged, sort_keys=True).encode())
    return merged
