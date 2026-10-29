#!/bin/sh
# Boot-slot chooser (bootloader stand-in for the QEMU target). Same logic as
# rossini/updater/bootctl.py BootCtl.choose(); prints the slot to boot, updates the state file.
# Usage: bootctl-choose.sh /path/to/bootctl
f="$1"
get() { sed -n "s/^$1=//p" "$f" | head -n1; }
confirmed=$(get confirmed); trial=$(get trial); tries=$(get tries)
[ -n "$confirmed" ] || confirmed=A
[ -n "$tries" ] || tries=0
put() { # key value
    if grep -q "^$1=" "$f" 2>/dev/null; then sed "s/^$1=.*/$1=$2/" "$f" > "$f.tmp"; else cp "$f" "$f.tmp"; echo "$1=$2" >> "$f.tmp"; fi
    sync; mv "$f.tmp" "$f"
}
if [ -n "$trial" ] && [ "$tries" -gt 0 ]; then
    put tries $((tries - 1))
    echo "$trial"
else
    if [ -n "$trial" ]; then put trial ""; put tries 0; fi
    echo "$confirmed"
fi
