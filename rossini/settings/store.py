"""Typed, validated, persistent settings. Every key has an owner that reacts via subscribe():
display.* -> Display/HAL, power.* -> PowerManager, reader.* -> ReaderSession, connect.* -> Connect.
There is deliberately no telemetry key: the system contains no telemetry code."""
import json
import os

from ..common import atomic_write

# key: (default, validator, group)
def _int(lo, hi):
    return lambda v: isinstance(v, int) and not isinstance(v, bool) and lo <= v <= hi

def _float(lo, hi):
    return lambda v: isinstance(v, (int, float)) and not isinstance(v, bool) and lo <= v <= hi

def _bool(v):
    return isinstance(v, bool)

def _enum(*opts):
    return lambda v: v in opts

def _url(v):
    return v == "" or (isinstance(v, str) and v.startswith(("http://", "https://")) and len(v) < 500)

SCHEMA = {
    "display.frontlight":       (0,     _int(0, 100),                     "Anzeige"),
    "display.rotation":         (0,     _enum(0, 90, 180, 270),           "Anzeige"),
    "display.full_refresh_every": (10,  _int(1, 100),                     "Anzeige"),
    "display.ui_scale":         (1.0,   _float(0.8, 1.6),                 "Anzeige"),
    "reader.font":              ("serif", _enum("serif", "sans"),         "Lesen"),
    "reader.font_size":         (36,    _int(18, 90),                     "Lesen"),
    "reader.line_spacing":      (1.35,  _float(1.0, 2.2),                 "Lesen"),
    "reader.margin":            (60,    _int(10, 200),                    "Lesen"),
    "reader.justify":           (True,  _bool,                            "Lesen"),
    "reader.indent":            (True,  _bool,                            "Lesen"),
    "reader.stats":             (False, _bool,                            "Lesen"),
    "reader.hyphenation":       (True,  _bool,                            "Lesen"),
    "reader.invert":            (False, _bool,                            "Lesen"),
    "reader.prev_zone":         (30,    _int(10, 50),                     "Lesen"),
    "reader.pdf_crop":          (True,  _bool,                            "Lesen"),
    "reader.pdf_reflow":        (False, _bool,                            "Lesen"),
    "power.standby_s":          (600,   _int(30, 7200),                   "Energie"),
    "power.off_s":              (86400, _int(600, 30 * 86400),            "Energie"),
    "connect.opds_url":         ("",    _url,                             "Verbindungen"),
    "connect.sync_dir":         ("",    lambda v: isinstance(v, str),     "Verbindungen"),
    "connect.webdav_url":       ("",    _url,                             "Verbindungen"),
    "system.language":          ("de",  _enum("de", "en"),                "System"),
}


class Settings:
    def __init__(self, path=None):
        self.path, self.values, self.subs = path, {k: v[0] for k, v in SCHEMA.items()}, []
        if path and os.path.exists(path):
            try:
                with open(path) as f:
                    for k, v in json.load(f).items():
                        if k in SCHEMA and SCHEMA[k][1](v):
                            self.values[k] = v
            except (ValueError, OSError):
                pass  # corrupt file: fall back to defaults rather than refusing to boot

    def get(self, key):
        return self.values[key]

    def as_dict(self):
        return dict(self.values)

    def set(self, key, value):
        if key not in SCHEMA:
            raise KeyError(key)
        if not SCHEMA[key][1](value):
            raise ValueError(f"invalid value for {key}: {value!r}")
        if self.values[key] == value:
            return
        self.values[key] = value
        if self.path:
            atomic_write(self.path, json.dumps(self.values, indent=1, sort_keys=True).encode())
        for prefix, fn in self.subs:
            if key.startswith(prefix):
                fn(key, value)

    def subscribe(self, prefix, fn):
        self.subs.append((prefix, fn))

    def reset(self):
        for k, v in SCHEMA.items():
            self.set(k, v[0])
