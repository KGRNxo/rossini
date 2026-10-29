"""Power policy as a pure state machine driven by a clock: active -> standby -> off, plus a
critical-battery shutdown. The caller executes the returned action (suspend, flush+poweroff)."""
ACTIVE, STANDBY, OFF = "active", "standby", "off"


class PowerManager:
    def __init__(self, standby_s, off_s, clock, low_pct=15, critical_pct=5):
        self.standby_s, self.off_s, self.clock = standby_s, off_s, clock
        self.low_pct, self.critical_pct = low_pct, critical_pct
        self.state, self.last = ACTIVE, clock()
        self.standby_since = None

    def configure(self, key, value):  # settings subscriber
        if key == "power.standby_s":
            self.standby_s = value
        elif key == "power.off_s":
            self.off_s = value

    def activity(self):
        """User input or wake event."""
        self.state, self.last, self.standby_since = ACTIVE, self.clock(), None

    def request_standby(self):
        if self.state == ACTIVE:
            self.state, self.standby_since = STANDBY, self.clock()
            return "suspend"

    def tick(self, battery=None, charging=None):
        """Returns None | 'suspend' | 'poweroff' | 'poweroff_low_battery'."""
        if battery is not None and not charging and battery <= self.critical_pct:
            self.state = OFF
            return "poweroff_low_battery"  # caller must flush the database before powering off
        now = self.clock()
        if self.state == ACTIVE and now - self.last >= self.standby_s:
            self.state, self.standby_since = STANDBY, now
            return "suspend"
        if self.state == STANDBY and now - self.standby_since >= self.off_s:
            self.state = OFF
            return "poweroff"
        return None

    def battery_warning(self, battery, charging):
        return battery is not None and not charging and battery <= self.low_pct
