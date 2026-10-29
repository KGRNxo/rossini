"""QEMU harness for the x86_64 development target: builds disk images (A/B slots, boot-state, data),
boots the real kernel + initramfs + squashfs root, captures the serial console, and reads files back out of
the ext4 images with debugfs. This validates the userland boot chain; it says nothing about Kindle hardware."""
import os
import shutil
import subprocess
import tempfile

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
OUT = os.environ.get("ROSSINI_OUT", os.path.join(ROOT, "build", "out"))
SLOT_MB, BOOT_MB, DATA_MB = 96, 8, 160


def available():
    return shutil.which("qemu-system-x86_64") and os.path.exists(os.path.join(OUT, "vmlinuz")) and shutil.which("mke2fs") and shutil.which("debugfs")


def _ext4(path, mb, src_dir):
    with open(path, "wb") as f:
        f.truncate(mb << 20)
    env = dict(os.environ, E2FSPROGS_FAKE_TIME="1700000000")
    subprocess.run(["mke2fs", "-q", "-t", "ext4", "-d", src_dir, "-U", "11111111-2222-3333-4444-555555555555", "-E", "hash_seed=11111111-2222-3333-4444-555555555555", path],
                   check=True, env=env, capture_output=True)


class Vm:
    def __init__(self, workdir, base_version="0.3.0", bootctl=None, data_files=None):
        self.w = workdir
        self.a, self.b = os.path.join(workdir, "slotA.img"), os.path.join(workdir, "slotB.img")
        self.boot, self.data = os.path.join(workdir, "boot.img"), os.path.join(workdir, "data.img")
        for img, sz in ((self.a, SLOT_MB), (self.b, SLOT_MB)):
            with open(img, "wb") as f:
                f.truncate(sz << 20)
        with open(os.path.join(OUT, f"rootfs-{base_version}.squashfs"), "rb") as s, open(self.a, "r+b") as d:
            shutil.copyfileobj(s, d)
        bd = os.path.join(workdir, "bootdir"); os.makedirs(bd)
        with open(os.path.join(bd, "bootctl"), "w") as f:
            f.write(bootctl or f"confirmed=A\ntrial=\ntries=0\nrollback_index=1\ntrial_rollback=0\nversion_A={base_version}\nversion_B=\n")
        _ext4(self.boot, BOOT_MB, bd)
        dd = os.path.join(workdir, "datadir"); os.makedirs(dd)
        for rel, src in (data_files or {}).items():
            os.makedirs(os.path.dirname(os.path.join(dd, rel)), exist_ok=True)
            shutil.copy(src, os.path.join(dd, rel))
        _ext4(self.data, DATA_MB, dd)
        self.log = []

    def run(self, mode="boot", initrd="initramfs.cpio.gz", extra="", timeout=420):
        cmd = ["qemu-system-x86_64", "-m", "1024", "-smp", "2", "-cpu", "max", "-display", "none", "-serial", "stdio", "-monitor", "none",
               "-no-reboot", "-nic", "none", "-kernel", os.path.join(OUT, "vmlinuz"), "-initrd", os.path.join(OUT, initrd),
               "-append", f"console=ttyS0 panic=-1 loglevel=3 rossini.test={mode} {extra}"]
        if os.path.exists("/dev/kvm") and os.access("/dev/kvm", os.R_OK | os.W_OK):
            cmd += ["-enable-kvm"]
        for img in (self.a, self.b, self.boot, self.data):
            cmd += ["-drive", f"file={img},if=virtio,format=raw"]
        try:
            p = subprocess.run(cmd, capture_output=True, timeout=timeout, stdin=subprocess.DEVNULL)
            text, rc = p.stdout.decode(errors="replace"), p.returncode
        except subprocess.TimeoutExpired as e:
            text, rc = (e.stdout or b"").decode(errors="replace") + "\nTIMEOUT", -1
        self.log.append(text)
        return text

    def read(self, image, path):
        r = subprocess.run(["debugfs", "-R", f"cat {path}", image], capture_output=True)
        return r.stdout

    def bootctl(self):
        return dict(l.split("=", 1) for l in self.read(self.boot, "/bootctl").decode().split() if "=" in l)

    def dump(self, image, path, dest):
        subprocess.run(["debugfs", "-R", f"rdump {path} {dest}", image], capture_output=True, check=True)

    def write_boot_file(self, name, data):
        tmp = os.path.join(self.w, "tmpfile"); open(tmp, "wb").write(data)
        subprocess.run(["debugfs", "-w", "-R", f"rm /{name}", self.boot], capture_output=True)
        subprocess.run(["debugfs", "-w", "-R", f"write {tmp} /{name}", self.boot], capture_output=True, check=True)
