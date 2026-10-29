"""Linux evdev input: raw event decoding (multitouch type B + single touch + keys) and a
gesture recogniser producing tap / long-press / swipe. Pure logic, driven by timestamps."""
import struct
from dataclasses import dataclass

EVENT = struct.Struct("llHHi")  # struct input_event on 64-bit Linux
EV_SYN, EV_KEY, EV_ABS = 0, 1, 3
ABS_X, ABS_Y, ABS_MT_SLOT, ABS_MT_POSITION_X, ABS_MT_POSITION_Y, ABS_MT_TRACKING_ID = 0, 1, 0x2F, 0x35, 0x36, 0x39
BTN_TOUCH = 0x14A
KEYS = {104: "page_up", 109: "page_down", 105: "left", 106: "right", 116: "power", 102: "home", 158: "back"}


@dataclass
class Gesture:
    kind: str       # tap | long_press | swipe | key
    x: int = 0
    y: int = 0
    direction: str = ""  # left|right|up|down for swipes, key name for keys


def decode(buf):
    for off in range(0, len(buf) - EVENT.size + 1, EVENT.size):
        sec, usec, t, c, v = EVENT.unpack_from(buf, off)
        yield sec + usec / 1e6, t, c, v


class TouchTracker:
    """Turns evdev events into gestures. Only the first finger is tracked."""
    def __init__(self, screen, long_press=0.6, slop=None):
        self.w, self.h = screen
        self.long_press = long_press
        self.slop = slop or int(0.03 * max(screen))
        self.slot, self.down, self.x, self.y, self.t0, self.start = 0, False, 0, 0, 0.0, (0, 0)
        self.moved = False
        self.fired = False

    def feed(self, ts, etype, code, value):
        out = []
        if etype == EV_KEY and value == 1 and code in KEYS:
            return [Gesture("key", direction=KEYS[code])]
        if etype == EV_ABS:
            if code == ABS_MT_SLOT:
                self.slot = value
            elif self.slot == 0:
                if code in (ABS_MT_POSITION_X, ABS_X):
                    self.x = value
                elif code in (ABS_MT_POSITION_Y, ABS_Y):
                    self.y = value
                elif code == ABS_MT_TRACKING_ID:
                    self._edge(ts, value != -1, out)
        elif etype == EV_KEY and code == BTN_TOUCH:
            self._edge(ts, bool(value), out)
        elif etype == EV_SYN and self.down:
            if abs(self.x - self.start[0]) + abs(self.y - self.start[1]) > self.slop:
                self.moved = True
        return out

    def _edge(self, ts, down, out):
        if down and not self.down:
            self.down, self.t0, self.start, self.moved, self.fired = True, ts, (self.x, self.y), False, False
        elif not down and self.down:
            self.down = False
            if self.fired:
                return
            dx, dy = self.x - self.start[0], self.y - self.start[1]
            if self.moved and max(abs(dx), abs(dy)) > 0.12 * min(self.w, self.h):
                d = ("right" if dx > 0 else "left") if abs(dx) >= abs(dy) else ("down" if dy > 0 else "up")
                out.append(Gesture("swipe", self.x, self.y, d))
            elif not self.moved:
                kind = "long_press" if ts - self.t0 >= self.long_press else "tap"
                out.append(Gesture(kind, self.x, self.y))

    def poll(self, ts):
        """Call periodically: emits long_press while the finger is still down."""
        if self.down and not self.moved and not self.fired and ts - self.t0 >= self.long_press:
            self.fired = True
            return [Gesture("long_press", self.x, self.y)]
        return []
