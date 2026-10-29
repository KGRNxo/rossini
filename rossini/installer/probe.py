"""Read-only inspection of a connected reader (mounted as USB mass storage) and user-data backup."""
import hashlib
import json
import os
import platform
import re
import shutil
import subprocess
import time


def read_facts(mount):
    """Collect what is actually observable from the mount. Nothing is inferred: model identification is
    not attempted here, the gate only matches rules against these raw values."""
    facts = {"mount": mount, "host": platform.platform()}
    v = os.path.join(mount, "system", "version.txt")
    if os.path.isfile(v):
        with open(v, errors="replace") as f:
            facts["version_txt"] = f.read(4096).strip()
    facts["has_documents_dir"] = os.path.isdir(os.path.join(mount, "documents"))
    try:
        st = os.statvfs(mount)
        facts["free_bytes"], facts["total_bytes"] = st.f_bavail * st.f_frsize, st.f_blocks * st.f_frsize
    except OSError:
        pass
    facts["usb"] = usb_info()
    return facts


def usb_info():
    """Raw USB description from the host; serial numbers are truncated to 4 characters."""
    cmd = ["system_profiler", "SPUSBDataType"] if platform.system() == "Darwin" else ["lsusb"]
    try:
        out = subprocess.run(cmd, capture_output=True, text=True, timeout=20).stdout
    except (OSError, subprocess.TimeoutExpired):
        return None
    out = re.sub(r"(Serial Number:\s*)(\w{4})\w*", r"\1\2…", out)
    return [l.strip() for l in out.splitlines() if re.search(r"amazon|kindle|1949", l, re.I)] or []


def backup(mount, dest):
    """Copy user data (documents dir) to dest and verify every file by hash. Returns the manifest path."""
    src = os.path.join(mount, "documents")
    if not os.path.isdir(src):
        raise FileNotFoundError("documents directory not found on device")
    os.makedirs(dest, exist_ok=True)
    target = os.path.join(dest, "documents")
    if os.path.exists(target):
        raise FileExistsError(f"{target} exists; refusing to overwrite a backup")
    shutil.copytree(src, target, symlinks=False)
    man = {}
    for d, _, fs in os.walk(src):
        for f in fs:
            a = os.path.join(d, f)
            rel = os.path.relpath(a, src)
            h = lambda p: hashlib.sha256(open(p, "rb").read()).hexdigest()
            man[rel] = h(a)
            if h(os.path.join(target, rel)) != man[rel]:
                raise IOError(f"backup verification failed for {rel}")
    path = os.path.join(dest, "backup-manifest.json")
    with open(path, "w") as f:
        json.dump({"created": time.strftime("%Y-%m-%dT%H:%M:%S"), "files": man}, f, indent=1)
    return path
