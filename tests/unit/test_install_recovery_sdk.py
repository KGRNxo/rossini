import json
import os
import subprocess
import tempfile
import unittest

from rossini.installer import cli, gate, probe
from rossini.recovery import tools as R
from rossini.sdk import manifest as SDK
from rossini.updater.bootctl import BootCtl

ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..")


class GateTest(unittest.TestCase):
    def test_every_shipped_kindle_profile_is_refused(self):
        profiles = gate.load_profiles()
        self.assertIn("kindle-kt6", profiles)
        for name, p in profiles.items():
            if p["kind"] == "hardware":
                self.assertEqual(p["release_status"], "research", name)
                self.assertEqual(p["identification"]["rules"], [], name)
        for facts in ({}, {"version_txt": "Kindle 5.16.2.1.1"}, {"version_txt": "anything", "has_documents_dir": True}):
            d = gate.evaluate(facts, profiles, True, "kindle-kt6", True)
            self.assertFalse(d.allowed)

    def test_even_a_matching_rule_needs_every_proof(self):
        prof = {"x": {"kind": "hardware", "release_status": "released", "install_method": "flash-v1",
                      "identification": {"rules": [{"fact": "version_txt", "regex": "Kindle 5\\..*"}]},
                      "evidence": {e: True for e in gate.EVIDENCE}}}
        facts = {"version_txt": "Kindle 5.16"}
        self.assertTrue(gate.evaluate(facts, prof, True, "x", True).allowed)
        for mut in (lambda p: p["x"].update(release_status="research"),
                    lambda p: p["x"]["evidence"].update(recovery_independent=False),
                    lambda p: p["x"].update(install_method=None)):
            import copy
            q = copy.deepcopy(prof); mut(q)
            self.assertFalse(gate.evaluate(facts, q, True, "x", True).allowed)
        self.assertFalse(gate.evaluate(facts, prof, False, None, True).allowed)
        self.assertFalse(gate.evaluate(facts, prof, True, "other", True).allowed)
        self.assertFalse(gate.evaluate(facts, prof, True, "x", False).allowed)
        self.assertFalse(gate.evaluate({"version_txt": "Kindle 4.1"}, prof, True, "x", True).allowed)

    def test_cli_refuses_unknown_device_and_writes_report(self):
        with tempfile.TemporaryDirectory() as d:
            os.makedirs(f"{d}/dev/system"); os.makedirs(f"{d}/dev/documents")
            open(f"{d}/dev/system/version.txt", "w").write("Kindle 5.16.2.1.1\n")
            open(f"{d}/dev/documents/a.epub", "w").write("x")
            rc = cli.main(["--mount", f"{d}/dev", "--report-dir", d, "--backup-dir", f"{d}/bk"])
            self.assertEqual(rc, 3)
            rep = [f for f in os.listdir(d) if f.startswith("rossini-diagnose")]
            self.assertEqual(len(rep), 1)
            data = json.load(open(f"{d}/{rep[0]}"))
            self.assertEqual(data["decision"], "refused")
            self.assertEqual(data["facts"]["version_txt"], "Kindle 5.16.2.1.1")
            self.assertFalse(os.path.exists(f"{d}/bk"))  # no side effects for refused devices

    def test_backup_verifies_and_never_overwrites(self):
        with tempfile.TemporaryDirectory() as d:
            os.makedirs(f"{d}/dev/documents/sub")
            open(f"{d}/dev/documents/sub/a.txt", "w").write("hello")
            m = probe.backup(f"{d}/dev", f"{d}/bk")
            self.assertIn("sub/a.txt", json.load(open(m))["files"])
            with self.assertRaises(FileExistsError):
                probe.backup(f"{d}/dev", f"{d}/bk")


class RecoveryTest(unittest.TestCase):
    def test_verify_detects_changed_and_missing_files(self):
        with tempfile.TemporaryDirectory() as d:
            os.makedirs(f"{d}/etc")
            open(f"{d}/etc/a", "w").write("one"); open(f"{d}/etc/b", "w").write("two")
            subprocess.run("sha256sum etc/a etc/b > ../m.sha256", shell=True, cwd=d, check=True)
            man = os.path.join(os.path.dirname(d), "m.sha256")
            self.addCleanup(os.unlink, man)
            self.assertEqual(R.verify_system(d, man), [])
            open(f"{d}/etc/a", "w").write("changed"); os.unlink(f"{d}/etc/b")
            self.assertEqual(sorted(R.verify_system(d, man)), ["fehlt: etc/b", "verändert: etc/a"])

    def test_restore_previous_and_refusal(self):
        with tempfile.TemporaryDirectory() as d:
            p = f"{d}/bootctl"
            open(p, "w").write("confirmed=B\ntrial=\ntries=0\nversion_A=0.3.0\nversion_B=0.4.0\n")
            self.assertEqual(R.restore_previous(p), "A")
            self.assertEqual(BootCtl(p).confirmed, "A")
            open(p, "w").write("confirmed=A\ntrial=B\ntries=2\nversion_A=0.3.0\n")
            with self.assertRaises(ValueError):
                R.restore_previous(p)

    def test_export_and_reset_needs_token(self):
        with tempfile.TemporaryDirectory() as d:
            os.makedirs(f"{d}/data/books"); open(f"{d}/data/books/x.epub", "w").write("b"); open(f"{d}/data/library.db", "w").write("db")
            out = R.export_data(f"{d}/data", f"{d}/usb")
            self.assertTrue(os.path.exists(f"{out}/books/x.epub"))
            with self.assertRaises(PermissionError):
                R.factory_reset(f"{d}/data", "yes")
            self.assertTrue(os.path.exists(f"{d}/data/library.db"))
            self.assertEqual(R.factory_reset(f"{d}/data", R.RESET_TOKEN), 2)
            self.assertEqual(os.listdir(f"{d}/data"), [])


class SdkTest(unittest.TestCase):
    def test_manifest_validation(self):
        ok = {"id": "org.example.notes", "name": "Notizen", "version": "1.0.0", "entry": "main.py", "permissions": ["library.read"]}
        self.assertEqual(SDK.validate(json.dumps(ok))["name"], "Notizen")
        for bad in ({**ok, "id": "x"}, {**ok, "entry": "../../bin/sh"}, {**ok, "entry": "/bin/sh"},
                    {**ok, "permissions": ["root"]}, {**ok, "version": "1"}, {**ok, "api_level": 9}, [], "{"):
            with self.assertRaises(SDK.ManifestError):
                SDK.validate(bad if not isinstance(bad, dict) else json.dumps(bad))


class HwdiagTest(unittest.TestCase):
    def test_script_runs_and_is_read_only(self):
        with tempfile.TemporaryDirectory() as d:
            out = subprocess.run(["sh", os.path.join(ROOT, "tools", "hwdiag.sh"), f"{d}/o.txt"], capture_output=True, text=True, check=True).stdout.strip()
            text = open(out).read()
            for sect in ("=== cpu ===", "=== partitions ===", "=== power_supply ===", "=== input ==="):
                self.assertIn(sect, text)


if __name__ == "__main__":
    unittest.main()
