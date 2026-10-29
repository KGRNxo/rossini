"""Runs the real init sequence (supervisor, indexer, connectd, self-test, slot confirmation) on the host."""
import os
import sys
import tempfile
import unittest

from rossini.system.init import Init
from rossini.system.supervisor import Service, Supervisor
from rossini.updater.bootctl import BootCtl

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))


class InitTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.d = self.tmp.name
        os.makedirs(f"{self.d}/boot"); os.makedirs(f"{self.d}/data")
        self.env = dict(os.environ, PYTHONPATH=ROOT)
        os.environ["PYTHONPATH"] = ROOT
        self.addCleanup(lambda: None)
        self.calls = []

    def init(self, slot="B"):
        return Init(data=f"{self.d}/data", boot=f"{self.d}/boot", slot=slot, version="9.9.9", powerctl=self.calls.append)

    def test_boot_confirms_trial_slot(self):
        open(f"{self.d}/boot/bootctl", "w").write("confirmed=A\ntrial=B\ntries=2\nrollback_index=1\ntrial_rollback=2\n")
        self.init("B").run()
        c = BootCtl(f"{self.d}/boot/bootctl")
        self.assertEqual((c.confirmed, c.trial, c.v["rollback_index"]), ("B", "", "2"))
        self.assertEqual(self.calls, ["poweroff"])
        self.assertTrue(os.path.exists(f"{self.d}/data/screens/home.png"))

    def test_failed_selftest_does_not_confirm_and_reboots(self):
        open(f"{self.d}/boot/bootctl", "w").write("confirmed=A\ntrial=B\ntries=2\n")
        marker = f"{self.d}/fail"; open(marker, "w").close()
        os.environ["ROSSINI_BAD_MARKER"] = marker
        self.addCleanup(os.environ.pop, "ROSSINI_BAD_MARKER", None)
        self.init("B").run()
        c = BootCtl(f"{self.d}/boot/bootctl")
        self.assertEqual((c.confirmed, c.trial), ("A", "B"))
        self.assertEqual(self.calls, ["reboot"])

    def test_supervisor_order_restart_and_crash_loop(self):
        py = sys.executable
        s = Supervisor([Service("b", [py, "-c", "pass"], oneshot=True, after=["a"]),
                        Service("a", [py, "-c", "pass"], oneshot=True),
                        Service("loop", [py, "-c", "import sys; sys.exit(3)"], after=["a"]),
                        Service("dep", [py, "-c", "pass"], oneshot=True, after=["loop"])], log=lambda m: None)
        self.assertEqual(s.order.index("a") < s.order.index("b"), True)
        s.run_until_settled(timeout=30)
        import time
        end = time.time() + 30
        while s.svc["loop"].status == "running" and time.time() < end:
            s.step(); time.sleep(0.05)
        self.assertEqual((s.svc["a"].status, s.svc["b"].status), ("done", "done"))
        self.assertEqual(s.svc["loop"].status, "failed")
        with self.assertRaises(ValueError):
            Supervisor([Service("x", [py], after=["nope"])])
        with self.assertRaises(ValueError):
            Supervisor([Service("x", [py], after=["y"]), Service("y", [py], after=["x"])])


if __name__ == "__main__":
    unittest.main()
