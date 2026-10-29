# Status per component

Levels (each includes none of the later ones): **I** implemented · **T** automated tests · **Q** booted in QEMU ·
**H1** started on real hardware · **H2** functionally verified on real hardware · **R** released for installation.

No component has reached H1. The only release-ready target is none. Test counts: 70 unit/integration tests and 5 QEMU
boot-chain tests, all passing at the time of writing (see `tools/test-all.command`).

| Component | I | T | Q | H1+ | Notes / known gaps |
|---|---|---|---|---|---|
| Library (SQLite, epub/fb2/cbz/txt metadata, covers, duplicates, collections, tags, search, rescan, DRM detection) | yes | yes | yes (self-test) | no | PDF/MOBI/AZW3/DJVU/RTF/HTML/CBR files are ignored (no decoder); series metadata only from epub/fb2 |
| Reader (epub/fb2/txt text flow, cbz pages, TOC, search, bookmarks, highlights, position restore, reflow) | yes | yes | yes | no | Not done: PDF (zoom/crop/reflow), MOBI/AZW3, DJVU, RTF, HTML, CBR; hyphenation; dictionary; translation; images inside epub/fb2; night mode; custom touch zones; highlight creation by touch (API exists, no selection UI) |
| Shell (home, library, detail, reader + menu, TOC, on-screen keyboard, discover, settings, dialogs) | yes | yes | yes (rendered) | no | Layout verified only at 1072x1448 and three other sizes as images; never on an E-Ink panel; no collections editor UI; no WLAN picker UI |
| Settings (typed, validated, persisted, wired to display/power/reader/HAL) | yes | yes | yes | no | Frontlight/WLAN/battery depend on board sysfs paths that are unknown for all Kindles |
| Display layer (diff-based partial/full refresh, rotation, 16-gray quantisation, backends) | yes | yes | yes (PNG) | no | No E-Ink controller backend exists (Kindle EPDC/MTK path unknown); no temperature compensation; no waveform selection |
| Input (evdev decode, tap/long-press/swipe, keys) | yes | yes | no | no | Never fed from a real device node; only the first finger is tracked |
| Power (standby/off/critical-battery policy) | yes | yes | policy only | no | No suspend/resume implementation, no wake sources, no measurements |
| Init + supervisor + boot self-test | yes | yes | yes | no | Python PID 1; footprint on a Kindle unmeasured; no hardware watchdog |
| Updater (Ed25519 signed packages, board/rollback checks, A/B trial boot, rollback, slot write+readback) | yes | yes | yes | no | Bootloader side is the shell script `bootctl-choose.sh` in the QEMU initramfs; on hardware it must be reproduced in the real bootloader (U-Boot env semantics) |
| Recovery (verify, fsck, restore previous slot, export, factory reset) | yes | yes | yes | no | Separate initramfs, but started by the QEMU command line: an independent *hardware* recovery path (own boot media/key combo) does not exist |
| Installer + gate | yes | yes | n/a | no | Refuses every device: no profile has identification rules, evidence or an install method. No flashing code exists |
| Connect: OPDS client, WLAN upload server, folder sync | yes | yes (local test servers) | yes (loopback) | no | Not done: WLAN association/credentials, MTP/USB gadget, WebDAV, SFTP, real Calibre server test, authenticated catalogs |
| SDK | manifest validation only | yes | no | no | No app runtime, sandbox or API |
| Board support (kernel, device tree, drivers) | **no** | - | - | no | All four Kindle profiles are `research`; KT6 is empty |
| Reproducible build | yes | yes (two builds, identical hashes of squashfs/initramfs/pkg) | - | - | Same host toolchain only; Buildroot not used |

## What exists as artifacts

`build/out/` (not committed): `rootfs-<ver>.squashfs`, `initramfs.cpio.gz`, `recovery.cpio.gz`, signed `update-*.pkg`,
`vmlinuz` (Ubuntu's kernel, QEMU only), `SHA256SUMS`. None of these can run on a Kindle.
