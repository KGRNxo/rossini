import struct
import unittest

from PIL import Image, ImageDraw

from rossini.display import input as I
from rossini.display.eink import Display, Recorder, quantize


def frame(fill=255, box=None):
    im = Image.new("L", (100, 200), fill)
    if box:
        ImageDraw.Draw(im).rectangle(box, fill=0)
    return im


class EinkTest(unittest.TestCase):
    def test_unchanged_frame_is_not_sent(self):
        r = Recorder(); d = Display((100, 200), r)
        self.assertEqual(d.present(frame()), "full")
        self.assertIsNone(d.present(frame()))
        self.assertEqual(len(r.updates), 1)

    def test_partial_region_and_periodic_full_refresh(self):
        r = Recorder(); d = Display((100, 200), r, full_every=3)
        d.present(frame())
        self.assertEqual(d.present(frame(box=(10, 20, 30, 40))), "partial")
        self.assertEqual(r.updates[-1][0], (10, 20, 31, 41))
        modes = [d.present(frame(box=(10, 20 + i, 30, 40 + i))) for i in range(1, 5)]
        self.assertEqual(modes, ["partial", "partial", "full", "partial"])

    def test_rotation_forces_full_and_swaps_geometry(self):
        r = Recorder(); d = Display((100, 200), r)
        d.present(frame())
        d.set_rotation(90)
        self.assertEqual(d.logical_size, (200, 100))
        self.assertEqual(d.present(Image.new("L", (200, 100), 255)), "full")
        with self.assertRaises(ValueError):
            d.present(frame())

    def test_quantize_to_16_levels(self):
        im = quantize(Image.linear_gradient("L"))
        self.assertLessEqual(len(set(im.getdata())), 16)
        self.assertEqual(quantize(Image.new("L", (1, 1), 255)).getpixel((0, 0)), 255)


def ev(t, typ, code, val):
    return (t, typ, code, val)


class InputTest(unittest.TestCase):
    def run_events(self, evs, tr=None):
        tr = tr or I.TouchTracker((1000, 1400))
        out = []
        for e in evs:
            out += tr.feed(*e)
        return out

    def touch(self, t0, t1, p0, p1):
        return [ev(t0, I.EV_ABS, I.ABS_MT_POSITION_X, p0[0]), ev(t0, I.EV_ABS, I.ABS_MT_POSITION_Y, p0[1]),
                ev(t0, I.EV_ABS, I.ABS_MT_TRACKING_ID, 5), ev(t0, I.EV_SYN, 0, 0),
                ev((t0 + t1) / 2, I.EV_ABS, I.ABS_MT_POSITION_X, p1[0]), ev((t0 + t1) / 2, I.EV_ABS, I.ABS_MT_POSITION_Y, p1[1]),
                ev((t0 + t1) / 2, I.EV_SYN, 0, 0),
                ev(t1, I.EV_ABS, I.ABS_MT_TRACKING_ID, -1), ev(t1, I.EV_SYN, 0, 0)]

    def test_tap_long_press_swipe(self):
        g = self.run_events(self.touch(1.0, 1.1, (500, 700), (502, 701)))
        self.assertEqual([(x.kind, x.x, x.y) for x in g], [("tap", 502, 701)])
        g = self.run_events(self.touch(1.0, 1.9, (500, 700), (500, 700)))
        self.assertEqual(g[0].kind, "long_press")
        g = self.run_events(self.touch(1.0, 1.2, (800, 700), (200, 710)))
        self.assertEqual((g[0].kind, g[0].direction), ("swipe", "left"))
        g = self.run_events(self.touch(1.0, 1.2, (500, 200), (500, 900)))
        self.assertEqual(g[0].direction, "down")

    def test_long_press_fires_once_while_held(self):
        tr = I.TouchTracker((1000, 1400))
        out = self.run_events(self.touch(1.0, 3.0, (100, 100), (100, 100))[:4], tr)
        self.assertEqual(out, [])
        self.assertEqual(tr.poll(1.7)[0].kind, "long_press")
        self.assertEqual(tr.poll(1.9), [])
        self.assertEqual(tr.feed(2.0, I.EV_ABS, I.ABS_MT_TRACKING_ID, -1), [])

    def test_keys_and_raw_decoding(self):
        buf = struct.pack("llHHi", 5, 500000, I.EV_KEY, 109, 1) + struct.pack("llHHi", 5, 600000, I.EV_KEY, 109, 0)
        evs = list(I.decode(buf))
        self.assertEqual(evs[0], (5.5, I.EV_KEY, 109, 1))
        g = self.run_events(evs)
        self.assertEqual([(x.kind, x.direction) for x in g], [("key", "page_down")])


if __name__ == "__main__":
    unittest.main()
