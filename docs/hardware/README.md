# Hardware port: what is known, what blocks

Amazon's published GPL source releases changed the picture: SoC, display controller, PMIC, kernel and (for the 2024 Kindle) the bootloader policy are now
**known from source**; see [amazon-sources.md](amazon-sources.md). Nothing is verified on a device yet, and every board profile is still `research`.

## Per target

| Target | Kernel source | Kernel builds here | Bootloader | Verdict |
|---|---|---|---|---|
| **KT6 "Rossini" (Kindle 2024)** | Amazon 4.9, MediaTek MT8512 | see STATUS (built with GCC 13 using `kernel/patches/amazon-rossini-4.9`) | **locked production U-Boot: signed FIT (key 'fireos-production'), anti-rollback, Amazon-issued unlock** | Software side prepared; **blocked** on the unlock, which only Amazon can grant |
| PW2, PW3, Voyage, KT2 | Lab126 3.0.35 (`imx60_wario`) | yes (`kernel/patches/lab126-3.0.35`, tested: zImage + 35 modules) | unknown (not in the release) | Most promising for experiments, but unknown signature policy and no recovery path |
| Oasis 1 | Lab126 3.0.35 (`imx60_duet`) | config only (same tree) | unknown | as above |

## Still needed before any first run on a real device
1. **Read the device.** `tools/hwdiag.sh` on the device (needs a shell) and `tools/hwdiag.command` on the Mac. This replaces every "inferred from source" in the
   profiles: `/proc/idme/board_id` or `/proc/board_id`, partition table, panel id, sysfs names.
2. **Boot-chain answer.** KT6: unlock authorization (see above). 3.0.35 devices: can an alternative kernel be booted at all, and how does one get back?
3. **Independent recovery.** A path that survives a bad kernel (second boot medium, key-combo, download mode), tested *before* the first install.
4. **Firmware blobs.** E-ink waveform files, Wi-Fi and touch firmware are loaded by the drivers from files that are not in the source; they must come from the
   device's own firmware image (legal review needed before redistribution).
5. **Boot image format.** KT6: FIT in partition `kernel` (unsigned images are only accepted by an unlocked device). 3.0.35: U-Boot uImage + ATAGs.
6. **Suspend/resume, power measurements, thermal behaviour**, per device.

## Safe order for a first hardware attempt (after 1-3)
1. Boot a Rossini kernel + initramfs from RAM or a secondary medium only, without touching eMMC.
2. Verify display, touch, keys over several cold starts; collect `dmesg`.
3. Only then prepare a slot layout; keep the stock firmware slot intact; test power cuts during an update on a sacrificial device.
4. Fill `evidence` flags in the profile one by one with test logs in `tests/hardware/`; set `release_status` last.

Do not use a device holding anything you cannot afford to brick. Do not copy drivers or boot parameters from another model.
Rossini will not include exploits, unlock bypasses or tooling that defeats a device's secure boot.
