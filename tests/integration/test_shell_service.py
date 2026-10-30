"""The UI service main loop with a real evdev byte stream (FIFO) as touch input."""
import os
import struct
import tempfile
import threading
import unittest

from rossini.display import input as I
from rossini.shell import screens as S
from rossini.shell.main import run
from tests import fixtures as F


def ev(t, typ, code, val):
    return struct.pack("llHHi", int(t), int((t % 1) * 1e6), typ, code, val)


class ShellServiceTest(unittest.TestCase):
    def test_touch_stream_navigates_and_frames_are_presented(self):
        with tempfile.TemporaryDirectory() as d:
            os.makedirs(f"{d}/books")
            F.make_epub(f"{d}/books/a.epub")
            from rossini.library.db import Library
            Library(f"{d}/rossini/library.db").scan(f"{d}/books")
            fifo = f"{d}/event0"
            os.mkfifo(fifo)
            # tap on the second bottom tab ("Bibliothek"): x in the 2nd fifth, y near the bottom
            x, y = 1072 // 5 + 100, 1448 - 40
            stream = (ev(1, I.EV_ABS, I.ABS_MT_POSITION_X, x) + ev(1, I.EV_ABS, I.ABS_MT_POSITION_Y, y) +
                      ev(1, I.EV_ABS, I.ABS_MT_TRACKING_ID, 1) + ev(1, I.EV_SYN, 0, 0) +
                      ev(1.1, I.EV_ABS, I.ABS_MT_TRACKING_ID, -1) + ev(1.1, I.EV_SYN, 0, 0))
            holder = os.open(fifo, os.O_RDONLY | os.O_NONBLOCK)  # keep a reader so the writer can open
            def writer():
                with open(fifo, "wb") as f:
                    f.write(stream)
            t = threading.Thread(target=writer); t.start()
            app = run(d, "qemu-x86_64", max_loops=3, inputs=[fifo])
            t.join(); os.close(holder)
            self.assertIsInstance(app.stack[-1], S.LibraryList)
            self.assertTrue(os.path.exists(f"{d}/screens/live.png"))
            app.ctx.lib.close()


if __name__ == "__main__":
    unittest.main()
