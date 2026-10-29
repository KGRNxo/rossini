# Changelog

## 0.4.0-dev (unreleased)
First commit of the from-scratch Rossini OS code base (no earlier source was available in the repository).

Added: library (SQLite, epub/fb2/cbz/txt), reader (epub/fb2/txt text, cbz images), E-Ink display layer, evdev gestures,
Rossini Shell, settings store, power policy, sysfs HAL, OPDS client, WLAN transfer server, folder sync, signed updater
with A/B trial boot and rollback, installer gate, recovery tools, SDK manifest validation, QEMU x86_64 images and boot tests.

Not added: any Kindle kernel, bootloader, display driver or device image. See docs/STATUS.md.

### Added after the first commit
Readers for PDF (zoom, crop, reflow), MOBI/AZW3, DjVu, CBR, RTF, HTML; hyphenation; images in epub/fb2/mobi; night mode; configurable
tap zones; selection by long press with dictionary (StarDict), highlights and notes; WLAN via wpa_supplicant; WebDAV sync; USB mass-storage
export; suspend call; collections editor; reading statistics screen; shell service main loop; pure-Python Ed25519 verification;
Buildroot ARMv7 build with boot test.
