import os
import shutil
import subprocess
import tempfile
import unittest

from rossini.installer import fit

HAVE = bool(shutil.which("mkimage") and shutil.which("dumpimage"))
REAL = os.path.join(os.path.dirname(__file__), "..", "..", "build", "kernel", "kt6")


class FitTest(unittest.TestCase):
    def test_its_has_config_named_like_booteink_expects(self):
        t = fit.its("/k", "/d", "mt8110-cava")
        self.assertIn('default = "conf-mt8110-cava"', t)
        self.assertIn("conf-mt8110-cava {", t)
        self.assertNotIn("anti-rollback", t)
        self.assertIn("anti-rollback-version = <3>;", fit.its("/k", "/d", "mt8110-cava", anti_rollback=3))
        self.assertIn('ramdisk = "ramdisk";', fit.its("/k", "/d", "x", ramdisk="/r"))
        for bad in ("", "../x", "a b", "x;y"):
            with self.assertRaises(ValueError):
                fit.its("/k", "/d", bad)

    @unittest.skipUnless(HAVE, "u-boot-tools missing")
    def test_mkimage_accepts_and_lists_the_configuration(self):
        with tempfile.TemporaryDirectory() as d:
            for n, size in (("k", 4096), ("d", 512)):
                open(f"{d}/{n}", "wb").write(os.urandom(size))
            out = f"{d}/fit.img"
            size = fit.build(out, f"{d}/k", f"{d}/d", "mt8110-cava", anti_rollback=2)
            self.assertEqual(size, os.path.getsize(out))
            info = subprocess.run(["mkimage", "-l", out], capture_output=True, text=True).stdout
            self.assertIn("conf-mt8110-cava", info)
            # the kernel payload round-trips
            subprocess.run(["dumpimage", "-T", "flat_dt", "-p", "0", "-o", f"{d}/k.out", out], capture_output=True, check=True)
            self.assertEqual(open(f"{d}/k.out", "rb").read(), open(f"{d}/k", "rb").read())

    @unittest.skipUnless(HAVE and os.path.exists(os.path.join(REAL, "out/arch/arm/boot/zImage")), "built KT6 kernel missing")
    def test_real_kt6_kernel_fits_into_booteink_limit(self):
        with tempfile.TemporaryDirectory() as d:
            size = fit.build(f"{d}/fit.img", os.path.join(REAL, "out/arch/arm/boot/zImage"),
                             os.path.join(REAL, "out/arch/arm/boot/dts/mediatek/mt8110-cava.dtb"), "mt8110-cava")
            self.assertLess(size, fit.MAX_BYTES)

    @unittest.skipUnless(HAVE, "u-boot-tools missing")
    def test_size_limit_of_booteink(self):
        with tempfile.TemporaryDirectory() as d:
            with open(f"{d}/k", "wb") as f:
                f.truncate(fit.MAX_BYTES + 4096)
            open(f"{d}/d", "wb").write(b"d" * 64)
            with self.assertRaisesRegex(ValueError, "refuses"):
                fit.build(f"{d}/o", f"{d}/k", f"{d}/d", "x")
            self.assertFalse(os.path.exists(f"{d}/o"))


if __name__ == "__main__":
    unittest.main()
