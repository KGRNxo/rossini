"""Suspend to RAM (or s2idle "freeze" where RAM suspend is unavailable) with an optional RTC wake alarm.
The write to /sys/power/state blocks until the system has resumed."""
import os
import time


def states(sysfs="/sys"):
    try:
        with open(os.path.join(sysfs, "power/state")) as f:
            return f.read().split()
    except OSError:
        return []


def suspend(prefer=("mem", "freeze"), wake_after=None, sysfs="/sys", rtc="rtc0"):
    """Returns (state used, seconds spent suspended). Raises OSError if the kernel refuses."""
    avail = states(sysfs)
    state = next((s for s in prefer if s in avail), None)
    if not state:
        raise OSError("kein Suspend-Zustand verfügbar")
    if wake_after:
        alarm = os.path.join(sysfs, "class/rtc", rtc, "wakealarm")
        with open(alarm, "w") as f:
            f.write("0")
        with open(alarm, "w") as f:
            f.write(f"+{int(wake_after)}")
    os.sync()  # data must be on disk before the device may lose power while asleep
    t = time.monotonic()
    with open(os.path.join(sysfs, "power/state"), "w") as f:
        f.write(state)
    return state, time.monotonic() - t
