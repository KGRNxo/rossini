"""USB mass storage export of the book transfer partition through the Linux USB gadget configfs.
Safety rule: a partition is exported only while the OS does not have it mounted, so host and device never
write the same filesystem at the same time. The ext4 data partition (database, settings) is never exported."""
import os


class UsbExport:
    def __init__(self, device, mountpoint, configfs="/sys/kernel/config", udc_dir="/sys/class/udc",
                 mounts="/proc/mounts", run=None, gadget="rossini"):
        self.device, self.mountpoint, self.mounts = device, mountpoint, mounts
        self.g = os.path.join(configfs, "usb_gadget", gadget)
        self.udc_dir = udc_dir
        self.run = run or (lambda argv: os.spawnvp(os.P_WAIT, argv[0], argv))

    def udc(self):
        try:
            return sorted(os.listdir(self.udc_dir))[0]
        except (OSError, IndexError):
            return None

    def mounted(self):
        with open(self.mounts) as f:
            return any(line.split()[0] == self.device for line in f if line.strip())

    def active(self):
        try:
            with open(os.path.join(self.g, "UDC")) as f:
                return bool(f.read().strip())
        except OSError:
            return False

    def _w(self, rel, value):
        p = os.path.join(self.g, rel)
        os.makedirs(os.path.dirname(p), exist_ok=True)
        with open(p, "w") as f:
            f.write(value)

    def start(self):
        udc = self.udc()
        if not udc:
            raise OSError("Kein USB-Gerätecontroller (UDC) vorhanden")
        os.sync()
        if self.mounted() and self.run(["umount", self.mountpoint]) != 0:
            raise OSError("Bücherpartition ist in Benutzung und kann nicht freigegeben werden")
        if self.mounted():
            raise OSError("Bücherpartition ist noch eingebunden")
        self._w("idVendor", "0x1d6b")   # Linux Foundation
        self._w("idProduct", "0x0104")  # Multifunction Composite Gadget
        self._w("strings/0x409/manufacturer", "Rossini")
        self._w("strings/0x409/product", "Rossini E-Reader")
        self._w("configs/c.1/strings/0x409/configuration", "Bücher")
        self._w("functions/mass_storage.usb0/lun.0/removable", "1")
        self._w("functions/mass_storage.usb0/lun.0/file", self.device)
        link = os.path.join(self.g, "configs/c.1/mass_storage.usb0")
        if not os.path.lexists(link):
            os.symlink(os.path.join(self.g, "functions/mass_storage.usb0"), link)
        self._w("UDC", udc)

    def stop(self):
        """Detach from the host and mount the partition again; the caller rescans the library afterwards."""
        if self.active():
            self._w("UDC", "")
            self._w("functions/mass_storage.usb0/lun.0/file", "")
        if not self.mounted() and self.run(["mount", self.device, self.mountpoint]) != 0:
            raise OSError("Bücherpartition konnte nicht wieder eingebunden werden")
