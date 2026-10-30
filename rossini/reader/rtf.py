"""RTF to plain paragraphs: groups, control words, hex/unicode escapes; skips destinations (fonts, colours,
pictures, metadata). Formatting is dropped."""
import re

SKIP = {"fonttbl", "colortbl", "stylesheet", "info", "pict", "header", "footer", "headerl", "headerr", "footerl",
        "footerr", "object", "listtable", "listoverridetable", "rsidtbl", "generator", "themedata", "datastore", "latentstyles"}
TOKEN = re.compile(rb"\\([a-z]{1,32})(-?\d{1,10})? ?|\\'([0-9a-fA-F]{2})|\\([^a-z])|([{}])|[\r\n]+|([^\\{}\r\n]+)")


def rtf_to_text(data, max_len=32 << 20):
    if not data.lstrip().startswith(b"{\\rtf"):
        raise ValueError("not an RTF file")
    out, stack, skip, uc, skip_chars = [], [], False, 1, 0
    codepage = "cp1252"
    for m in TOKEN.finditer(data):
        word, arg, hexc, sym, brace, text = m.groups()
        if brace == b"{":
            stack.append((skip, uc))
        elif brace == b"}":
            if stack:
                skip, uc = stack.pop()
        elif skip:
            continue
        elif word:
            w = word.decode()
            if w in SKIP:
                skip = True
            elif w in ("par", "line", "sect", "page"):
                out.append("\n")
            elif w == "tab":
                out.append("\t")
            elif w == "uc" and arg:
                uc = int(arg)
            elif w == "ansicpg" and arg:
                codepage = f"cp{int(arg)}"
            elif w == "u" and arg:
                out.append(chr(int(arg) % 65536))
                skip_chars = uc
        elif sym:
            if sym == b"*":
                skip = True
            elif sym in (b"\\", b"{", b"}"):
                out.append(sym.decode())
            elif sym == b"~":
                out.append("\u00a0")
        elif hexc:
            if skip_chars:
                skip_chars -= 1
            else:
                try:
                    out.append(bytes([int(hexc, 16)]).decode(codepage))
                except (LookupError, UnicodeDecodeError):
                    out.append("?")
        elif text:
            t = text.decode(codepage, "replace")
            if skip_chars:
                cut = min(skip_chars, len(t))
                t, skip_chars = t[cut:], skip_chars - cut
            out.append(t)
        if len(out) > max_len:
            raise ValueError("RTF too large")
    return "".join(out)
