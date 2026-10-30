"""Rossini Library: SQLite catalogue. Book files are never modified; metadata, progress
and notes live only in the database. Deleting a file requires an explicit flag."""
import hashlib
import os
import re
import sqlite3
import time
import uuid
from dataclasses import dataclass, field

from . import meta as M

SCHEMA = """
CREATE TABLE IF NOT EXISTS books(
  id INTEGER PRIMARY KEY, key TEXT UNIQUE NOT NULL, title TEXT NOT NULL, author TEXT NOT NULL DEFAULT '',
  series TEXT, series_index REAL, language TEXT, added REAL NOT NULL,
  status TEXT NOT NULL DEFAULT 'unread' CHECK(status IN ('unread','reading','finished')),
  favorite INTEGER NOT NULL DEFAULT 0, archived INTEGER NOT NULL DEFAULT 0,
  locked INTEGER NOT NULL DEFAULT 0, cover BLOB);
CREATE TABLE IF NOT EXISTS files(
  id INTEGER PRIMARY KEY, book_id INTEGER REFERENCES books(id) ON DELETE CASCADE,
  path TEXT UNIQUE NOT NULL, format TEXT NOT NULL, size INTEGER, sha256 TEXT, mtime REAL, broken TEXT);
CREATE TABLE IF NOT EXISTS collections(id INTEGER PRIMARY KEY, name TEXT UNIQUE NOT NULL);
CREATE TABLE IF NOT EXISTS collection_books(
  collection_id INTEGER REFERENCES collections(id) ON DELETE CASCADE,
  book_id INTEGER REFERENCES books(id) ON DELETE CASCADE, PRIMARY KEY(collection_id, book_id));
CREATE TABLE IF NOT EXISTS tags(book_id INTEGER REFERENCES books(id) ON DELETE CASCADE, tag TEXT NOT NULL,
  PRIMARY KEY(book_id, tag));
CREATE TABLE IF NOT EXISTS progress(book_id INTEGER PRIMARY KEY REFERENCES books(id) ON DELETE CASCADE,
  position INTEGER NOT NULL, percent REAL NOT NULL, updated REAL NOT NULL);
CREATE TABLE IF NOT EXISTS annotations(uid TEXT PRIMARY KEY, book_id INTEGER REFERENCES books(id) ON DELETE CASCADE,
  kind TEXT NOT NULL CHECK(kind IN ('bookmark','highlight','note')), start INTEGER NOT NULL, end INTEGER,
  text TEXT, note TEXT, created REAL NOT NULL, updated REAL NOT NULL, deleted INTEGER NOT NULL DEFAULT 0);
CREATE TABLE IF NOT EXISTS reading_log(day TEXT, book_id INTEGER, seconds INTEGER, pages INTEGER,
  PRIMARY KEY(day, book_id));
"""
SORTS = {"title": "lower(title)", "author": "lower(author), lower(title)", "added": "added DESC",
         "series": "lower(coalesce(series,'')), series_index, lower(title)",
         "recent": "coalesce((SELECT updated FROM progress p WHERE p.book_id=books.id),0) DESC"}


def book_key(author, title):
    n = lambda s: re.sub(r"[\W_]+", "", s.casefold())
    return f"{n(author)}|{n(title)}"


def sha256_file(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


@dataclass
class ScanReport:
    added: int = 0
    updated: int = 0
    unchanged: int = 0
    broken: list = field(default_factory=list)
    ignored: int = 0  # files with extensions the reader cannot open


class Library:
    def __init__(self, path):
        if path != ":memory:":
            os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
        self.db = sqlite3.connect(path)
        self.db.row_factory = sqlite3.Row
        self.db.execute("PRAGMA foreign_keys=ON")
        if path != ":memory:":
            self.db.execute("PRAGMA journal_mode=WAL")
            self.db.execute("PRAGMA synchronous=NORMAL")
        self.db.executescript(SCHEMA)
        self._migrate()

    def _migrate(self):
        """Add columns introduced after a database was created."""
        cols = {r[1] for r in self.db.execute("PRAGMA table_info(progress)")}
        if "kind" not in cols:  # 'text' = char offset, 'page' = page index
            self.db.execute("ALTER TABLE progress ADD COLUMN kind TEXT")
            self.db.commit()

    def close(self):
        self.db.commit()
        self.db.close()

    # --- import -------------------------------------------------------------
    def scan(self, *paths):
        rep = ScanReport()
        for root in paths:
            files = [root] if os.path.isfile(root) else (
                os.path.join(d, f) for d, _, fs in os.walk(root) for f in sorted(fs))
            for p in files:
                if os.path.splitext(p)[1].lower() not in M.FORMATS:
                    rep.ignored += 1
                    continue
                self._import_file(os.path.abspath(p), rep)
        self.db.commit()
        return rep

    def _import_file(self, path, rep):
        st = os.stat(path)
        row = self.db.execute("SELECT * FROM files WHERE path=?", (path,)).fetchone()
        if row and row["size"] == st.st_size and row["mtime"] == st.st_mtime and not row["broken"]:
            rep.unchanged += 1
            return
        digest = sha256_file(path)
        try:
            fmt, m = M.extract(path)
        except M.Broken as e:
            self._store_broken(path, st, digest, str(e), row)
            rep.broken.append((path, str(e)))
            return
        except Exception as e:  # corrupt files must never abort a scan
            self._store_broken(path, st, digest, f"error: {type(e).__name__}", row)
            rep.broken.append((path, f"error: {type(e).__name__}"))
            return
        book_id = self._book_for(m, row)
        if row:
            self.db.execute("UPDATE files SET book_id=?,size=?,sha256=?,mtime=?,broken=NULL WHERE id=?",
                            (book_id, st.st_size, digest, st.st_mtime, row["id"]))
            rep.updated += 1
        else:
            self.db.execute("INSERT INTO files(book_id,path,format,size,sha256,mtime) VALUES(?,?,?,?,?,?)",
                            (book_id, path, fmt, st.st_size, digest, st.st_mtime))
            rep.added += 1

    def _store_broken(self, path, st, digest, reason, row):
        if row:
            self.db.execute("UPDATE files SET size=?,sha256=?,mtime=?,broken=? WHERE id=?",
                            (st.st_size, digest, st.st_mtime, reason, row["id"]))
        else:
            self.db.execute("INSERT INTO files(book_id,path,format,size,sha256,mtime,broken) VALUES(NULL,?,?,?,?,?,?)",
                            (path, M.FORMATS[os.path.splitext(path)[1].lower()], st.st_size, digest,
                             st.st_mtime, reason))

    def _book_for(self, m, row):
        """Find or create the book; all formats of one work share one book row."""
        key = book_key(m.author, m.title)
        b = self.db.execute("SELECT id, locked FROM books WHERE key=?", (key,)).fetchone()
        if not b and row and row["book_id"]:  # file changed; keep the book if the user edited it
            b = self.db.execute("SELECT id, locked FROM books WHERE id=? AND locked=1", (row["book_id"],)).fetchone()
        if b:
            if not b["locked"]:
                self.db.execute("UPDATE books SET series=coalesce(?,series), series_index=coalesce(?,series_index),"
                                " language=coalesce(?,language), cover=coalesce(cover,?) WHERE id=?",
                                (m.series, m.series_index, m.language, m.cover, b["id"]))
            return b["id"]
        cur = self.db.execute("INSERT INTO books(key,title,author,series,series_index,language,added,cover)"
                              " VALUES(?,?,?,?,?,?,?,?)",
                              (key, m.title, m.author, m.series, m.series_index, m.language, time.time(), m.cover))
        return cur.lastrowid

    def rescan(self, book_id):
        """Re-read metadata from the book's files; discards manual edits."""
        for r in self.db.execute("SELECT path FROM files WHERE book_id=? AND broken IS NULL", (book_id,)).fetchall():
            try:
                _, m = M.extract(r["path"])
            except (M.Broken, OSError):
                continue
            self.db.execute("UPDATE books SET title=?,author=?,key=?,series=?,series_index=?,language=?,"
                            "cover=coalesce(?,cover),locked=0 WHERE id=?",
                            (m.title, m.author, book_key(m.author, m.title), m.series, m.series_index,
                             m.language, m.cover, book_id))
            self.db.commit()
            return True
        return False

    def prune_missing(self):
        """Forget files that no longer exist (explicit; scans never do this)."""
        gone = [r["id"] for r in self.db.execute("SELECT id,path FROM files") if not os.path.exists(r["path"])]
        self.db.executemany("DELETE FROM files WHERE id=?", [(i,) for i in gone])
        self.db.execute("DELETE FROM books WHERE id NOT IN (SELECT book_id FROM files WHERE book_id IS NOT NULL)")
        self.db.commit()
        return len(gone)

    # --- queries ------------------------------------------------------------
    def books(self, sort="title", query=None, status=None, fmt=None, collection=None, tag=None,
              favorites=False, archived=False, limit=None, offset=0):
        sql, args = ["SELECT id,title,author,series,series_index,status,favorite,archived,"
                     "(SELECT group_concat(format) FROM files f WHERE f.book_id=books.id) AS formats,"
                     "(SELECT percent FROM progress p WHERE p.book_id=books.id) AS percent FROM books WHERE archived=?"], [int(archived)]
        if query:
            q = "%" + re.sub(r"([\\%_])", r"\\\1", query.casefold()) + "%"
            sql.append("AND (lower(title) LIKE ? ESCAPE '\\' OR lower(author) LIKE ? ESCAPE '\\' OR lower(coalesce(series,'')) LIKE ? ESCAPE '\\'"
                       " OR id IN (SELECT book_id FROM tags WHERE lower(tag) LIKE ? ESCAPE '\\'))")
            args += [q] * 4
        if status:
            sql.append("AND status=?"); args.append(status)
        if fmt:
            sql.append("AND id IN (SELECT book_id FROM files WHERE format=?)"); args.append(fmt)
        if collection:
            sql.append("AND id IN (SELECT book_id FROM collection_books cb JOIN collections c ON c.id=cb.collection_id WHERE c.name=?)")
            args.append(collection)
        if tag:
            sql.append("AND id IN (SELECT book_id FROM tags WHERE tag=?)"); args.append(tag)
        if favorites:
            sql.append("AND favorite=1")
        sql.append("ORDER BY " + SORTS[sort])
        if limit is not None:
            sql.append("LIMIT ? OFFSET ?"); args += [limit, offset]
        return [dict(r) for r in self.db.execute(" ".join(sql), args)]

    def count(self, **kw):
        return len(self.books(**kw))

    def book(self, book_id):
        r = self.db.execute("SELECT id,title,author,series,series_index,language,status,favorite,archived,"
                            "cover FROM books WHERE id=?", (book_id,)).fetchone()
        if not r:
            return None
        d = dict(r)
        d["files"] = [dict(f) for f in self.db.execute(
            "SELECT path,format,size,sha256,broken FROM files WHERE book_id=? ORDER BY format", (book_id,))]
        d["tags"] = [t[0] for t in self.db.execute("SELECT tag FROM tags WHERE book_id=? ORDER BY tag", (book_id,))]
        return d

    def duplicates(self):
        """Groups of different paths with identical content."""
        rows = self.db.execute("SELECT sha256, group_concat(path, char(10)) p FROM files GROUP BY sha256"
                               " HAVING count(*)>1").fetchall()
        return [r["p"].split("\n") for r in rows]

    def broken(self):
        return [(r["path"], r["broken"]) for r in self.db.execute("SELECT path,broken FROM files WHERE broken IS NOT NULL")]

    # --- edits (metadata only; files untouched) -----------------------------
    def edit(self, book_id, **fields):
        allowed = {"title", "author", "series", "series_index", "language"}
        bad = set(fields) - allowed
        if bad:
            raise ValueError(f"cannot edit {sorted(bad)}")
        if not fields:
            return
        cur = self.book(book_id)
        key = book_key(fields.get("author", cur["author"]), fields.get("title", cur["title"]))
        sets = ",".join(f"{k}=?" for k in fields)
        self.db.execute(f"UPDATE books SET {sets}, key=?, locked=1 WHERE id=?", (*fields.values(), key, book_id))
        self.db.commit()

    def set_status(self, book_id, status):
        self.db.execute("UPDATE books SET status=? WHERE id=?", (status, book_id)); self.db.commit()

    def set_favorite(self, book_id, on=True):
        self.db.execute("UPDATE books SET favorite=? WHERE id=?", (int(on), book_id)); self.db.commit()

    def set_archived(self, book_id, on=True):
        self.db.execute("UPDATE books SET archived=? WHERE id=?", (int(on), book_id)); self.db.commit()

    def add_tag(self, book_id, tag):
        self.db.execute("INSERT OR IGNORE INTO tags VALUES(?,?)", (book_id, tag.strip())); self.db.commit()

    def remove_tag(self, book_id, tag):
        self.db.execute("DELETE FROM tags WHERE book_id=? AND tag=?", (book_id, tag)); self.db.commit()

    def collection_add(self, name, book_id):
        self.db.execute("INSERT OR IGNORE INTO collections(name) VALUES(?)", (name,))
        cid = self.db.execute("SELECT id FROM collections WHERE name=?", (name,)).fetchone()[0]
        self.db.execute("INSERT OR IGNORE INTO collection_books VALUES(?,?)", (cid, book_id)); self.db.commit()

    def collection_remove(self, name, book_id):
        self.db.execute("DELETE FROM collection_books WHERE book_id=? AND collection_id="
                        "(SELECT id FROM collections WHERE name=?)", (book_id, name)); self.db.commit()

    def collections(self):
        return [dict(r) for r in self.db.execute(
            "SELECT c.name, count(cb.book_id) AS n FROM collections c LEFT JOIN collection_books cb"
            " ON cb.collection_id=c.id GROUP BY c.id ORDER BY lower(c.name)")]

    def remove(self, book_id, delete_files=False):
        """Remove a book from the library. Files stay on disk unless delete_files=True."""
        paths = [r["path"] for r in self.db.execute("SELECT path FROM files WHERE book_id=?", (book_id,))]
        self.db.execute("DELETE FROM books WHERE id=?", (book_id,))
        self.db.commit()
        if delete_files:
            for p in paths:
                try:
                    os.unlink(p)
                except FileNotFoundError:
                    pass
        return paths

    # --- progress and annotations ------------------------------------------
    def get_progress(self, book_id):
        r = self.db.execute("SELECT position,percent,updated,kind FROM progress WHERE book_id=?", (book_id,)).fetchone()
        return dict(r) if r else None

    def set_progress(self, book_id, position, percent, when=None, kind=None):
        when = time.time() if when is None else when
        self.db.execute("INSERT INTO progress(book_id,position,percent,updated,kind) VALUES(?,?,?,?,?) ON CONFLICT(book_id) DO UPDATE SET "
                        "position=excluded.position, percent=excluded.percent, updated=excluded.updated, kind=excluded.kind",
                        (book_id, position, percent, when, kind))
        status = "finished" if percent >= 0.99 else "reading"
        self.db.execute("UPDATE books SET status=? WHERE id=?", (status, book_id))
        self.db.commit()

    def add_annotation(self, book_id, kind, start, end=None, text=None, note=None):
        uid, now = uuid.uuid4().hex, time.time()
        self.db.execute("INSERT INTO annotations VALUES(?,?,?,?,?,?,?,?,?,0)",
                        (uid, book_id, kind, start, end, text, note, now, now)); self.db.commit()
        return uid

    def annotations(self, book_id, kind=None):
        q, a = "SELECT * FROM annotations WHERE book_id=? AND deleted=0", [book_id]
        if kind:
            q += " AND kind=?"; a.append(kind)
        return [dict(r) for r in self.db.execute(q + " ORDER BY start", a)]

    def delete_annotation(self, uid):
        self.db.execute("UPDATE annotations SET deleted=1, updated=? WHERE uid=?", (time.time(), uid)); self.db.commit()

    # --- opt-in reading statistics -----------------------------------------
    def log_reading(self, book_id, seconds, pages, day=None):
        day = day or time.strftime("%Y-%m-%d")
        self.db.execute("INSERT INTO reading_log VALUES(?,?,?,?) ON CONFLICT(day,book_id) DO UPDATE SET "
                        "seconds=seconds+excluded.seconds, pages=pages+excluded.pages", (day, book_id, seconds, pages))
        self.db.commit()

    def book_collections(self, book_id):
        return [r[0] for r in self.db.execute("SELECT c.name FROM collections c JOIN collection_books cb ON cb.collection_id=c.id"
                                              " WHERE cb.book_id=? ORDER BY lower(c.name)", (book_id,))]

    def stats_by_month(self, months=6):
        return [dict(r) for r in self.db.execute(
            "SELECT substr(day,1,7) AS month, sum(seconds) AS seconds, sum(pages) AS pages, count(DISTINCT book_id) AS books"
            " FROM reading_log GROUP BY month ORDER BY month DESC LIMIT ?", (months,))]

    def stats(self):
        r = self.db.execute("SELECT coalesce(sum(seconds),0) s, coalesce(sum(pages),0) p FROM reading_log").fetchone()
        return {"seconds": r["s"], "pages": r["p"],
                "finished": self.db.execute("SELECT count(*) FROM books WHERE status='finished'").fetchone()[0]}
