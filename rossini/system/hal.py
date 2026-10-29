"""Hardware abstraction through sysfs. Paths come from the board profile (boards/<id>/profile.json);
a board that does not declare a path simply has no such capability (None), nothing is guessed."""
import json
import os

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def load_profile(board_id, root=ROOT):
    with open(os.path.join(root, "boards", board_id, "profile.json")) as f:
        return json.load(f)


class Hal:
    def __init__(self, profile, sysroot="/"):
        self.p, self.sysroot = profile, sysroot
        self.sysfs = profile.get("sysfs", {})

    def _path(self, key):
        v = self.sysfs.get(key)
        return os.path.join(self.sysroot, v.lstrip("/")) if v else None

    def _read(self, key):
        p = self._path(key)
        try:
            with open(p) as f:
                return f.read().strip()
        except (TypeError, OSError):
            return None

    def battery_percent(self):
        v = self._read("battery_capacity")
        return int(v) if v and v.isdigit() else None

    def charging(self):
        v = self._read("battery_status")
        return None if v is None else v.lower() in ("charging", "full")

    def frontlight_max(self):
        v = self._read("frontlight_max")
        return int(v) if v and v.isdigit() else None

    def set_frontlight(self, percent):
        """percent 0..100 -> raw brightness. Returns False if the board has no frontlight."""
        p, mx = self._path("frontlight_brightness"), self.frontlight_max()
        if not p or not mx:
            return False
        with open(p, "w") as f:
            f.write(str(round(mx * percent / 100)))
        return True

    def wifi_connected(self):
        v = self._read("wifi_operstate")
        return None if v is None else v == "up"
