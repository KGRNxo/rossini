# Recovery

Implemented (`rossini/recovery`, `system/init/recovery-*.sh`): integrity check of a slot against its `manifest.sha256`, read-only
`e2fsck`, restoring the previous slot in `bootctl` (refused if that slot never held a version), data export (copy + size check), factory reset that
needs the literal confirmation token `ERASE-USER-DATA`.

QEMU: `qemu ... -initrd build/out/recovery.cpio.gz -append "rossini.recovery=auto"` boots the separate recovery userland and runs the checks
(covered by `tests/qemu/test_qemu.py`). Automatic recovery is also built into the update flow: an update that does not pass the boot self-test is
rolled back after three attempts.

Not available: a recovery that is reachable when the regular boot chain is dead on real hardware. On a Kindle that requires an independent boot
path, which is unknown for KT6. Restoring original Kindle firmware is not implemented (no verified, legally reviewed procedure).

Manual use on any machine: `python3 -m rossini.recovery verify|fsck|restore|export|reset ...`.
