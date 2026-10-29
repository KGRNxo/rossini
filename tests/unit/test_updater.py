import os
import random
import subprocess
import tempfile
import unittest

from rossini.updater import package
from rossini.updater.bootctl import BootCtl
from rossini.updater.install import install

HERE = os.path.dirname(os.path.abspath(__file__))
CHOOSE = os.path.join(HERE, "..", "..", "system", "init", "bootctl-choose.sh")


class UpdaterTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.d = self.tmp.name
        self.priv, self.pub = package.generate_keypair()
        self.slots = {"A": f"{self.d}/slotA", "B": f"{self.d}/slotB"}
        for s in self.slots.values():
            with open(s, "wb") as f:
                f.write(b"old" * 1000)
        self.ctl = f"{self.d}/bootctl"
        with open(self.ctl, "w") as f:
            f.write("confirmed=A\ntrial=\ntries=0\nrollback_index=2\n")

    def pkg(self, name="u.pkg", version="0.5.0", rb=3, boards=("qemu-x86_64",), key=None, payload=b"NEWROOT" * 5000):
        with open(f"{self.d}/rootfs", "wb") as f:
            f.write(payload)
        out = f"{self.d}/{name}"
        package.build(out, version, rb, list(boards), {"rootfs": f"{self.d}/rootfs"}, key or self.priv)
        return out

    def inst(self, pkg, **kw):
        return install(pkg, [self.pub], "qemu-x86_64", self.slots, self.ctl, **kw)

    def test_happy_path_trial_then_confirm(self):
        self.inst(self.pkg())
        self.assertEqual(open(self.slots["B"], "rb").read()[:7], b"NEWROOT")
        c = BootCtl(self.ctl)
        self.assertEqual((c.confirmed, c.trial, c.v["tries"]), ("A", "B", "3"))
        self.assertEqual(c.choose(), "B")
        self.assertTrue(BootCtl(self.ctl).confirm("B"))
        c = BootCtl(self.ctl)
        self.assertEqual((c.confirmed, c.trial, c.v["rollback_index"]), ("B", "", "3"))
        self.assertEqual(c.choose(), "B")
        self.assertEqual(c.status(), "aktiv B v0.5.0, bestätigt")

    def test_unconfirmed_trial_rolls_back_after_three_boots(self):
        self.inst(self.pkg())
        self.assertEqual([BootCtl(self.ctl).choose() for _ in range(5)], ["B", "B", "B", "A", "A"])
        c = BootCtl(self.ctl)
        self.assertEqual((c.confirmed, c.trial), ("A", ""))

    def test_rejections_leave_slots_and_state_untouched(self):
        before = (open(self.ctl).read(), open(self.slots["B"], "rb").read())
        other_priv, _ = package.generate_keypair()
        cases = {
            "signature": self.pkg("bad.pkg", key=other_priv),
            "board": self.pkg("b.pkg", boards=("other-board",)),
            "downgrade": self.pkg("d.pkg", rb=1),
        }
        for why, p in cases.items():
            with self.assertRaises(package.PackageError, msg=why):
                self.inst(p)
        self.assertEqual(before, (open(self.ctl).read(), open(self.slots["B"], "rb").read()))

    def test_tampering_is_detected(self):
        good = self.pkg()
        data = bytearray(open(good, "rb").read())
        data[data.index(b"NEWROOT") + 100] ^= 0xFF  # flip a payload byte
        bad = f"{self.d}/tampered.pkg"
        open(bad, "wb").write(data)
        with self.assertRaisesRegex(package.PackageError, "Prüfsumme"):
            self.inst(bad)
        open(f"{self.d}/trunc.pkg", "wb").write(bytes(data[:3000]))
        with self.assertRaises(package.PackageError):
            self.inst(f"{self.d}/trunc.pkg")
        self.assertEqual(BootCtl(self.ctl).trial, "")

    def test_power_loss_during_write_keeps_old_system_bootable(self):
        class PowerCut(Exception):
            pass
        def cut(n):
            if n >= 20000:
                raise PowerCut
        for fault in (cut, ):
            with self.assertRaises(PowerCut):
                self.inst(self.pkg(payload=b"X" * 100000), _fault=fault)
        c = BootCtl(self.ctl)
        self.assertEqual((c.choose(), c.trial), ("A", ""))  # still the confirmed slot, no trial armed
        self.inst(self.pkg(payload=b"Y" * 100000))  # retry succeeds
        self.assertEqual(BootCtl(self.ctl).trial, "B")

    def test_no_temp_files_left_after_state_writes(self):
        """bootctl is replaced atomically via temp file + rename."""
        self.inst(self.pkg())
        for name in os.listdir(self.d):
            self.assertFalse(name.startswith(".tmp-"), name)

    def test_shell_chooser_matches_python_reference(self):
        rnd = random.Random(7)
        for _ in range(30):
            confirmed, trial = rnd.choice("AB"), rnd.choice(["", "A", "B"])
            tries = rnd.randint(0, 3)
            state = f"confirmed={confirmed}\ntrial={trial}\ntries={tries}\nrollback_index=0\n"
            outs = []
            for impl in ("py", "sh"):
                p = f"{self.d}/s_{impl}"
                open(p, "w").write(state)
                if impl == "py":
                    slot = BootCtl(p).choose()
                else:
                    slot = subprocess.run(["sh", CHOOSE, p], capture_output=True, text=True, check=True).stdout.strip()
                outs.append((slot, {k: v for k, v in (l.split("=") for l in open(p).read().split() if "=" in l) if k in ("confirmed", "trial", "tries")}))
            self.assertEqual(outs[0], outs[1], state)


if __name__ == "__main__":
    unittest.main()
