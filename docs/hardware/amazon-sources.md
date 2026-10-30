# What Amazon's published source says about each target

Amazon publishes the GPL source of every Kindle firmware at
https://www.amazon.com/gp/help/customer/display.html?nodeId=200203720 (one section per device, several `Kindle_src_<fw>_<build>.tar.gz` per
section). Everything below was read from those sources. Nothing was verified on a device.

## Which kernel for which device

| Device | Amazon section | Kernel | SoC | Rossini board |
|---|---|---|---|---|
| **Kindle 2024 ("Rossini")** | Kindle (11th Generation - 2024 Release) | Linux 4.9-lab126, 32-bit ARM | MediaTek MT8512 family | `kindle-kt6` |
| Paperwhite 6th/7th gen, Voyage, Kindle 7th gen | PW (6th), PW (7th), Voyage (7th), Kindle (7th) | Linux 3.0.35-lab126 (`imx60_wario_defconfig`) | NXP i.MX 6SoloLite | `kindle-pw2`, `-pw3`, `-voyage`, `-kt2` |
| Oasis (first generation) | (Amazon's README lists KOA) | Linux 3.0.35-lab126 (`imx60_duet_defconfig`) | NXP i.MX 6SoloLite | `kindle-oasis` |

The 3.0.35 tree is Amazon's `Kindle_src_5.10.1.1` release re-uploaded at https://github.com/katadelos/linux-3.0.35-lab126; the 4.9 tree is in
the 2024-release tarball (`gplrelease/linux-4.9.tar.gz`, pinned by sha256 in `boards/_families/amazon-rossini.json`). The latest 5.19.6 tarballs of
other sections contain unrelated kernels (Fire-tablet MediaTek 4.9/5.15/6.6): always take the tarball from the section of the device.

## KT6 / Rossini: what the source establishes

* **Identity.** The code names itself: `PRODUCT_ROSSINI` in `drivers/misc/mediatek/hwtcon_v2`, `BOARD_TYPE_ROSSINI` and `u-boot_version_rossini.json` in
  U-Boot. U-Boot maps the idme `board_id` (characters 3-5, "tattoo code" `3M5` or `3GM`) to the dtb `mt8110-cava`. `/proc/idme/board_id` exposes it
  on a running device. This yields a candidate gate rule (`boards/kindle-kt6/profile.json`, not active until checked against a real device).
* **Display.** MediaTek HWTCON v2 e-ink controller, `/dev/fb0` 8 bpp gray, panel 1448x1072. Update ioctls are mxcfb-shaped but the struct and the
  waveform numbering differ from the i.MX one; `rossini/display/mxcfb.py` implements both and `tests/unit/test_mxcfb.py` compiles
  static assertions against Amazon's `hwtcon_ioctl_cmd.h` with the ARM compiler.
* **Other hardware.** ROHM BD71828 PMIC (battery supply `bd71827_bat`), SGM3756 PWM frontlight, FITI e-paper PMIC, Parade or Goodix touch,
  MediaTek CONSYS Wi-Fi/BT, MAX20342 charger detection.
* **Bootloader (the decisive part).** U-Boot with Amazon's "UFBL" extension loads a **signed FIT image** from the eMMC partition `kernel`. On a
  *locked production device* only configurations signed with the key hint `fireos-production` are verified (everything else is skipped), the
  anti-rollback version is enforced (Rossini only), the secure-boot and production eFuses (`SBC_EN`, `AR_EN`) are read, console output is
  disabled, and `fastboot` refuses restricted commands. Leaving the locked state needs an unlock code that Amazon issues from the device's
  hardware serial; the code that checks it (`amzn_unlock.h`, `amzn_fastboot_lockdown.h`) is not in the published source.
  **Consequence: a normally sold KT6 will not start a Rossini kernel unless Amazon unlocks it.** This project neither contains nor will contain a
  way around that.

## 3.0.35 devices: what the source establishes

* i.MX6SL (`SOC_IMX6SL`), boot via ATAGs from the bootloader: `ATAG_SERIAL16`, `ATAG_REVISION16` (board id), `ATAG_MACADDR`, `ATAG_BOOTMODE` must be
  provided (`/proc/board_id`, `/proc/usid`, ... are filled from them). Default cmdline in `CONFIG_CMDLINE`.
* EPDC framebuffer `mxc_epdc_fb` (module), panel modes for five panels (1024x758, 1440x1080, 1448x1072, 800x600, 1072x1448); which device has which
  panel is not in the source.
* MAX77696 PMIC (battery `max77696-battery`, charger `max77696-charger`, backlight `max77696-bl` 12-bit, RTC, on-key), zForce2 or Cypress
  TrueTouch touch, FSR page keys (`KEY_PAGEUP`/`KEY_PAGEDOWN`), Hall sensor, ALS, Atheros AR6003 (base) or Broadcom 4343W (duet) Wi-Fi.
* Kernel features that constrain Rossini's userland: **no devtmpfs**, squashfs **zlib only**, no configfs gadget (use `g_file_storage`, implemented as
  `LegacyGadgetExport`), no `getrandom`/`statx`/`memfd`. glibc >= 2.26 refuses to start on 3.0.35 ("kernel too old"), hence the musl toolchain in
  `build/buildroot/configs/rossini_lab126_defconfig`.
* Their bootloader is not in the published release for these devices; its signature policy is unknown. The 2024 U-Boot shows the direction Amazon took.

## Not in any of the sources

Waveform files, Wi-Fi firmware, touch firmware, idme contents, the eMMC partition table, the unlock verification, and the physical mapping of
board-id codenames to marketing names for the 3.0.35 family.
