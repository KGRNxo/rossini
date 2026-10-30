"""WLAN through wpa_supplicant's control interface (wpa_cli). The passphrase is never stored: it is turned
into the WPA PSK (PBKDF2-SHA1, 4096 rounds, as wpa_passphrase does) and only that key ends up in the
supplicant configuration on the data partition (mode 0600)."""
import hashlib
import subprocess
import time
from dataclasses import dataclass


@dataclass
class Network:
    ssid: str
    signal: int = 0
    secured: bool = True
    saved_id: str = None


def psk(ssid, passphrase):
    if not 8 <= len(passphrase) <= 63 or not all(32 <= ord(c) < 127 for c in passphrase):
        raise ValueError("WPA-Passwort: 8 bis 63 druckbare ASCII-Zeichen")
    return hashlib.pbkdf2_hmac("sha1", passphrase.encode(), ssid.encode(), 4096, 32).hex()


class Wifi:
    def __init__(self, iface="wlan0", run=None, sleep=time.sleep):
        self.iface, self.sleep = iface, sleep
        self._run = run or (lambda argv: subprocess.run(argv, capture_output=True, text=True, timeout=20).stdout)

    def cli(self, *args):
        out = self._run(["wpa_cli", "-i", self.iface, *args]).strip()
        if args and args[0] in ("add_network",):
            return out
        if out.startswith("FAIL"):
            raise RuntimeError(f"wpa_cli {args[0]}: {out}")
        return out

    def status(self):
        return dict(l.split("=", 1) for l in self.cli("status").splitlines() if "=" in l)

    def saved(self):
        out = {}
        for line in self.cli("list_networks").splitlines()[1:]:
            parts = line.split("\t")
            if len(parts) >= 2:
                out[parts[1]] = parts[0]
        return out

    def scan(self, wait=3.0):
        self.cli("scan")
        self.sleep(wait)
        saved, best = self.saved(), {}
        for line in self.cli("scan_results").splitlines()[1:]:
            parts = line.split("\t")
            if len(parts) < 5 or not parts[4]:
                continue  # hidden networks are not listed
            ssid, sig = parts[4], int(parts[2])
            if ssid not in best or sig > best[ssid].signal:
                best[ssid] = Network(ssid, sig, any(x in parts[3] for x in ("WPA", "RSN", "WEP")), saved.get(ssid))
        return sorted(best.values(), key=lambda n: -n.signal)

    def connect(self, ssid, passphrase=None):
        """Add (or replace) the network and select it. Open networks pass no passphrase."""
        for name, nid in self.saved().items():
            if name == ssid:
                self.cli("remove_network", nid)
        nid = self.cli("add_network")
        if not nid.isdigit():
            raise RuntimeError(f"wpa_cli add_network: {nid}")
        self.cli("set_network", nid, "ssid", ssid.encode().hex())  # hex form needs no quoting
        if passphrase:
            self.cli("set_network", nid, "psk", psk(ssid, passphrase))
        else:
            self.cli("set_network", nid, "key_mgmt", "NONE")
        self.cli("select_network", nid)
        self.cli("save_config")
        return nid

    def forget(self, ssid):
        nid = self.saved().get(ssid)
        if nid is not None:
            self.cli("remove_network", nid)
            self.cli("save_config")

    def wait_connected(self, timeout=20.0, step=1.0):
        end = time.monotonic() + timeout
        while time.monotonic() < end:
            st = self.status()
            if st.get("wpa_state") == "COMPLETED":
                return st
            self.sleep(step)
        return None
