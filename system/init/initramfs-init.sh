#!/bin/busybox sh
# Stage 1 (QEMU dev target): bootloader stand-in. Chooses the A/B slot with bootctl-choose.sh,
# mounts the selected squashfs root plus boot-state and data partitions, then hands over to Rossini's init.
# On real hardware this logic belongs to the bootloader (see docs/architecture/boot-chain.md).
export PATH=/bin:/sbin
/bin/busybox --install -s /bin 2>/dev/null
mount -t proc proc /proc; mount -t sysfs sys /sys; mount -t devtmpfs dev /dev
say() { echo "ROSSINI-INITRAMFS: $*"; }
die() { say "FATAL: $*"; sync; sleep 1; poweroff -f; }
dev_of() { [ "$1" = A ] && echo /dev/vda || echo /dev/vdb; }

mkdir -p /boot /newroot /data
mount -t ext4 /dev/vdc /boot || die "boot-state partition unusable"
slot=$(sh /bin/bootctl-choose.sh /boot/bootctl)
confirmed=$(sed -n 's/^confirmed=//p' /boot/bootctl)
say "chooser picked slot $slot (confirmed: $confirmed)"
if ! mount -t squashfs -o ro "$(dev_of "$slot")" /newroot 2>/dev/null; then
    say "slot $slot does not mount"
    [ "$slot" != "$confirmed" ] || die "confirmed slot $confirmed does not mount"
    # a trial slot that cannot even mount is failed: drop the trial so the confirmed slot boots from now on
    sed -i 's/^trial=.*/trial=/; s/^tries=.*/tries=0/' /boot/bootctl; sync
    slot=$confirmed
    mount -t squashfs -o ro "$(dev_of "$slot")" /newroot || die "confirmed slot $slot does not mount"
fi
if mount -t ext4 /dev/vdd /data; then :; else say "data partition unusable, running on tmpfs"; mount -t tmpfs data /data; fi
mount -t tmpfs -o mode=755 run /newroot/run; mount -t tmpfs -o mode=1777 tmp /newroot/tmp
for m in proc sys dev boot data; do mkdir -p /newroot/$m; mount --move /$m /newroot/$m; done
say "switching root to slot $slot"
ROSSINI_SLOT=$slot exec switch_root /newroot /sbin/init
