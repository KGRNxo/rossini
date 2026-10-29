"""End-to-end boot-chain tests in QEMU (x86_64 development target, NOT Kindle hardware).
Requires: python3 tools/build_images.py. Skipped when QEMU or images are missing."""
import os
import shutil
import tempfile
import unittest

from tests.qemu.harness import OUT, Vm, available


@unittest.skipUnless(available(), "QEMU or built images missing (run tools/build_images.py)")
class QemuBoot(unittest.TestCase):
    def vm(self, **kw):
        d = tempfile.mkdtemp(prefix="rossini-vm-")
        self.addCleanup(shutil.rmtree, d, True)
        return Vm(d, **kw)

    def test_cold_boot_selftest_and_screens(self):
        vm = self.vm()
        out = vm.run("boot")
        self.assertIn("ROSSINI-INITRAMFS: chooser picked slot A", out)
        self.assertIn("ROSSINI: boot slot=A version=0.3.0", out)
        self.assertIn("ROSSINI: selftest PASS", out, out[-2500:])
        for chk in ("data-fs", "library+reader", "shell+display", "transfer", "power", "connectd"):
            self.assertIn(f"selftest PASS {chk}", out)
        self.assertIn("Power down", out)
        dst = tempfile.mkdtemp(); self.addCleanup(shutil.rmtree, dst, True)
        vm.dump(vm.data, "/screens", dst)
        from PIL import Image
        im = Image.open(os.path.join(dst, "screens", "home.png"))
        self.assertGreater(len(set(im.getdata())), 3)
        self.assertEqual(vm.bootctl()["confirmed"], "A")

    def test_signed_update_trial_confirm(self):
        vm = self.vm(data_files={"update/rossini.pkg": os.path.join(OUT, "update-0.4.0-dev.pkg")})
        out1 = vm.run("update")
        self.assertIn("update install rc=0", out1, out1[-2500:])
        self.assertEqual((vm.bootctl()["trial"], vm.bootctl()["tries"]), ("B", "3"))
        out2 = vm.run("update")
        self.assertIn("chooser picked slot B", out2)
        self.assertIn("ROSSINI: boot slot=B version=0.4.0-dev", out2)
        self.assertIn("confirmed slot B", out2, out2[-2500:])
        c = vm.bootctl()
        self.assertEqual((c["confirmed"], c["trial"], c["rollback_index"]), ("B", "", "2"))

    def test_failing_update_rolls_back_to_previous_slot(self):
        vm = self.vm(data_files={"update/rossini.pkg": os.path.join(OUT, "update-0.4.0-dev-bad.pkg")})
        vm.run("update")
        self.assertEqual(vm.bootctl()["trial"], "B")
        picked = []
        for _ in range(4):
            out = vm.run("update")
            picked.append("B" if "chooser picked slot B" in out else "A")
            if picked[-1] == "A":
                break
        self.assertEqual(picked, ["B", "B", "B", "A"], picked)
        self.assertIn("NOT confirmed", vm.log[1])
        self.assertIn("selftest PASS", vm.log[-1])
        self.assertIn("boot slot=A version=0.3.0", vm.log[-1])
        c = vm.bootctl()
        self.assertEqual((c["confirmed"], c["trial"]), ("A", ""))

    def test_unmountable_trial_slot_falls_back_immediately(self):
        vm = self.vm(bootctl="confirmed=A\ntrial=B\ntries=3\nrollback_index=1\nversion_A=0.3.0\nversion_B=junk\n")
        out = vm.run("boot")  # slot B is empty/garbage
        self.assertIn("slot B does not mount", out)
        self.assertIn("boot slot=A version=0.3.0", out)
        self.assertEqual(vm.bootctl()["trial"], "")

    def test_recovery_image_is_independent_and_finds_problems(self):
        vm = self.vm()
        out = vm.run("boot", initrd="recovery.cpio.gz", extra="rossini.recovery=auto")
        self.assertIn("ROSSINI-RECOVERY: started", out)
        self.assertIn("slot a integrity OK", out, out[-2000:])
        self.assertIn("slot b not mountable", out)
        self.assertIn("data fs clean", out)
        self.assertIn("data export ok", out)
        self.assertNotIn("ROSSINI: boot slot", out)  # regular system was never started
        # corrupt slot A in the middle of the image: recovery must notice
        with open(vm.a, "r+b") as f:
            f.seek(8 << 20); f.write(b"\xff" * 4096)
        out = vm.run("boot", initrd="recovery.cpio.gz", extra="rossini.recovery=auto")
        self.assertTrue("slot a integrity FAILED" in out or "slot a not mountable" in out, out[-1500:])


if __name__ == "__main__":
    unittest.main()
