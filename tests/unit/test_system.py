import json
import os
import tempfile
import unittest

from rossini.settings.store import Settings
from rossini.system.hal import Hal, load_profile
from rossini.system.power import PowerManager


class SettingsTest(unittest.TestCase):
    def test_validation_persistence_and_subscribers(self):
        with tempfile.TemporaryDirectory() as d:
            p = os.path.join(d, "s.json")
            s, seen = Settings(p), []
            s.subscribe("display.", lambda k, v: seen.append((k, v)))
            s.set("display.rotation", 90)
            s.set("reader.font_size", 40)
            self.assertEqual(seen, [("display.rotation", 90)])
            for k, bad in (("display.rotation", 45), ("reader.font_size", 5), ("reader.justify", "yes"),
                           ("connect.opds_url", "ftp://x"), ("reader.font_size", True)):
                with self.assertRaises(ValueError):
                    s.set(k, bad)
            with self.assertRaises(KeyError):
                s.set("telemetry.enabled", True)
            s2 = Settings(p)
            self.assertEqual((s2.get("display.rotation"), s2.get("reader.font_size")), (90, 40))

    def test_corrupt_or_invalid_file_falls_back_to_defaults(self):
        with tempfile.TemporaryDirectory() as d:
            p = os.path.join(d, "s.json")
            open(p, "w").write('{"display.rotation": 7, "reader.font_size": 44')
            self.assertEqual(Settings(p).get("display.rotation"), 0)
            open(p, "w").write('{"display.rotation": 7, "reader.font_size": 44}')
            s = Settings(p)
            self.assertEqual((s.get("display.rotation"), s.get("reader.font_size")), (0, 44))


class PowerTest(unittest.TestCase):
    def test_standby_off_and_wake(self):
        t = [0]
        pm = PowerManager(60, 600, lambda: t[0])
        self.assertIsNone(pm.tick())
        t[0] = 61
        self.assertEqual(pm.tick(), "suspend")
        t[0] = 300; pm.activity()
        self.assertEqual(pm.state, "active")
        t[0] = 400
        self.assertEqual(pm.tick(), "suspend")
        t[0] = 1001
        self.assertEqual(pm.tick(), "poweroff")

    def test_critical_battery_only_when_not_charging(self):
        pm = PowerManager(60, 600, lambda: 0)
        self.assertIsNone(pm.tick(battery=3, charging=True))
        self.assertEqual(pm.tick(battery=3, charging=False), "poweroff_low_battery")
        self.assertTrue(PowerManager(1, 1, lambda: 0).battery_warning(10, False))

    def test_setting_changes_apply(self):
        t = [0]
        pm = PowerManager(60, 600, lambda: t[0])
        s = Settings()
        s.subscribe("power.", pm.configure)
        s.set("power.standby_s", 30)
        t[0] = 31
        self.assertEqual(pm.tick(), "suspend")


class HalTest(unittest.TestCase):
    def test_sysfs_reads_and_frontlight_write(self):
        with tempfile.TemporaryDirectory() as d:
            for rel, val in (("bat/capacity", "73"), ("bat/status", "Charging"), ("fl/max", "255"), ("fl/b", "0")):
                os.makedirs(os.path.join(d, os.path.dirname(rel)), exist_ok=True)
                open(os.path.join(d, rel), "w").write(val)
            hal = Hal({"sysfs": {"battery_capacity": "/bat/capacity", "battery_status": "/bat/status",
                                 "frontlight_max": "/fl/max", "frontlight_brightness": "/fl/b"}}, d)
            self.assertEqual((hal.battery_percent(), hal.charging()), (73, True))
            self.assertTrue(hal.set_frontlight(50))
            self.assertEqual(open(os.path.join(d, "fl/b")).read(), "128")
            self.assertIsNone(hal.wifi_connected())

    def test_board_without_capability_reports_none(self):
        hal = Hal({"sysfs": {}})
        self.assertEqual((hal.battery_percent(), hal.charging(), hal.set_frontlight(10)), (None, None, False))


if __name__ == "__main__":
    unittest.main()
