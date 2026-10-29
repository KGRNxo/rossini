"""PID 1 of the Rossini userland. Sequence:
 mount -> data dirs -> start services -> boot self-test -> confirm slot (or reboot so the
 bootloader can roll back) -> optional test scenario from the kernel command line.
Kernel command line keys: rossini.slot=A|B  rossini.test=boot|update|bad-update  rossini.mode=normal"""
import json
import os
import subprocess
import sys
import time

from ..updater.bootctl import BootCtl
from .supervisor import Service, Supervisor

PY = sys.executable or "/usr/bin/python3"


def log(msg):
    print(f"ROSSINI: {msg}", flush=True)


def cmdline(path="/proc/cmdline"):
    out = {}
    try:
        with open(path) as f:
            for tok in f.read().split():
                k, _, v = tok.partition("=")
                out[k] = v
    except OSError:
        pass
    return out


def sh(*argv):
    return subprocess.run(argv, capture_output=True, text=True).returncode


class Init:
    def __init__(self, data="/data", boot="/boot", slot=None, version="?", pid1=True, powerctl=None, py=PY):
        self.data, self.boot, self.slot, self.version, self.pid1 = data, boot, slot, version, pid1
        self.py = py
        self.powerctl = powerctl or self._powerctl
        self.bootctl_path = os.path.join(boot, "bootctl")

    @staticmethod
    def _powerctl(action):
        sh("sync")
        sh("poweroff" if action == "poweroff" else "reboot", "-f")
        time.sleep(30)

    def prepare(self):
        if os.getpid() == 1:
            sh("ip", "link", "set", "lo", "up")  # loopback is needed by local services
        for d in ("books", "rossini", "exports", "update"):
            os.makedirs(os.path.join(self.data, d), exist_ok=True)

    def services(self):
        py, data = self.py, self.data
        return [Service("library-index", [py, "-m", "rossini.library.indexer", data], oneshot=True),
                Service("connectd", [py, "-m", "rossini.connect.daemon", data, "8080"], after=["library-index"]),
                Service("selftest", [py, "-m", "rossini.system.selftest", data, "/run/rossini-selftest"],
                        oneshot=True, after=["connectd"])]

    def bring_up(self):
        """Returns True if the self-test passed."""
        log(f"boot slot={self.slot} version={self.version}")
        self.prepare()
        os.makedirs("/run/rossini", exist_ok=True)
        sup = Supervisor(self.services(), log=lambda m: log(m))
        sup.run_until_settled(timeout=300)
        ok = sup.svc["selftest"].status == "done"
        log(f"selftest {'PASS' if ok else 'FAIL'}")
        self.sup = sup
        return ok

    def run(self):
        opts = cmdline()
        scenario = opts.get("rossini.test", "")
        ok = self.bring_up()
        ctl = BootCtl(self.bootctl_path) if os.path.exists(self.bootctl_path) else None
        if ctl and ctl.trial == self.slot:
            if ok:
                ctl.confirm(self.slot)
                log(f"confirmed slot {self.slot} version {self.version}")
            else:
                log(f"slot {self.slot} NOT confirmed (self-test failed); rebooting so the bootloader can roll back")
                self.sup.stop_all()
                return self.powerctl("reboot")
        elif not ok:
            log("self-test failed on the confirmed slot; staying down")
            self.sup.stop_all()
            return self.powerctl("poweroff")
        if scenario in ("update", "bad-update") and self.slot == (ctl.confirmed if ctl else None):
            pkg = os.path.join(self.data, "update", "rossini.pkg")
            if os.path.exists(pkg) and not ctl.trial:
                log("update package found, installing")
                rc = sh(self.py, "-m", "rossini.updater.cli", "install", pkg, "--board", "qemu-x86_64",
                        "--pubkey", "/etc/rossini/update.pub", "--bootctl", self.bootctl_path)
                log(f"update install rc={rc}")
                os.rename(pkg, pkg + ".done")
                self.sup.stop_all()
                return self.powerctl("reboot" if rc == 0 else "poweroff")
        log("scenario complete")
        self.sup.stop_all()
        return self.powerctl("poweroff")


def main():
    opts = cmdline()
    ver = open("/etc/rossini/version").read().strip() if os.path.exists("/etc/rossini/version") else "dev"
    Init(slot=os.environ.get("ROSSINI_SLOT") or opts.get("rossini.slot"), version=ver).run()


if __name__ == "__main__":
    main()
