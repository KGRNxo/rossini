#!/bin/busybox sh
# Rossini Recovery (QEMU dev target): a separate initramfs that carries its own userland and never mounts the
# regular system read-write. Commands arrive on the kernel command line (rossini.recovery=auto) or an
# interactive shell is offered on the console.
export PATH=/bin:/sbin:/usr/bin:/usr/sbin PYTHONPATH=/opt/rossini PYTHONDONTWRITEBYTECODE=1
/bin/busybox --install -s /bin 2>/dev/null
mount -t proc proc /proc; mount -t sysfs sys /sys; mount -t devtmpfs dev /dev
mkdir -p /boot /mnt/a /mnt/b /data /mnt/usb
echo "ROSSINI-RECOVERY: started"
mount -t ext4 -o ro /dev/vdc /boot || echo "ROSSINI-RECOVERY: boot-state unreadable"
if grep -q rossini.recovery=auto /proc/cmdline; then
    sh /opt/rossini/system/init/recovery-auto.sh
    poweroff -f
fi
exec sh
