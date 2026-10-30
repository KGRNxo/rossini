"""E-Ink backend for the Freescale/Lab126 EPDC framebuffer (mxc_epdc_fb, kernel 3.0.35-lab126 and compatible).
Draws 8-bit gray into the mmap'ed /dev/fb0 and submits regions with MXCFB_SEND_UPDATE. Two variants: the i.MX6 EPDC
(Kindle PW2/PW3/KV/KT2/KOA, kernel 3.0.35-lab126) and the MediaTek HWTCON (Kindle KT6 "Rossini", kernel 4.9-lab126).

Layouts and ioctl numbers mirror include/linux/mxcfb.h and include/linux/fb.h of the Lab126 source for 32-bit ARM
(`unsigned long` is 4 bytes). tests/unit/test_mxcfb.py compiles static assertions with the ARM cross compiler against
the real kernel headers when a kernel tree is available, so a drift is caught there.
NOT verified on real hardware."""
import ctypes
import fcntl
import mmap
import os
import time

# --- ioctl numbering (asm-generic, valid for ARM) --------------------------------------------------------------------
_W, _R = 1, 2


def _ioc(d, t, nr, size):
    return (d << 30) | (size << 16) | (ord(t) << 8) | nr


class Rect(ctypes.Structure):
    _fields_ = [("top", ctypes.c_uint32), ("left", ctypes.c_uint32), ("width", ctypes.c_uint32), ("height", ctypes.c_uint32)]


class AltBuffer(ctypes.Structure):
    _fields_ = [("phys_addr", ctypes.c_uint32), ("width", ctypes.c_uint32), ("height", ctypes.c_uint32), ("alt_update_region", Rect)]


class UpdateData(ctypes.Structure):  # Lab126 variant: has the two hist_* waveform fields
    _fields_ = [("update_region", Rect), ("waveform_mode", ctypes.c_uint32), ("update_mode", ctypes.c_uint32),
                ("update_marker", ctypes.c_uint32), ("hist_bw_waveform_mode", ctypes.c_uint32),
                ("hist_gray_waveform_mode", ctypes.c_uint32), ("temp", ctypes.c_int32), ("flags", ctypes.c_uint32),
                ("alt_buffer_data", AltBuffer)]


class SwipeData(ctypes.Structure):
    _fields_ = [("direction", ctypes.c_uint32), ("steps", ctypes.c_uint32)]


class HwtconUpdateData(ctypes.Structure):
    """MediaTek HWTCON (Kindle 'Rossini'/KT6, kernel 4.9-lab126, include/linux/hwtcon_ioctl_cmd.h)."""
    _fields_ = [("update_region", Rect), ("waveform_mode", ctypes.c_uint32), ("update_mode", ctypes.c_uint32),
                ("update_marker", ctypes.c_uint32), ("temp", ctypes.c_int32), ("flags", ctypes.c_uint32),
                ("dither_mode", ctypes.c_int32), ("quant_bit", ctypes.c_int32), ("alt_buffer_data", AltBuffer),
                ("swipe_data", SwipeData), ("hist_bw_waveform_mode", ctypes.c_uint32), ("hist_gray_waveform_mode", ctypes.c_uint32),
                ("ts_pxp", ctypes.c_uint32), ("ts_epdc", ctypes.c_uint32)]


class MarkerData(ctypes.Structure):
    _fields_ = [("update_marker", ctypes.c_uint32), ("collision_test", ctypes.c_uint32)]


class Bitfield(ctypes.Structure):
    _fields_ = [("offset", ctypes.c_uint32), ("length", ctypes.c_uint32), ("msb_right", ctypes.c_uint32)]


class VarScreenInfo(ctypes.Structure):
    _fields_ = [("xres", ctypes.c_uint32), ("yres", ctypes.c_uint32), ("xres_virtual", ctypes.c_uint32), ("yres_virtual", ctypes.c_uint32),
                ("xoffset", ctypes.c_uint32), ("yoffset", ctypes.c_uint32), ("bits_per_pixel", ctypes.c_uint32), ("grayscale", ctypes.c_uint32),
                ("red", Bitfield), ("green", Bitfield), ("blue", Bitfield), ("transp", Bitfield),
                ("nonstd", ctypes.c_uint32), ("activate", ctypes.c_uint32), ("height", ctypes.c_uint32), ("width", ctypes.c_uint32),
                ("accel_flags", ctypes.c_uint32), ("pixclock", ctypes.c_uint32), ("left_margin", ctypes.c_uint32),
                ("right_margin", ctypes.c_uint32), ("upper_margin", ctypes.c_uint32), ("lower_margin", ctypes.c_uint32),
                ("hsync_len", ctypes.c_uint32), ("vsync_len", ctypes.c_uint32), ("sync", ctypes.c_uint32), ("vmode", ctypes.c_uint32),
                ("rotate", ctypes.c_uint32), ("reserved", ctypes.c_uint32 * 5)]


class FixScreenInfo(ctypes.Structure):
    _fields_ = [("id", ctypes.c_char * 16), ("smem_start", ctypes.c_uint32), ("smem_len", ctypes.c_uint32), ("type", ctypes.c_uint32),
                ("type_aux", ctypes.c_uint32), ("visual", ctypes.c_uint32), ("xpanstep", ctypes.c_uint16), ("ypanstep", ctypes.c_uint16),
                ("ywrapstep", ctypes.c_uint16), ("line_length", ctypes.c_uint32), ("mmio_start", ctypes.c_uint32), ("mmio_len", ctypes.c_uint32),
                ("accel", ctypes.c_uint32), ("reserved", ctypes.c_uint16 * 3)]


FBIOGET_VSCREENINFO, FBIOPUT_VSCREENINFO, FBIOGET_FSCREENINFO = 0x4600, 0x4601, 0x4602
MXCFB_SET_AUTO_UPDATE_MODE = _ioc(_W, "F", 0x2D, 4)
MXCFB_SEND_UPDATE = _ioc(_W, "F", 0x2E, ctypes.sizeof(UpdateData))
MXCFB_SEND_UPDATE_HWTCON = _ioc(_W, "F", 0x2E, ctypes.sizeof(HwtconUpdateData))
MXCFB_WAIT_FOR_UPDATE_COMPLETE = _ioc(_W | _R, "F", 0x2F, ctypes.sizeof(MarkerData))
MXCFB_SET_PWRDOWN_DELAY = _ioc(_W, "F", 0x30, 4)
MXCFB_SET_UPDATE_SCHEME = _ioc(_W, "F", 0x32, 4)
MXCFB_GET_TEMPERATURE = _ioc(_R, "F", 0x38, 4)

GRAYSCALE_8BIT = 0x1
FB_ACTIVATE_FORCE = 128
FB_ACTIVATE_NOW = 0
UPDATE_MODE_PARTIAL, UPDATE_MODE_FULL = 0, 1
UPDATE_SCHEME_QUEUE_AND_MERGE = 2
AUTO_UPDATE_MODE_REGION_MODE = 0
TEMP_USE_AMBIENT = 0x1000
WAVEFORM = {"init": 0, "du": 1, "gc16": 2, "gc16_fast": 3, "a2": 4, "gl16": 5, "gl16_fast": 6, "du4": 7, "reagl": 8, "reagld": 9}
# Display layer mode -> (waveform, update mode). shortcut: static table; the Lab126 waveform tables per panel/temperature
# are inside the waveform firmware, which the driver selects by number. Upgrade: per-panel tuning measured on a device.
MODES = {"full": ("gc16", UPDATE_MODE_FULL), "partial": ("gl16_fast", UPDATE_MODE_PARTIAL), "fast": ("du", UPDATE_MODE_PARTIAL)}
# HWTCON uses different waveform numbers (WAVEFORM_MODE_ENUM in hwtcon_ioctl_cmd.h)
WAVEFORM_HWTCON = {"init": 0, "du": 1, "gc16": 2, "gl16": 3, "gl16_fast": 3, "reagl": 4, "reagld": 5, "a2": 6, "du4": 7}


class MxcfbBackend:
    """Display backend; pass in `ioctl`/`opener` to run without hardware."""

    def __init__(self, dev="/dev/fb0", ioctl=fcntl.ioctl, opener=os.open, mapper=mmap.mmap, wait=True, pwrdown_delay_ms=None,
                 variant="imx"):
        """variant: 'imx' (i.MX6 EPDC, Lab126 3.0.35) or 'hwtcon' (MediaTek, Lab126 4.9 / Kindle KT6 'Rossini')."""
        if variant not in ("imx", "hwtcon"):
            raise ValueError(variant)
        self.variant = variant
        self.ioctl, self.wait, self.marker = ioctl, wait, 0
        self.fd = opener(dev, os.O_RDWR)
        var, fix = VarScreenInfo(), FixScreenInfo()
        self._call(FBIOGET_VSCREENINFO, var)
        var.bits_per_pixel, var.grayscale, var.activate = 8, GRAYSCALE_8BIT, FB_ACTIVATE_FORCE
        var.yres_virtual = max(var.yres_virtual, var.yres)
        self._call(FBIOPUT_VSCREENINFO, var)
        self._call(FBIOGET_VSCREENINFO, var)
        if var.bits_per_pixel != 8:
            raise OSError(f"framebuffer refused 8 bpp grayscale (got {var.bits_per_pixel} bpp)")
        self._call(FBIOGET_FSCREENINFO, fix)
        self.width, self.height, self.stride = var.xres, var.yres, fix.line_length
        self.fb = mapper(self.fd, fix.line_length * var.yres_virtual, mmap.MAP_SHARED, mmap.PROT_READ | mmap.PROT_WRITE)
        self._call(MXCFB_SET_UPDATE_SCHEME, ctypes.c_uint32(UPDATE_SCHEME_QUEUE_AND_MERGE))
        self._call(MXCFB_SET_AUTO_UPDATE_MODE, ctypes.c_uint32(AUTO_UPDATE_MODE_REGION_MODE))
        if pwrdown_delay_ms is not None:
            self._call(MXCFB_SET_PWRDOWN_DELAY, ctypes.c_int32(pwrdown_delay_ms))

    def _call(self, request, arg):
        return self.ioctl(self.fd, request, arg)

    def update(self, image, bbox, mode):
        """image: PIL 'L' image of the full panel; bbox: (x0, y0, x1, y1) region to push."""
        x0, y0, x1, y1 = bbox
        if image.size != (self.width, self.height):
            raise ValueError(f"image {image.size} does not match framebuffer {(self.width, self.height)}")
        raw = image.tobytes()
        for y in range(y0, y1):  # copy only the changed rows/columns into the mapped buffer
            self.fb[y * self.stride + x0:y * self.stride + x1] = raw[y * self.width + x0:y * self.width + x1]
        wf, um = MODES[mode]
        self.marker = (self.marker % 0xFFFF) + 1
        region = Rect(y0, x0, x1 - x0, y1 - y0)
        if self.variant == "hwtcon":
            tbl = WAVEFORM_HWTCON
            upd = HwtconUpdateData(region, tbl[wf], um, self.marker, TEMP_USE_AMBIENT, 0, 0, 0, hist_bw_waveform_mode=tbl["gc16"],
                                   hist_gray_waveform_mode=tbl["gl16"])
        else:
            upd = UpdateData(region, WAVEFORM[wf], um, self.marker, WAVEFORM["gc16"], WAVEFORM["gl16"], TEMP_USE_AMBIENT, 0)
        self._call(MXCFB_SEND_UPDATE_HWTCON if self.variant == "hwtcon" else MXCFB_SEND_UPDATE, upd)
        if self.wait:
            self._call(MXCFB_WAIT_FOR_UPDATE_COMPLETE, MarkerData(self.marker, 0))
        return self.marker

    def close(self):
        self.fb.close()
        os.close(self.fd)
