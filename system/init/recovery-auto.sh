#!/bin/sh
# Automatic recovery diagnosis used by tests and by the "Repair" entry: read-only checks first.
R="python3 -m rossini.recovery"
echo "ROSSINI-RECOVERY: bootctl: $(tr '\n' ' ' < /boot/bootctl)"
for s in a b; do
    dev=/dev/vd$([ $s = a ] && echo a || echo b)
    if mount -t squashfs -o ro $dev /mnt/$s 2>/dev/null; then
        if [ -f /mnt/$s/etc/rossini/manifest.sha256 ]; then
            if $R verify /mnt/$s /mnt/$s/etc/rossini/manifest.sha256 >/tmp/v.txt; then echo "ROSSINI-RECOVERY: slot $s integrity OK"; else echo "ROSSINI-RECOVERY: slot $s integrity FAILED: $(head -n 3 /tmp/v.txt | tr '\n' ';')"; fi
        fi
    else echo "ROSSINI-RECOVERY: slot $s not mountable"; fi
done
if e2fsck -n /dev/vdd >/tmp/fsck.txt 2>&1; then echo "ROSSINI-RECOVERY: data fs clean"; else echo "ROSSINI-RECOVERY: data fs problems: $(tail -n 1 /tmp/fsck.txt)"; fi
if mount -t ext4 -o ro /dev/vdd /data 2>/dev/null; then
    out=$($R export /data /tmp/export 2>&1) && echo "ROSSINI-RECOVERY: data export ok ($(find /tmp/export -type f | wc -l) files)" || echo "ROSSINI-RECOVERY: data export FAILED: $out"
fi
echo "ROSSINI-RECOVERY: done"
