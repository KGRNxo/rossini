"""Offline dictionaries in StarDict format (.ifo + .idx + .dict/.dict.dz). Bilingual StarDict
dictionaries double as the translation feature. Dictionaries live in <data>/dictionaries/."""
import bisect
import glob
import gzip
import os
import re
import struct

MAX_DICT = 256 << 20


class StarDict:
    def __init__(self, ifo_path):
        base = ifo_path[:-4]
        info = {}
        with open(ifo_path, encoding="utf-8", errors="replace") as f:
            if not f.readline().startswith("StarDict's dict ifo file"):
                raise ValueError("not a StarDict .ifo")
            for line in f:
                k, _, v = line.strip().partition("=")
                info[k] = v
        self.name = info.get("bookname", os.path.basename(base))
        self.types = info.get("sametypesequence", "")
        if info.get("idxoffsetbits", "32") != "32":
            raise ValueError("64-bit StarDict index not supported")
        with open(base + ".idx", "rb") as f:
            idx = f.read()
        self.keys, self.entries = [], []
        i = 0
        while i < len(idx):
            j = idx.index(b"\0", i)
            word = idx[i:j].decode("utf-8", "replace")
            off, size = struct.unpack(">II", idx[j + 1:j + 9])
            self.entries.append((word, off, size))
            i = j + 9
        self.entries.sort(key=lambda e: e[0].casefold())
        self.keys = [e[0].casefold() for e in self.entries]
        self.dict_path = base + ".dict" if os.path.exists(base + ".dict") else base + ".dict.dz"
        self._data = None

    def _blob(self):
        if self._data is None:
            # shortcut: .dict.dz is decompressed completely into memory (capped); upgrade to dictzip random access for very large dictionaries
            opener = gzip.open if self.dict_path.endswith(".dz") else open
            with opener(self.dict_path, "rb") as f:
                self._data = f.read(MAX_DICT)
        return self._data

    def _definition(self, off, size):
        raw = self._blob()[off:off + size]
        if self.types in ("m", "t", "y", "g", "x", "h", ""):
            text = raw.decode("utf-8", "replace")
            if self.types in ("x", "h", "g"):
                text = re.sub(r"<[^>]+>", " ", text)
            return " ".join(text.split())
        return raw.decode("utf-8", "replace")

    def lookup(self, word, limit=3):
        k = word.casefold()
        i = bisect.bisect_left(self.keys, k)
        out = []
        while i < len(self.keys) and self.keys[i] == k and len(out) < limit:
            w, off, size = self.entries[i]
            out.append((w, self._definition(off, size)))
            i += 1
        return out


WORD = re.compile(r"[\W_]+$|^[\W_]+")


def candidates(word):
    """The word as found, without punctuation, and a few German/English inflection fallbacks."""
    w = WORD.sub("", word)
    out = [w]
    for suf in ("es", "en", "er", "em", "e", "s", "n"):
        if len(w) > len(suf) + 3 and w.lower().endswith(suf):
            out.append(w[:-len(suf)])
    return list(dict.fromkeys(out))


class Dictionaries:
    def __init__(self, directory):
        self.dicts, self.errors = [], []
        for ifo in sorted(glob.glob(os.path.join(directory, "**", "*.ifo"), recursive=True)):
            try:
                self.dicts.append(StarDict(ifo))
            except (OSError, ValueError, struct.error) as e:
                self.errors.append((ifo, str(e)))

    def lookup(self, word):
        """[(dictionary name, headword, definition)] for the first inflection candidate that matches."""
        for cand in candidates(word):
            hits = [(d.name, w, text) for d in self.dicts for w, text in d.lookup(cand)]
            if hits:
                return hits
        return []
