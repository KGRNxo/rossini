"""A/B boot state in a flat key=value file. The format deliberately mirrors U-Boot environment
semantics (upgrade_available / bootcount / bootlimit) so that on real hardware the same logic
lives in the bootloader. tools/initramfs-init.sh implements the identical chooser in POSIX sh;
tests/unit/test_updater.py checks both implementations against each other."""
import os

from ..common import atomic_write

TRIES = 3
KEYS = ("confirmed", "trial", "tries", "rollback_index", "trial_rollback", "version_A", "version_B")
DEFAULTS = {"confirmed": "A", "trial": "", "tries": "0", "rollback_index": "0", "trial_rollback": "0",
            "version_A": "", "version_B": ""}


class BootCtl:
    def __init__(self, path):
        self.path, self.v = path, dict(DEFAULTS)
        if os.path.exists(path):
            with open(path) as f:
                for line in f:
                    k, _, val = line.strip().partition("=")
                    if k in DEFAULTS:
                        self.v[k] = val
        if self.v["confirmed"] not in ("A", "B") or self.v["trial"] not in ("", "A", "B"):
            raise ValueError("corrupt bootctl state")

    def save(self):
        atomic_write(self.path, "".join(f"{k}={self.v[k]}\n" for k in KEYS).encode())

    @property
    def confirmed(self):
        return self.v["confirmed"]

    @property
    def trial(self):
        return self.v["trial"]

    @staticmethod
    def other(slot):
        return "B" if slot == "A" else "A"

    def inactive(self):
        return self.other(self.confirmed)

    def begin_trial(self, slot, version, rollback_index):
        """Called only after the slot image was written and verified."""
        if slot != self.inactive():
            raise ValueError("can only update the inactive slot")
        self.v.update(trial=slot, tries=str(TRIES), trial_rollback=str(rollback_index), **{f"version_{slot}": version})
        self.save()

    def choose(self):
        """Boot-time decision (reference implementation of the bootloader logic). Persists the new counter."""
        if self.trial and int(self.v["tries"]) > 0:
            self.v["tries"] = str(int(self.v["tries"]) - 1)
            self.save()
            return self.trial
        if self.trial:  # trial slot never confirmed: roll back
            self.v.update(trial="", tries="0")
            self.save()
        return self.confirmed

    def confirm(self, slot):
        """Called by the booted system once its self-check passed."""
        if self.trial == slot:
            self.v.update(confirmed=slot, trial="", tries="0",
                          rollback_index=str(max(int(self.v["rollback_index"]), int(self.v["trial_rollback"]))))
            self.save()
            return True
        return self.confirmed == slot

    def status(self):
        return (f"aktiv {self.confirmed} v{self.v['version_' + self.confirmed] or '?'}"
                + (f", Test {self.trial} ({self.v['tries']} Versuche)" if self.trial else ", bestätigt"))
