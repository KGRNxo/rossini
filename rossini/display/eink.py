"""E-Ink presentation layer. The shell draws into a gray framebuffer; this layer decides what
actually goes to the panel: nothing if nothing changed, a partial update of the changed region,
and a full flashing refresh when ghosting has accumulated or on request.
Backends: Recorder (tests), PngBackend (host preview), FbdevBackend (generic Linux fbdev only;
panel-specific controllers such as the Kindle EPDC need a board backend that does not exist yet)."""
from PIL import Image, ImageChops


def quantize(im, levels=16):
    n = levels - 1
    return im.point([round(round(i * n / 255) * 255 / n) for i in range(256)])


class Recorder:
    def __init__(self):
        self.updates = []

    def update(self, image, bbox, mode):
        self.updates.append((bbox, mode))


class PngBackend:
    def __init__(self, path):
        self.path = path
        self.count = 0

    def update(self, image, bbox, mode):
        image.save(self.path)
        self.count += 1


class FbdevBackend:
    """Writes 8-bit gray to a linux framebuffer node. Only valid for panels exposing 8bpp fbdev."""
    def __init__(self, dev="/dev/fb0"):
        self.dev = dev

    def update(self, image, bbox, mode):
        with open(self.dev, "r+b", buffering=0) as f:
            f.write(image.tobytes())


class Display:
    def __init__(self, size, backend, full_every=10, levels=16, base_rotation=0):
        """base_rotation: fixed rotation of the physical panel relative to the UI's portrait orientation (e.g. 90 for a
        landscape-native panel); the user's rotation setting is applied on top of it."""
        self.size, self.backend, self.full_every, self.levels = size, backend, full_every, levels
        self.base_rotation = base_rotation
        self.shown = None
        self.partials = 0
        self.rotation = 0
        self.force_full = True

    def set_rotation(self, degrees):
        if degrees not in (0, 90, 180, 270):
            raise ValueError("rotation must be 0/90/180/270")
        self.rotation = degrees
        self.force_full = True

    @property
    def total_rotation(self):
        return (self.rotation + self.base_rotation) % 360

    @property
    def logical_size(self):
        w, h = self.size
        return (h, w) if self.total_rotation in (90, 270) else (w, h)

    def request_full(self):
        self.force_full = True

    def present(self, image):
        """Show a logical-orientation frame. Returns the update mode used, or None if skipped."""
        if image.size != self.logical_size:
            raise ValueError(f"frame {image.size} != display {self.logical_size}")
        panel = quantize(image.rotate(-self.total_rotation, expand=True) if self.total_rotation else image, self.levels)
        if self.shown is None or self.force_full or self.partials >= self.full_every:
            mode, bbox = "full", (0, 0) + panel.size
        else:
            bbox = ImageChops.difference(self.shown, panel).getbbox()
            if bbox is None:
                return None
            mode = "partial"
        self.backend.update(panel, bbox, mode)
        self.shown = panel
        self.partials = 0 if mode == "full" else self.partials + 1
        self.force_full = False
        return mode
