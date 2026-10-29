"""Boots the Buildroot-built ARMv7 image (kernel + cross-compiled Python userland) in qemu-system-arm.
Needs tools/build-arm.command first; skipped otherwise. Not a Kindle: vexpress-a9 is an emulated reference board."""
import os
import shutil
import subprocess
import tempfile
import threading
import unittest

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
IMG = os.environ.get("ROSSINI_ARM_IMAGES", os.path.join(ROOT, "build", "arm", "images"))


@unittest.skipUnless(shutil.which("qemu-system-arm") and os.path.exists(os.path.join(IMG, "zImage")), "ARM image not built")
class ArmBoot(unittest.TestCase):
    def test_boot_selftest_and_pure_python_signature_check(self):
        with tempfile.TemporaryDirectory() as d:
            root = os.path.join(d, "root.img")
            shutil.copy(os.path.join(IMG, "rootfs.ext4"), root)
            subprocess.run(["qemu-img", "resize", "-f", "raw", root, "512M"], check=True, capture_output=True)
            p = subprocess.Popen(
                ["qemu-system-arm", "-M", "vexpress-a9", "-m", "512", "-nographic", "-no-reboot", "-nic", "none",
                 "-kernel", os.path.join(IMG, "zImage"), "-dtb", os.path.join(IMG, "vexpress-v2p-ca9.dtb"),
                 "-drive", f"file={root},if=sd,format=raw", "-append", "root=/dev/mmcblk0 rw console=ttyAMA0 panic=-1"],
                stdout=subprocess.PIPE, stderr=subprocess.STDOUT, stdin=subprocess.DEVNULL)
            lines, timer = [], threading.Timer(2400, p.kill)
            timer.start()
            try:
                for raw in p.stdout:  # stop as soon as the test script reports completion
                    lines.append(raw.decode(errors="replace"))
                    if "ROSSINI-ARM: done" in lines[-1]:
                        break
            finally:
                timer.cancel()
                p.kill()
                p.wait()
            out = "".join(lines)
        self.assertIn("armv7l", out)
        for chk in ("data-fs", "library+reader", "shell+display", "transfer", "power"):
            self.assertIn(f"selftest PASS {chk}", out, out[-2500:])
        self.assertIn("ROSSINI-ARM: selftest PASS", out)
        self.assertIn("signed package verified", out)
        self.assertIn("tampered package rejected", out)


if __name__ == "__main__":
    unittest.main()
