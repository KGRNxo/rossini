import os
import tempfile
import unittest

from rossini.system import networking, suspend
from rossini.system.usb import UsbExport


class FakeWpa:
    def __init__(self):
        self.calls, self.nets = [], {}

    def __call__(self, argv):
        args = tuple(argv[3:])
        self.calls.append(args)
        cmd = args[0]
        if cmd == "scan_results":
            return ("bssid / frequency / signal level / flags / ssid\n"
                    "aa:bb\t2412\t-40\t[WPA2-PSK-CCMP][ESS]\tZuhause\n"
                    "aa:bc\t5180\t-70\t[WPA2-PSK-CCMP][ESS]\tZuhause\n"
                    "cc:dd\t2437\t-60\t[ESS]\tCafé Frei\n"
                    "ee:ff\t2437\t-50\t[WPA2]\t\n")
        if cmd == "list_networks":
            return "network id / ssid / bssid / flags\n" + "".join(f"{i}\t{s}\tany\t\n" for s, i in self.nets.items())
        if cmd == "add_network":
            nid = str(len(self.nets) + 10)
            self.nets[f"pending{nid}"] = nid
            return nid
        if cmd == "set_network" and args[2] == "ssid":
            name = bytes.fromhex(args[3]).decode()
            self.nets = {(name if v == args[1] else k): v for k, v in self.nets.items()}
        if cmd == "remove_network":
            self.nets = {k: v for k, v in self.nets.items() if v != args[1]}
        if cmd == "status":
            return "wpa_state=COMPLETED\nssid=Zuhause\nip_address=192.168.1.20\n"
        return "OK"


class WifiTest(unittest.TestCase):
    def test_scan_connect_forget_and_psk(self):
        fake = FakeWpa()
        w = networking.Wifi(run=fake, sleep=lambda s: None)
        nets = w.scan()
        self.assertEqual([(n.ssid, n.signal, n.secured) for n in nets], [("Zuhause", -40, True), ("Café Frei", -60, False)])
        nid = w.connect("Zuhause", "geheimes passwort")
        sets = [c for c in fake.calls if c[0] == "set_network"]
        self.assertEqual(sets[0][2:], ("ssid", "Zuhause".encode().hex()))
        self.assertEqual(sets[1][2], "psk")
        self.assertEqual(len(sets[1][3]), 64)
        self.assertNotIn("geheimes passwort", repr(fake.calls))  # passphrase never reaches the supplicant
        # RFC/IEEE 802.11i test vector (Annex H.4): passphrase "password", SSID "IEEE"
        self.assertEqual(networking.psk("IEEE", "password"), "f42c6fc52df0ebef9ebb4b90b38a5f902e83fe1b135a70e23aed762e9710a12e")
        self.assertEqual(w.saved(), {"Zuhause": nid})
        w.connect("Zuhause", "anderes passwort")  # re-adding replaces, never duplicates
        self.assertEqual(len(w.saved()), 1)
        self.assertEqual(w.wait_connected()["ip_address"], "192.168.1.20")
        w.forget("Zuhause")
        self.assertEqual(w.saved(), {})
        w.connect("Café Frei")
        self.assertIn(("set_network", w.saved()["Café Frei"], "key_mgmt", "NONE"), fake.calls)
        for bad in ("kurz", "x" * 64, "ümlaut-passwort"):
            with self.assertRaises(ValueError):
                networking.psk("a", bad)


class SuspendTest(unittest.TestCase):
    def test_writes_alarm_then_state(self):
        with tempfile.TemporaryDirectory() as d:
            os.makedirs(f"{d}/power"); os.makedirs(f"{d}/class/rtc/rtc0")
            open(f"{d}/power/state", "w").write("freeze mem\n")
            open(f"{d}/class/rtc/rtc0/wakealarm", "w").close()
            state, _ = suspend.suspend(wake_after=5, sysfs=d)
            self.assertEqual(state, "mem")
            self.assertEqual(open(f"{d}/power/state").read(), "mem")
            self.assertEqual(open(f"{d}/class/rtc/rtc0/wakealarm").read(), "+5")
            open(f"{d}/power/state", "w").write("disk\n")
            with self.assertRaises(OSError):
                suspend.suspend(sysfs=d)


class UsbTest(unittest.TestCase):
    def test_export_only_when_unmounted_and_round_trip(self):
        with tempfile.TemporaryDirectory() as d:
            os.makedirs(f"{d}/udc/musb-hdrc.0"); os.makedirs(f"{d}/cfg/usb_gadget")
            mounts = f"{d}/mounts"
            open(mounts, "w").write("/dev/mmcblk0p4 /media/books vfat rw 0 0\n")
            calls = []

            def run(argv):
                calls.append(argv)
                if argv[0] == "umount":
                    open(mounts, "w").write("")
                elif argv[0] == "mount":
                    open(mounts, "w").write("/dev/mmcblk0p4 /media/books vfat rw 0 0\n")
                return 0
            u = UsbExport("/dev/mmcblk0p4", "/media/books", configfs=f"{d}/cfg", udc_dir=f"{d}/udc", mounts=mounts, run=run)
            u.start()
            self.assertEqual(calls[0], ["umount", "/media/books"])
            g = f"{d}/cfg/usb_gadget/rossini"
            self.assertEqual(open(f"{g}/UDC").read(), "musb-hdrc.0")
            self.assertEqual(open(f"{g}/functions/mass_storage.usb0/lun.0/file").read(), "/dev/mmcblk0p4")
            self.assertTrue(os.path.islink(f"{g}/configs/c.1/mass_storage.usb0"))
            self.assertTrue(u.active())
            u.stop()
            self.assertFalse(u.active())
            self.assertEqual(calls[-1], ["mount", "/dev/mmcblk0p4", "/media/books"])

    def test_refuses_without_udc_or_when_busy(self):
        with tempfile.TemporaryDirectory() as d:
            open(f"{d}/mounts", "w").write("/dev/sdb1 /media/books vfat rw 0 0\n")
            u = UsbExport("/dev/sdb1", "/media/books", configfs=d, udc_dir=f"{d}/none", mounts=f"{d}/mounts", run=lambda a: 0)
            with self.assertRaises(OSError):
                u.start()
            os.makedirs(f"{d}/udc/x")
            u = UsbExport("/dev/sdb1", "/media/books", configfs=d, udc_dir=f"{d}/udc", mounts=f"{d}/mounts", run=lambda a: 1)
            with self.assertRaisesRegex(OSError, "in Benutzung"):
                u.start()


if __name__ == "__main__":
    unittest.main()
