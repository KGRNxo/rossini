"""Shared helpers: atomic file writes, hostile-input-safe XML parsing, time."""
import os
import tempfile
import xml.etree.ElementTree as ET


def atomic_write(path, data):
    """Write bytes so that a crash leaves either the old or the new file, never a mix."""
    d = os.path.dirname(path) or "."
    os.makedirs(d, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=d, prefix=".tmp-")
    try:
        with os.fdopen(fd, "wb") as f:
            f.write(data)
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp, path)
        dfd = os.open(d, os.O_RDONLY)
        try:
            os.fsync(dfd)
        finally:
            os.close(dfd)
    except BaseException:
        try:
            os.unlink(tmp)
        except OSError:
            pass
        raise


def safe_xml(data):
    """Parse XML from untrusted files. Entity declarations are rejected outright
    (entity-expansion attacks); DOCTYPE without entities is tolerated."""
    if isinstance(data, str):
        data = data.encode("utf-8")
    if b"<!entity" in data.lower():
        raise ValueError("XML entity declarations are not allowed")
    return ET.fromstring(data)


def local(tag):
    """'{ns}name' -> 'name'"""
    return tag.rsplit("}", 1)[-1]
