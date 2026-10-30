import ctypes
import os
import shutil
import subprocess
import tempfile
import unittest

from PIL import Image

from rossini.display import mxcfb as M

HDR = os.environ.get("ROSSINI_LAB126_HEADERS", os.path.join(os.path.dirname(__file__), "..", "..", "build", "kernel", "hdr", "include"))  # `make headers_install` of the Lab126 tree
CC = os.environ.get("ROSSINI_ARM_CC") or shutil.which("arm-linux-gcc") or shutil.which("arm-linux-gnueabihf-gcc")


class FakeFb:
    """Stands in for /dev/fb0 + mmap: records ioctls, validates arguments like the driver would."""
    def __init__(self, w=1072, h=1448):
        self.w, self.h, self.calls, self.bpp = w, h, [], 32
        self.mem = bytearray(w * h)

    def opener(self, dev, flags):
        return os.open(os.devnull, os.O_RDWR)

    def mapper(self, fd, length, flags, prot):
        assert length == self.w * self.h
        return self.mem

    def ioctl(self, fd, req, arg):
        self.calls.append((req, bytes(arg) if hasattr(arg, "__buffer__") or isinstance(arg, (bytes, bytearray)) else arg))
        if req == M.FBIOGET_VSCREENINFO:
            arg.xres, arg.yres, arg.xres_virtual, arg.yres_virtual, arg.bits_per_pixel = self.w, self.h, self.w, self.h, self.bpp
        elif req == M.FBIOPUT_VSCREENINFO:
            assert arg.grayscale == M.GRAYSCALE_8BIT and arg.activate == M.FB_ACTIVATE_FORCE
            self.bpp = arg.bits_per_pixel
        elif req == M.FBIOGET_FSCREENINFO:
            arg.line_length = self.w
        return 0

    def sent(self):
        out = []
        for req, arg in self.calls:
            if req == M.MXCFB_SEND_UPDATE:
                out.append(M.UpdateData.from_buffer_copy(arg))
        return out


class MxcfbBackendTest(unittest.TestCase):
    def backend(self, fake=None, **kw):
        f = fake or FakeFb()
        return f, M.MxcfbBackend(ioctl=f.ioctl, opener=f.opener, mapper=f.mapper, **kw)

    def test_init_switches_to_8bit_gray_and_selects_queue_scheme(self):
        f, b = self.backend()
        reqs = [r for r, _ in f.calls]
        self.assertEqual(f.bpp, 8)
        self.assertIn(M.MXCFB_SET_UPDATE_SCHEME, reqs)
        self.assertEqual((b.width, b.height, b.stride), (1072, 1448, 1072))

    def test_update_copies_only_region_and_submits_matching_rect(self):
        f, b = self.backend()
        im = Image.new("L", (1072, 1448), 255)
        im.paste(0, (100, 200, 140, 230))
        marker = b.update(im, (100, 200, 140, 230), "partial")
        self.assertEqual(f.mem[200 * 1072 + 100], 0)
        self.assertEqual(f.mem[200 * 1072 + 99], 0)  # untouched memory stays 0 (we did not write outside the region)
        self.assertEqual(f.mem[231 * 1072 + 100], 0)
        u = f.sent()[0]
        self.assertEqual((u.update_region.top, u.update_region.left, u.update_region.width, u.update_region.height), (200, 100, 40, 30))
        self.assertEqual((u.waveform_mode, u.update_mode, u.update_marker), (M.WAVEFORM["gl16_fast"], M.UPDATE_MODE_PARTIAL, marker))
        self.assertEqual(f.calls[-1][0], M.MXCFB_WAIT_FOR_UPDATE_COMPLETE)

    def test_full_refresh_uses_flashing_gc16_and_markers_increase(self):
        f, b = self.backend(wait=False)
        im = Image.new("L", (1072, 1448), 128)
        m1 = b.update(im, (0, 0, 1072, 1448), "full")
        m2 = b.update(im, (0, 0, 10, 10), "fast")
        u1, u2 = f.sent()
        self.assertEqual((u1.waveform_mode, u1.update_mode), (M.WAVEFORM["gc16"], M.UPDATE_MODE_FULL))
        self.assertEqual(u2.waveform_mode, M.WAVEFORM["du"])
        self.assertEqual(m2, m1 + 1)
        self.assertNotIn(M.MXCFB_WAIT_FOR_UPDATE_COMPLETE, [r for r, _ in f.calls])
        self.assertEqual(f.mem[5 * 1072 + 5], 128)

    def test_refuses_wrong_size_and_non_gray_framebuffer(self):
        f, b = self.backend()
        with self.assertRaises(ValueError):
            b.update(Image.new("L", (10, 10)), (0, 0, 10, 10), "full")

        class Stubborn(FakeFb):
            def ioctl(self, fd, req, arg):
                r = super().ioctl(fd, req, arg)
                if req == M.FBIOPUT_VSCREENINFO:
                    self.bpp = 32
                return r
        with self.assertRaisesRegex(OSError, "8 bpp"):
            self.backend(Stubborn())

    def test_plugs_into_display_layer(self):
        from rossini.display.eink import Display
        f, b = self.backend(wait=False)
        d = Display((1072, 1448), b)
        self.assertEqual(d.present(Image.new("L", (1072, 1448), 255)), "full")
        im = Image.new("L", (1072, 1448), 255)
        im.paste(0, (10, 10, 50, 50))
        self.assertEqual(d.present(im), "partial")
        self.assertEqual(f.sent()[1].update_region.width, 40)


class HwtconBackendTest(unittest.TestCase):
    def test_hwtcon_variant_uses_its_own_struct_and_waveforms(self):
        f = FakeFb(1448, 1072)
        b = M.MxcfbBackend(ioctl=f.ioctl, opener=f.opener, mapper=f.mapper, variant="hwtcon", wait=False)
        im = Image.new("L", (1448, 1072), 255)
        im.paste(0, (10, 20, 30, 40))
        b.update(im, (10, 20, 30, 40), "partial")
        b.update(im, (0, 0, 1448, 1072), "full")
        sent = [M.HwtconUpdateData.from_buffer_copy(a) for r, a in f.calls if r == M.MXCFB_SEND_UPDATE_HWTCON]
        self.assertEqual(len(sent), 2)
        self.assertEqual((sent[0].update_region.left, sent[0].update_region.top, sent[0].update_region.width), (10, 20, 20))
        self.assertEqual((sent[0].waveform_mode, sent[0].update_mode), (3, M.UPDATE_MODE_PARTIAL))   # GL16 in HWTCON numbering
        self.assertEqual((sent[1].waveform_mode, sent[1].update_mode), (2, M.UPDATE_MODE_FULL))      # GC16
        self.assertNotEqual(M.MXCFB_SEND_UPDATE, M.MXCFB_SEND_UPDATE_HWTCON)
        with self.assertRaises(ValueError):
            M.MxcfbBackend(ioctl=f.ioctl, opener=f.opener, mapper=f.mapper, variant="nope")


KT6_HDR = os.environ.get("ROSSINI_KT6_HWTCON_HEADER", os.path.join(os.path.dirname(__file__), "..", "..", "build", "kernel", "kt6", "hwtcon_ioctl_cmd.h"))


@unittest.skipUnless(CC and os.path.exists(KT6_HDR), "ARM cross compiler or KT6 hwtcon_ioctl_cmd.h missing (tools/fetch-kt6-source.command)")
class HwtconAbi(unittest.TestCase):
    def test_layout_and_ioctls_match_amazons_hwtcon_header(self):
        a = []
        for name, cls in (("mxcfb_update_data", M.HwtconUpdateData), ("mxcfb_swipe_data", M.SwipeData)):
            a.append(f'_Static_assert(sizeof(struct {name}) == {ctypes.sizeof(cls)}, "sizeof {name}");')
            for f, *_ in cls._fields_:
                a.append(f'_Static_assert(offsetof(struct {name}, {f}) == {getattr(cls, f).offset}, "{name}.{f}");')
        a.append(f'_Static_assert(MXCFB_SEND_UPDATE == 0x{M.MXCFB_SEND_UPDATE_HWTCON:08x}u, "send_update");')
        a.append(f'_Static_assert(MXCFB_WAIT_FOR_UPDATE_COMPLETE == 0x{M.MXCFB_WAIT_FOR_UPDATE_COMPLETE:08x}u, "wait");')
        for k, h in (("init", "INIT"), ("du", "DU"), ("gc16", "GC16"), ("gl16", "GL16"), ("reagl", "REAGL"), ("reagld", "REAGLD"), ("a2", "A2"), ("du4", "DU4")):
            a.append(f'_Static_assert(WAVEFORM_MODE_{h} == {M.WAVEFORM_HWTCON[k]}, "{k}");')
        with tempfile.TemporaryDirectory() as d:
            open(d + "/a.c", "w").write("#include <stdint.h>\n#include <stddef.h>\n#include <linux/ioctl.h>\n#include <linux/types.h>\n#include \"hwtcon_ioctl_cmd.h\"\n" + "\n".join(a))
            r = subprocess.run([CC, "-fsyntax-only", "-DPRODUCT_ROSSINI", "-I" + os.path.dirname(KT6_HDR), d + "/a.c"], capture_output=True, text=True)
        self.assertEqual(r.returncode, 0, r.stderr[-2500:])


@unittest.skipUnless(CC and os.path.isdir(HDR), "ARM cross compiler or exported Lab126 kernel headers missing")
class AbiAgainstKernelHeaders(unittest.TestCase):
    """Compiles static assertions with the ARM compiler against the real Lab126 headers."""
    def check(self, asserts):
        src = ("#include <linux/types.h>\n#include <linux/ioctl.h>\n#include <linux/fb.h>\n#include <linux/mxcfb.h>\n#include <stddef.h>\n#include <stdint.h>\n"
               + "\n".join(asserts))
        with tempfile.TemporaryDirectory() as d:
            open(d + "/a.c", "w").write(src)
            # -I puts the Lab126 headers ahead of the toolchain's own kernel headers; libc headers come from the sysroot
            return subprocess.run([CC, "-fsyntax-only", "-I" + HDR, d + "/a.c"], capture_output=True, text=True)

    def expected(self):
        out = []
        for name, cls in (("mxcfb_rect", M.Rect), ("mxcfb_alt_buffer_data", M.AltBuffer), ("mxcfb_update_data", M.UpdateData),
                          ("mxcfb_update_marker_data", M.MarkerData), ("fb_bitfield", M.Bitfield), ("fb_var_screeninfo", M.VarScreenInfo),
                          ("fb_fix_screeninfo", M.FixScreenInfo)):
            out.append(f'_Static_assert(sizeof(struct {name}) == {ctypes.sizeof(cls)}, "sizeof {name}");')
            for f, *_ in cls._fields_:
                if f != "reserved":
                    out.append(f'_Static_assert(offsetof(struct {name}, {f}) == {getattr(cls, f).offset}, "{name}.{f}");')
        for c in ("MXCFB_SEND_UPDATE", "MXCFB_WAIT_FOR_UPDATE_COMPLETE", "MXCFB_SET_UPDATE_SCHEME", "MXCFB_SET_AUTO_UPDATE_MODE", "MXCFB_SET_PWRDOWN_DELAY"):
            out.append(f'_Static_assert({c} == 0x{getattr(M, c):08x}u, "{c}");')
        for c, v in (("GRAYSCALE_8BIT", M.GRAYSCALE_8BIT), ("UPDATE_MODE_FULL", 1), ("UPDATE_MODE_PARTIAL", 0), ("UPDATE_SCHEME_QUEUE_AND_MERGE", 2),
                     ("WAVEFORM_MODE_GC16", 2), ("WAVEFORM_MODE_DU", 1), ("WAVEFORM_MODE_GL16_FAST", 6), ("TEMP_USE_AMBIENT", 0x1000)):
            out.append(f'_Static_assert({c} == {v}, "{c}");')
        return out

    def test_layouts_and_ioctl_numbers_match_kernel(self):
        r = self.check(self.expected())
        self.assertEqual(r.returncode, 0, r.stderr[-2500:])

    def test_the_check_can_fail(self):
        r = self.check(['_Static_assert(sizeof(struct mxcfb_update_data) == 1, "x");'])
        self.assertNotEqual(r.returncode, 0)

    def test_waveform_table_matches_header(self):
        names = {"init": "INIT", "du": "DU", "gc16": "GC16", "gc16_fast": "GC16_FAST", "a2": "A2", "gl16": "GL16", "gl16_fast": "GL16_FAST",
                 "du4": "DU4", "reagl": "REAGL", "reagld": "REAGLD"}
        r = self.check([f'_Static_assert(WAVEFORM_MODE_{h} == {M.WAVEFORM[k]}, "{k}");' for k, h in names.items()])
        self.assertEqual(r.returncode, 0, r.stderr[-1500:])


if __name__ == "__main__":
    unittest.main()
