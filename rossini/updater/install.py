"""Install a verified package into the inactive slot and arm the trial boot.
Power-fail safety: the boot state is only changed after the slot image is fully written, flushed
and read back identical. Before that point the confirmed slot stays bootable and untouched."""
import hashlib
import os
import stat
import tempfile

from . import package
from .bootctl import BootCtl


def write_slot(dev, src, size, chunk=1 << 20, _fault=None):
    """Copy src into the slot device and read it back; returns the sha256 of what the device holds.
    _fault(bytes_written) lets tests cut the power mid-write."""
    if stat.S_ISBLK(os.stat(dev).st_mode) if os.path.exists(dev) else False:
        with open(dev, "rb") as d:
            if size > d.seek(0, os.SEEK_END):
                raise package.PackageError("Slot ist zu klein für das Image")
    done = 0
    with open(src, "rb") as s, open(dev, "r+b" if os.path.exists(dev) else "wb") as d:
        while buf := s.read(chunk):
            d.write(buf)
            done += len(buf)
            if _fault:
                _fault(done)
        d.flush()
        os.fsync(d.fileno())
    h = hashlib.sha256()
    with open(dev, "rb") as d:
        left = size
        while left and (b := d.read(min(chunk, left))):
            h.update(b)
            left -= len(b)
    return h.hexdigest()


def install(pkg_path, trusted_keys, board, slots, bootctl_path, _fault=None):
    """slots: {'A': dev, 'B': dev}. Returns the manifest. Raises PackageError on any failed check."""
    ctl = BootCtl(bootctl_path)
    with tempfile.TemporaryDirectory(prefix="rossini-update-") as stage:
        man, staged = package.verify(pkg_path, trusted_keys, board, int(ctl.v["rollback_index"]), stage)
        if "rootfs" not in staged:
            raise package.PackageError("Paket enthält kein rootfs")
        target = ctl.inactive()
        expected = next(p["sha256"] for p in man["payloads"] if p["name"] == "rootfs")
        size = os.path.getsize(staged["rootfs"])
        got = write_slot(slots[target], staged["rootfs"], size, _fault=_fault)
        if got != expected:
            raise package.PackageError("Rückleseprüfung des Slots fehlgeschlagen")
        ctl.begin_trial(target, man["version"], man["rollback_index"])
    return man
