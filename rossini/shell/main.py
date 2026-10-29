"""rossini-shell: the UI service. Reads touch/keys from evdev, drives the App, presents frames through the
board's display backend, runs the power policy (standby via suspend, power-off, critical battery).
Usage: python -m rossini.shell.main <data_dir> <board_id>"""
import fcntl
import glob
import os
import select
import struct
import sys
import time

from ..display import input as I
from ..display.eink import Display, FbdevBackend, PngBackend
from ..library.db import Library
from ..settings.store import Settings
from ..system import suspend as S
from ..system.hal import Hal, load_profile
from ..system.power import PowerManager
from .app import App, Ctx

EVIOCGABS = lambda axis: 0x80184540 + axis  # _IOR('E', 0x40 + axis, struct input_absinfo)


def abs_range(fd, axis):
    try:
        buf = fcntl.ioctl(fd, EVIOCGABS(axis), bytes(24))
        _, lo, hi, *_ = struct.unpack("6i", buf)
        return lo, hi
    except OSError:
        return None


class InputDevice:
    """One /dev/input/event* node with its own gesture tracker, scaled to screen coordinates."""
    def __init__(self, path, screen):
        self.fd = os.open(path, os.O_RDONLY | os.O_NONBLOCK)
        self.screen = screen
        self.rx = abs_range(self.fd, I.ABS_MT_POSITION_X) or abs_range(self.fd, I.ABS_X)
        self.ry = abs_range(self.fd, I.ABS_MT_POSITION_Y) or abs_range(self.fd, I.ABS_Y)
        self.tracker = I.TouchTracker(screen)

    def _scale(self, code, value):
        if code in (I.ABS_MT_POSITION_X, I.ABS_X) and self.rx and self.rx[1] > self.rx[0]:
            return int((value - self.rx[0]) * self.screen[0] / (self.rx[1] - self.rx[0] + 1))
        if code in (I.ABS_MT_POSITION_Y, I.ABS_Y) and self.ry and self.ry[1] > self.ry[0]:
            return int((value - self.ry[0]) * self.screen[1] / (self.ry[1] - self.ry[0] + 1))
        return value

    def read(self):
        try:
            buf = os.read(self.fd, I.EVENT.size * 64)
        except BlockingIOError:
            return []
        out = []
        for ts, t, c, v in I.decode(buf):
            out += self.tracker.feed(ts, t, c, self._scale(c, v) if t == I.EV_ABS else v)
        return out


def backend_for(profile, data):
    spec = profile.get("display", {}).get("backend", "png")
    if spec.startswith("fbdev:"):
        return FbdevBackend(spec.split(":", 1)[1])
    os.makedirs(os.path.join(data, "screens"), exist_ok=True)
    return PngBackend(os.path.join(data, "screens", "live.png"))


def run(data, board, poweroff=None, max_loops=None, inputs=None):
    profile = load_profile(board)
    geo = profile.get("display", {})
    size = (geo.get("width", 1072), geo.get("height", 1448))
    lib = Library(os.path.join(data, "rossini", "library.db"))
    st = Settings(os.path.join(data, "rossini", "settings.json"))
    hal = Hal(profile)
    power = PowerManager(st.get("power.standby_s"), st.get("power.off_s"), time.monotonic)
    ctx = Ctx(lib, st, hal, power, data, [os.path.join(data, "books")], time.time,
              open("/etc/rossini/version").read().strip() if os.path.exists("/etc/rossini/version") else "dev", board,
              actions={"poweroff": poweroff or (lambda: os.system("poweroff")), "reboot": lambda: os.system("reboot")})
    display = Display(size, backend_for(profile, data))
    app = App(ctx, display)
    display.present(app.render())
    print("shell: first frame presented", flush=True)
    devices = []
    for p in inputs if inputs is not None else sorted(glob.glob("/dev/input/event*")):
        try:
            devices.append(InputDevice(p, display.logical_size))
        except OSError:
            pass
    last_tick, loops = 0.0, 0
    while max_loops is None or loops < max_loops:
        loops += 1
        r, _, _ = select.select([d.fd for d in devices], [], [], 1.0)
        changed = False
        for dev in devices:
            if dev.fd in r:
                for g in dev.read():
                    if g.kind == "key" and g.direction == "power":
                        power.request_standby()
                        changed |= _sleep(app, display)
                    else:
                        changed |= app.handle(g)
            for g in dev.tracker.poll(time.time()):
                changed |= app.handle(g)
        now = time.monotonic()
        if now - last_tick >= 30:
            last_tick = now
            action = power.tick(hal.battery_percent(), hal.charging())
            if action == "suspend":
                changed |= _sleep(app, display)
            elif action in ("poweroff", "poweroff_low_battery"):
                app.shutdown()
                ctx.actions["poweroff"]()
                return action
            changed = True  # clock in the status bar
        if changed:
            display.present(app.render())
    return app  # only reached when max_loops is set (tests)


def _sleep(app, display):
    app.ctx.lib.db.commit()  # reading position is saved on every page turn; flush before power may drop
    try:
        S.suspend()
    except OSError as e:
        print(f"shell: suspend not possible: {e}", flush=True)
    app.ctx.power.activity()
    display.request_full()  # E-Ink may have drifted while asleep
    return True


if __name__ == "__main__":
    sys.exit(run(sys.argv[1], sys.argv[2]) and 0)
