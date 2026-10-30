import os
import shutil
import subprocess
import tempfile
import unittest

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
SRC = os.environ.get("ROSSINI_LAB126_SRC", "/home/user/katadelos/linux-3.0.35-lab126")
PIN = "7ac2585f384573da8cbdcc987a3503e2e6ff1fb4"


@unittest.skipUnless(os.path.isdir(os.path.join(SRC, ".git")), "Lab126 kernel checkout not available")
class KernelPatchTest(unittest.TestCase):
    def test_patches_apply_cleanly_to_the_pinned_commit(self):
        head = subprocess.run(["git", "-C", SRC, "rev-parse", "HEAD"], capture_output=True, text=True).stdout.strip()
        self.assertEqual(head, PIN)
        patches = sorted(os.listdir(os.path.join(ROOT, "kernel/patches/lab126-3.0.35")))
        self.assertTrue(patches)
        with tempfile.TemporaryDirectory() as d:
            subprocess.run(f"git -C {SRC} archive HEAD arch/arm/mm/proc-v7.S arch/arm/boot/compressed include/linux | tar -x -C {d}", shell=True, check=True)
            subprocess.run(["git", "init", "-q", d], check=True)
            for p in patches:
                r = subprocess.run(["git", "-C", d, "apply", "--check", os.path.join(ROOT, "kernel/patches/lab126-3.0.35", p)], capture_output=True, text=True)
                self.assertEqual(r.returncode, 0, r.stderr)


KT6 = os.environ.get("ROSSINI_KT6_SRC", os.path.join(ROOT, "build", "kernel", "kt6", "src"))


@unittest.skipUnless(os.path.isdir(os.path.join(KT6, ".git")), "KT6 kernel checkout not available (tools/build-kernel.command kt6)")
class Kt6PatchTest(unittest.TestCase):
    def test_patches_apply_to_pristine_commit(self):
        pdir = os.path.join(ROOT, "kernel/patches/amazon-rossini-4.9")
        with tempfile.TemporaryDirectory() as d:
            subprocess.run(f"git -C {KT6} archive HEAD arch/arm/Makefile arch/arm/mm/proc-v7.S arch/arm/boot/compressed | tar -x -C {d}", shell=True, check=True)
            subprocess.run(["git", "init", "-q", d], check=True)
            for p in sorted(os.listdir(pdir)):
                r = subprocess.run(["git", "-C", d, "apply", "--check", os.path.join(pdir, p)], capture_output=True, text=True)
                self.assertEqual(r.returncode, 0, r.stderr)


if __name__ == "__main__":
    unittest.main()
