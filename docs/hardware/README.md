# Hardware port: what is known, what blocks

## Verified facts about target devices
None. Every field in `boards/kindle-*/profile.json` is `null/unverified`. The Paperwhite 2/3 and Voyage profiles carry a
`claimed_unverified` SoC note taken from community documentation; it must be confirmed on a device before use.
For the Kindle Basic 2024 (KT6) no SoC, bootloader, display controller or storage layout is recorded. The model name alone
does not determine them, and this project has not measured a device.

## Blockers (in order)
1. **Facts.** Run `tools/hwdiag.sh` on the device (needs a shell; USB mass storage alone is not enough) and
   `tools/hwdiag.command` on the Mac. Output feeds the profile: SoC (`/proc/cpuinfo`, device-tree), partitions/MTD, framebuffer,
   backlight, power supply, input devices, network, USB gadget, suspend states.
2. **Bootloader policy.** Does the device's boot ROM/bootloader verify signatures on kernel and rootfs? Can an alternative kernel be
   booted at all, and is there a safe fallback to stock firmware? Until answered, no flashing code may be written.
3. **Independent recovery.** A recovery path that survives a bad kernel (second boot medium, key-combo entry, hardware
   download mode) must exist and be tested *before* the first install. Unknown for KT6.
4. **E-Ink driver.** (`rossini/shell/main.py` selects the backend from `display.backend` in the board profile; only `png` and generic `fbdev:/dev/fbN` exist.) The panel controller and its waveform handling must be identified. Rossini's `Display` needs a backend
   implementing `update(image, bbox, mode)` on that controller (mxcfb/EPDC on i.MX6 devices, something else elsewhere).
5. **Kernel.** Vendor kernel sources for the exact device (GPL source offers by the manufacturer), device tree, config, then
   WLAN/USB/battery/frontlight drivers.
6. **Suspend/resume**, measured power draw, wake sources.

## Safe order for a first hardware attempt (after 1-3 are answered)
1. Boot a Rossini kernel + initramfs **from RAM or secondary medium only**, without touching eMMC/NAND.
2. Verify display, touch, keys over several cold starts; collect `dmesg`.
3. Only then prepare a slot layout; keep stock firmware slot intact; test power cuts during update on a sacrificial device.
4. Fill `evidence` flags in the profile one by one with test logs in `tests/hardware/`; set `release_status` last.

Do not use a device that holds anything you cannot afford to brick. Do not copy drivers or boot parameters from another model.
