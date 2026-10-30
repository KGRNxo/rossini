# Boot chains

## QEMU development target (implemented and tested)
`qemu -kernel vmlinuz -initrd initramfs.cpio.gz` -> `system/init/initramfs-init.sh` mounts the boot-state disk (`bootctl`), asks
`bootctl-choose.sh` for slot A or B, mounts that slot's squashfs, moves /boot and /data into it and executes `rossini.system.init`. Trial slots
get three attempts; the booted system confirms itself after its self-test or reboots (rollback by the chooser). The chooser is a stand-in for a
bootloader: it uses the same variables as U-Boot's bootcount scheme, so the logic can move into a real bootloader unchanged.

## Kindle 2024 (KT6 "Rossini") as far as Amazon's source shows
```
BROM (MediaTek, secure boot fuse SBC_EN) -> preloader -> U-Boot + UFBL -> `booteink`
   reads FIT image from eMMC partition "kernel", verifies (locked production device: key hint 'fireos-production' only,
   anti-rollback version), bootm '#conf-mt8110-cava' -> Linux 4.9-lab126 -> init
```
* A/B for Rossini would need either two FIT partitions with a bootloader that selects one (U-Boot environment/`bootcount`), or a Rossini-owned
  stage inside the single FIT (kernel + initramfs that kexec/switch_roots to the slot). The second works without changing the bootloader,
  but only once an image is accepted by it at all - which on a locked device means Amazon's signature.
* `rossini/installer/fit.py` builds the unsigned FIT (config `conf-mt8110-cava`, <= 32 MiB) for engineering or unlocked devices.

## Kindle PW2/PW3/KV/KT2/Oasis (Lab126 3.0.35)
Bootloader not in the release. The kernel expects ATAGs (serial16, revision16 = board id, MAC, boot mode) and the default
`root=/dev/mmcblk0p1`. No devtmpfs (use mdev), squashfs zlib only. Rossini's userland for these kernels must be built against musl
(`build/buildroot/configs/rossini_lab126_defconfig`); glibc >= 2.26 aborts with "kernel too old".

## Recovery
Independent hardware recovery has to come from the device (second boot path); see docs/hardware/README.md. The QEMU recovery image demonstrates
the userland tools only.
