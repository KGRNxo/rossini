# Architecture

## Inventory of the starting point
The repository was empty when this code base was started (no commits on the remote). The earlier Rossini Reader 0.9 /
Rossini OS 0.3 sources, boards, Buildroot integration and tests were not available, so nothing could be reused or assessed.
If they surface, they should be reviewed against this code base before anything is merged.

## Layers

```
 Rossini Shell (rossini/shell)  --uses-->  Reader session, Library, Connect, Settings
        |                                       |
 App (gestures -> frames)                 SQLite (data partition), user files untouched
        |
 Display (diff, refresh policy, rotation)  <--  backends: PNG | fbdev | (board EPD backend: missing)
 Input (evdev -> gestures)
        |
 System: init (PID 1) -> supervisor -> services (indexer, connectd, selftest)
         power policy, sysfs HAL (paths from boards/<id>/profile.json)
        |
 Update/boot: bootctl (A/B) <- updater (verify, write slot, arm trial) ; recovery
        |
 Linux kernel + bootloader  (BSP per device: NOT PRESENT for any Kindle)
```

Interfaces that matter:
* **Position = character offset** into the book's text stream. Fonts, size and margins can change without losing the place;
  progress, bookmarks and highlights all use it, and so does sync.
* **Library DB vs files:** book files are never written; edits live in `books` rows (`locked` protects them from rescans).
* **Settings keys** are the only way UI changes system behaviour; owners subscribe by key prefix.
* **bootctl** (flat `key=value`, U-Boot-env shaped) is the contract between updater, init, recovery and bootloader.
* **Board profile** is the contract between hardware facts and everything that must not guess them.

## Boot chain (QEMU development target)
QEMU loads kernel + `initramfs.cpio.gz`. `system/init/initramfs-init.sh` mounts the boot-state disk, asks
`bootctl-choose.sh` for a slot, mounts that slot's squashfs, moves /boot and /data into it and executes
`rossini.system.init` as PID 1. A slot in trial state gets 3 attempts; the booted system confirms itself only after the
boot self-test passes; otherwise it reboots and the chooser falls back to the confirmed slot. A trial slot that cannot be
mounted is dropped immediately.

On a Kindle, the chooser and its counters must live in the bootloader. Whether that bootloader can be replaced or even
extended is unknown (signature policy not verified): this is the main open technical risk.

## Decisions
* **Python userland.** Chosen for correctness and testability of a large amount of logic with few people. Cost: runtime
  footprint (the QEMU rootfs squashfs is ~25 MB including Python, Pillow, cryptography) and start-up time on slow CPUs.
  Unmeasured on any real reader. Hot paths (pagination, rendering) may move to C/Rust if measurements demand it.
* **Own reader engine for text formats** instead of KOReader (crengine/MuPDF). It covers epub/fb2/txt/cbz only. For PDF, MOBI, DJVU
  a native engine is required; embedding KOReader's engines (AGPL-3.0) behind the same `ReaderSession` interface is the likely route.
* **Buildroot is not used yet.** The dev images are assembled by `tools/build_images.py` from host busybox/Python and a distro
  kernel, which was enough to validate the boot chain but is not a cross-compiling ARM build. A Buildroot/Yocto tree
  becomes necessary with the first real BSP.
* **No telemetry code exists**; there is no telemetry setting.
* **Credentials are not stored** (no authenticated catalogs yet) rather than stored weakly.
