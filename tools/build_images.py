#!/usr/bin/env python3
"""Build the QEMU development images (Linux host only; on macOS tools/build-all.command runs this in a container).

Produces in <out>/:
  rootfs-<ver>.squashfs        root of one A/B slot (busybox + python + rossini)
  rootfs-<ver>-bad.squashfs    same, but its boot self-test is rigged to fail (rollback test fixture)
  initramfs.cpio.gz            stage 1: slot chooser (bootloader stand-in for QEMU)
  recovery.cpio.gz             separate recovery userland
  update-<ver>.pkg             signed update package (and -bad variant)
  vmlinuz                      kernel used for QEMU (distro kernel, NOT a Kindle kernel)
  SHA256SUMS, BUILDINFO.json
Reproducible: fixed mtimes (SOURCE_DATE_EPOCH), sorted archives, no timestamps in gzip/squashfs.
"""
import argparse
import hashlib
import json
import os
import shutil
import subprocess
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
from rossini import VERSION  # noqa: E402
from rossini.updater import package  # noqa: E402

PYVER = "python3.13"
STDLIB = f"/usr/lib/{PYVER}"
SITE = f"/usr/local/lib/{PYVER}/dist-packages"
STDLIB_SKIP = ("test", "tests", "idlelib", "tkinter", "turtledemo", "ensurepip", "lib2to3", "__pycache__",
               "pydoc_data", "turtle.py", "site-packages", "dist-packages", "config-3.13-x86_64-linux-gnu")


def run(*a, **k):
    return subprocess.run(a, check=True, **k)


def copy_file(src, dst):
    os.makedirs(os.path.dirname(dst), exist_ok=True)
    shutil.copy2(os.path.realpath(src), dst)


def copy_tree(src, dst, skip=()):
    for d, dirs, files in os.walk(src):
        dirs[:] = sorted(x for x in dirs if x not in skip)
        rel = os.path.relpath(d, src)
        for f in sorted(files):
            if f in skip or f.endswith((".pyc", ".pyo")):
                continue
            s = os.path.join(d, f)
            if os.path.islink(s) and not os.path.exists(s):
                continue
            copy_file(s, os.path.normpath(os.path.join(dst, rel, f)))


def is_elf(p):
    try:
        with open(p, "rb") as f:
            return f.read(4) == b"\x7fELF"
    except OSError:
        return False


def copy_libs(root):
    """Copy every shared library needed by any ELF in root (transitively), to the same absolute path."""
    done = set()
    todo = [os.path.join(d, f) for d, _, fs in os.walk(root) for f in fs if is_elf(os.path.join(d, f)) and not os.path.islink(os.path.join(d, f))]
    while todo:
        elf = todo.pop()
        if elf in done:
            continue
        done.add(elf)
        out = subprocess.run(["ldd", elf], capture_output=True, text=True).stdout
        for line in out.splitlines():
            parts = line.split()
            path = parts[2] if "=>" in parts and len(parts) > 2 else (parts[0] if parts and parts[0].startswith("/") else None)
            if not path or not os.path.exists(path):
                continue
            dst = os.path.join(root, os.path.realpath(os.path.dirname(path)).lstrip("/"), os.path.basename(path))
            if not os.path.exists(dst):
                copy_file(path, dst)
                todo.append(dst)


def normalize_times(root, epoch):
    for d, dirs, files in os.walk(root):
        for n in dirs + files:
            p = os.path.join(d, n)
            os.utime(p, (epoch, epoch), follow_symlinks=False)
    os.utime(root, (epoch, epoch))


def sha256(p):
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for c in iter(lambda: f.read(1 << 20), b""):
            h.update(c)
    return h.hexdigest()


def skeleton(root):
    for d in ("usr/bin", "usr/sbin", "usr/lib", "etc/rossini", "proc", "sys", "dev", "run", "tmp", "data", "boot", "opt", "mnt", "newroot", "var"):
        os.makedirs(os.path.join(root, d), exist_ok=True)
    for link, target in (("bin", "usr/bin"), ("sbin", "usr/sbin"), ("lib", "usr/lib"), ("lib64", "usr/lib64")):
        os.symlink(target, os.path.join(root, link))
    os.makedirs(os.path.join(root, "usr/lib64"), exist_ok=True)


def busybox_into(root):
    bb = shutil.which("busybox")
    copy_file(bb, os.path.join(root, "usr/bin/busybox"))
    names = subprocess.run([bb, "--list"], capture_output=True, text=True, check=True).stdout.split()
    for n in sorted(names):
        p = os.path.join(root, "usr/bin", n)
        if n != "busybox" and not os.path.lexists(p):
            os.symlink("busybox", p)


def python_into(root, full):
    copy_file(f"/usr/bin/{PYVER}", os.path.join(root, f"usr/bin/{PYVER}"))
    os.symlink(PYVER, os.path.join(root, "usr/bin/python3"))
    copy_tree(STDLIB, os.path.join(root, STDLIB.lstrip("/")), skip=STDLIB_SKIP)
    if full:
        # the device verifies updates with the pure-Python Ed25519 code: no crypto package is shipped
        for pkg in ("PIL", "pillow.libs", "pymupdf", "pyphen"):
            p = os.path.join(SITE, pkg)
            if os.path.isdir(p):
                copy_tree(p, os.path.join(root, SITE.lstrip("/"), pkg), skip=("__pycache__", "layout", "mupdf-devel"))
        for tool in ("ddjvu", "djvused", "bsdtar"):  # DjVu and CBR decoders, run as separate processes
            if shutil.which(tool):
                copy_file(shutil.which(tool), os.path.join(root, "usr/bin", tool))


def rossini_into(root, full):
    dst = os.path.join(root, "opt/rossini")
    copy_tree(os.path.join(ROOT, "rossini"), os.path.join(dst, "rossini"))
    copy_tree(os.path.join(ROOT, "boards"), os.path.join(dst, "boards"))
    copy_tree(os.path.join(ROOT, "system"), os.path.join(dst, "system"))
    if full:
        copy_tree(os.path.join(ROOT, "assets"), os.path.join(dst, "assets"))
        os.makedirs(os.path.join(dst, "tests"))
        for f in ("__init__.py", "fixtures.py"):
            copy_file(os.path.join(ROOT, "tests", f), os.path.join(dst, "tests", f))


def write(path, text, mode=0o644):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w") as f:
        f.write(text)
    os.chmod(path, mode)


def make_rootfs(out, tmp, version, pubkey_hex, bad, epoch):
    root = os.path.join(tmp, "rootfs-bad" if bad else "rootfs")
    shutil.rmtree(root, ignore_errors=True)
    os.makedirs(root)
    skeleton(root)
    busybox_into(root)
    python_into(root, full=True)
    rossini_into(root, full=True)
    copy_libs(root)
    write(os.path.join(root, "etc/rossini/version"), version + "\n")
    write(os.path.join(root, "etc/rossini/board"), "qemu-x86_64\n")
    write(os.path.join(root, "etc/rossini/update.pub"), pubkey_hex + "\n")
    if bad:
        write(os.path.join(root, "etc/rossini/selftest-fail"), "test fixture: forces the boot self-test to fail\n")
    write(os.path.join(root, "usr/sbin/init"),
          "#!/usr/bin/busybox sh\nexport PATH=/usr/bin:/usr/sbin PYTHONPATH=/opt/rossini PYTHONDONTWRITEBYTECODE=1 "
          "ROSSINI_FONT_DIR=/opt/rossini/assets/fonts HOME=/tmp\nexec python3 -m rossini.system.init\n", 0o755)
    # integrity manifest used by recovery (everything except itself)
    lines = []
    for d, dirs, files in os.walk(root):
        dirs.sort()
        for f in sorted(files):
            p = os.path.join(d, f)
            if os.path.islink(p):
                continue
            rel = os.path.relpath(p, root)
            if rel != "etc/rossini/manifest.sha256":
                lines.append(f"{sha256(p)}  {rel}")
    write(os.path.join(root, "etc/rossini/manifest.sha256"), "\n".join(lines) + "\n")
    normalize_times(root, epoch)
    img = os.path.join(out, f"rootfs-{version}{'-bad' if bad else ''}.squashfs")
    if os.path.exists(img):
        os.unlink(img)
    run("mksquashfs", root, img, "-comp", "zstd", "-Xcompression-level", "12", "-noappend", "-no-progress", "-all-root",
        "-mkfs-time", str(epoch), "-all-time", str(epoch), "-no-xattrs", "-quiet", "-processors", "1")
    return img, root


def make_cpio(out, name, root, epoch):
    normalize_times(root, epoch)
    cpio = os.path.join(out, name)
    listing = subprocess.run(["find", ".", "-mindepth", "1"], cwd=root, capture_output=True, text=True, check=True).stdout.split("\n")
    names = "\n".join(sorted(x for x in listing if x)) + "\n"
    raw = subprocess.run(["cpio", "-o", "-H", "newc", "--reproducible", "--quiet", "-R", "0:0"], cwd=root, input=names.encode(),
                         capture_output=True, check=True).stdout
    gz = subprocess.run(["gzip", "-n", "-9"], input=raw, capture_output=True, check=True).stdout
    with open(cpio, "wb") as f:
        f.write(gz)
    return cpio


def make_initramfs(out, tmp, epoch):
    root = os.path.join(tmp, "initramfs")
    shutil.rmtree(root, ignore_errors=True)
    os.makedirs(root)
    for d in ("bin", "sbin", "proc", "sys", "dev", "boot", "data", "newroot", "run", "tmp", "etc"):
        os.makedirs(os.path.join(root, d))
    copy_file(shutil.which("busybox"), os.path.join(root, "bin/busybox"))
    copy_file(os.path.join(ROOT, "system/init/initramfs-init.sh"), os.path.join(root, "init"))
    copy_file(os.path.join(ROOT, "system/init/bootctl-choose.sh"), os.path.join(root, "bin/bootctl-choose.sh"))
    os.chmod(os.path.join(root, "init"), 0o755)
    return make_cpio(out, "initramfs.cpio.gz", root, epoch)


def make_recovery(out, tmp, epoch):
    root = os.path.join(tmp, "recovery")
    shutil.rmtree(root, ignore_errors=True)
    os.makedirs(root)
    skeleton(root)
    busybox_into(root)
    python_into(root, full=False)
    rossini_into(root, full=False)
    e2fsck = shutil.which("e2fsck")
    copy_file(e2fsck, os.path.join(root, "usr/sbin/e2fsck"))
    copy_libs(root)
    shutil.copy2(os.path.join(ROOT, "system/init/recovery-init.sh"), os.path.join(root, "init"))
    os.chmod(os.path.join(root, "init"), 0o755)
    return make_cpio(out, "recovery.cpio.gz", root, epoch)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=os.path.join(ROOT, "build", "out"))
    ap.add_argument("--keys", default=None, help="dir with update.key/update.pub (created if missing)")
    a = ap.parse_args()
    out = os.path.abspath(a.out)
    os.makedirs(out, exist_ok=True)
    tmp = os.path.join(os.path.dirname(out), "work")
    os.makedirs(tmp, exist_ok=True)
    epoch = int(os.environ.get("SOURCE_DATE_EPOCH") or subprocess.run(["git", "log", "-1", "--format=%ct"], cwd=ROOT, capture_output=True, text=True).stdout.strip() or 1700000000)
    keys = a.keys or os.path.join(out, "keys")
    if not os.path.exists(os.path.join(keys, "update.key")):
        from rossini.updater.cli import main as cli
        cli(["keygen", keys])
    pub = open(os.path.join(keys, "update.pub")).read().strip()
    priv = bytes.fromhex(open(os.path.join(keys, "update.key")).read().strip())
    version = VERSION
    # baseline (installed into slot A initially), the good update, and the rigged update used for the rollback test
    for ver, rb, bad in (("0.3.0", 1, False), (version, 2, False), (version, 2, True)):
        img, _ = make_rootfs(out, tmp, ver, pub, bad, epoch)
        pkg = os.path.join(out, f"update-{ver}{'-bad' if bad else ''}.pkg")
        package.build(pkg, ver, rb, ["qemu-x86_64"], {"rootfs": img}, priv, created=epoch)
        print("built", os.path.basename(img), os.path.getsize(img) // 1024, "KiB")
    make_initramfs(out, tmp, epoch)
    make_recovery(out, tmp, epoch)
    kern = "/boot/vmlinuz"
    shutil.copy2(os.path.realpath(kern), os.path.join(out, "vmlinuz"))
    names = sorted(f for f in os.listdir(out) if os.path.isfile(os.path.join(out, f)))
    with open(os.path.join(out, "SHA256SUMS"), "w") as f:
        for n in names:
            if n != "SHA256SUMS":
                f.write(f"{sha256(os.path.join(out, n))}  {n}\n")
    with open(os.path.join(out, "BUILDINFO.json"), "w") as f:
        json.dump({"version": version, "target": "qemu-x86_64", "source_date_epoch": epoch,
                   "kernel": "distro kernel for QEMU only, not a Kindle kernel", "signed_with": pub[:16] + "…"}, f, indent=1)
    print("done:", out)


if __name__ == "__main__":
    main()
