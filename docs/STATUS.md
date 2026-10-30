# Status per component

Levels (each includes none of the later ones): **I** implemented · **T** automated tests · **Q** booted in QEMU ·
**H1** started on real hardware · **H2** functionally verified on real hardware · **R** released for installation.

No component has reached H1; no device is released. At the time of writing: 92 unit/integration tests, 5 x86_64 QEMU
boot-chain tests and 1 ARMv7 (Buildroot) boot test, all passing (`tools/test-all.command`, `tools/build-arm.command`).

| Component | I | T | Q | H1+ | Notes / known gaps |
|---|---|---|---|---|---|
| Library (SQLite; epub, fb2, mobi/azw3, pdf, djvu, cbz/cbr, rtf, html, txt; covers, duplicates, collections, tags, search, rescan, DRM detection) | yes | yes | yes (self-test) | no | MOBI: HUFF/CDIC-compressed and encrypted files are refused; KF8 fragment order simplified (see `reader/mobi.py`); PDF/DjVu need PyMuPDF/djvulibre on the device |
| Reader, flowing formats (epub, fb2, mobi/azw3, html, rtf, txt, PDF reflow) | yes | yes | yes | no | Hyphenation (pyphen, book language), inline images (epub, fb2, mobi), TOC, search, bookmarks, highlights/notes by long-press selection, dictionary lookup (StarDict), night mode, configurable back-tap zone, position restore. Not done: tables/CSS layout, footnote pop-ups, text-to-speech, font choice beyond serif/sans, images inside HTML files |
| Reader, fixed layout (PDF via MuPDF, DjVu via djvulibre, cbz/cbr) | yes | yes | yes (PDF in ARM/x86 images) | no | Margin crop, 4 zoom steps with tile walking, search (PDF). No pinch gestures, no PDF annotations, no scanned-PDF OCR, no DRM PDFs |
| Shell (home, library + collections editor, detail, reader + menu, selection panel, WLAN picker, statistics, USB mode, settings, dialogs, keyboard) | yes | yes | yes (rendered) | no | Never shown on an E-Ink panel; layouts verified as images at 4 sizes; UI strings German only (setting `system.language` exists, no English translation yet) |
| Shell service (evdev -> gestures -> App -> display, power policy, suspend call) | yes | yes (FIFO as evdev) | yes (first frame) | no | Not run against a real touch device |
| Settings | yes | yes | yes | no | Frontlight/battery/WLAN indicator depend on board sysfs paths that are unknown for all Kindles |
| Display layer | yes | yes | yes (PNG) | no | No E-Ink controller backend (Kindle EPDC/MTK path unknown); no temperature compensation or waveform selection |
| Input (evdev decode, tap/long-press/swipe, keys, axis scaling) | yes | yes | no | no | Only the first finger is tracked |
| Power (policy) + suspend (`/sys/power/state` + RTC alarm) | yes | yes (fake sysfs) | **no** | no | In QEMU the guest enters s2idle but the emulated RTC alarm did not wake it, so resume is unverified. No wake-source configuration, no measurements |
| Init + supervisor + boot self-test | yes | yes | yes (x86_64, ARMv7) | no | Python PID 1; footprint on a Kindle unmeasured; no hardware watchdog |
| Updater: Ed25519-signed packages (device-side verification in pure Python, RFC 8032 vectors + cross-check against `cryptography`), board/rollback checks, A/B trial boot, rollback | yes | yes | yes (x86_64: trial, confirm, rollback; ARMv7: verification) | no | Bootloader side is a shell script in the QEMU initramfs; on hardware it must be reproduced in the real bootloader (U-Boot env semantics) |
| Recovery | yes | yes | yes | no | Separate initramfs, started by the QEMU command line: an independent *hardware* recovery path does not exist |
| Installer + gate | yes | yes | n/a | no | Refuses every device (no profile has identification rules, evidence or install method). No flashing code exists |
| Connect: OPDS, WLAN (wpa_supplicant control), upload server, folder sync, WebDAV sync (ETag), credentials file (0600) | yes | yes (local servers, fake wpa_cli) | partly (loopback) | no | WLAN never run against a real supplicant/radio; credentials not encrypted at rest; SFTP not implemented; not tested against a real Calibre/Nextcloud |
| USB mass-storage export (configfs gadget, unmounts before exporting) | yes | yes (fake configfs) | no | no | MTP not implemented; needs a UDC and a separate vfat books partition |
| SDK | manifest validation only | yes | no | no | No app runtime or sandbox |
| Board support: Amazon kernels (KT6 4.9 MediaTek; PW2/PW3/KV/KT2 and Oasis 3.0.35 i.MX6SL) | build recipes + patches | yes (patch-apply and ABI tests) | no | no | Both kernels compile with GCC 13 (KT6: zImage, mt8110-cava.dtb, 160+ modules incl. hwtcon_v2, goodix, pt5; wario: zImage + 35 modules). Never booted anywhere: there is no emulation of these SoCs and no device access. Device trees/configs are Amazon's unchanged |
| Display backend for real panels: i.MX6 EPDC (3.0.35) and MediaTek HWTCON (KT6) | yes | yes (fake framebuffer; struct layouts and ioctl numbers compile-checked with the ARM compiler against Amazon's headers) | no | no | Waveform tuning per panel/temperature is unknown; waveform firmware not available |
| Board profiles | KT6, PW2, PW3, Voyage, KT2, Oasis (all `research`) | yes (gate refuses all) | n/a | no | Facts are from Amazon source, flagged unverified; KT6 identification rule is a candidate only |
| Buildroot ARMv7 cross build | yes | yes | yes (vexpress-a9, kernel 6.12.51) | - | Reference board, not a Kindle SoC |
| Reproducible build (x86_64 images) | yes | yes (two builds, identical hashes) | - | - | Same host toolchain only; Buildroot output not yet checked for reproducibility |

## Artifacts

`build/out/` (x86_64 QEMU) and `build/arm/images/` (ARMv7 QEMU), not committed. Ubuntu's kernel and Buildroot's vexpress kernel are for
emulation only. None of these can run on a Kindle.

## Open at the time of writing
* `rossini_lab126_defconfig` (musl userland for 3.0.35) now selects mdev for /dev; its build is still unfinished and unverified.
  "musl runs on 3.0.35" is **not verified**; `tools/syscall_compat.py` (static syscall check against the kernel table) exists but was not run on that rootfs.
  The config also still needs `BR2_ROOTFS_DEVICE_CREATION_DYNAMIC_MDEV=y` (3.0.35 has no devtmpfs).
* Boot images: `rossini/installer/fit.py` builds an unsigned KT6 FIT (tested with mkimage and the real built kernel); no uImage/ATAG path for 3.0.35 yet.
