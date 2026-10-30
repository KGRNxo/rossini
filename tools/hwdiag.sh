#!/bin/sh
# Rossini hardware diagnosis. Runs on any Linux device with a POSIX shell (busybox is enough) and
# writes a plain-text facts bundle. Read-only. These values are the ONLY acceptable source for filling in
# a boards/<id>/profile.json.   Usage: hwdiag.sh [output-file]
out="${1:-rossini-hwdiag-$(date +%Y%m%d-%H%M%S).txt}"
sect() { printf '\n=== %s ===\n' "$1"; }
cat_f() { for f in "$@"; do [ -r "$f" ] && { printf -- '--- %s\n' "$f"; head -c 4096 "$f" 2>/dev/null | tr '\0' '\n'; echo; }; done; }
{
  echo "rossini-hwdiag 1"
  sect uname;        uname -a
  sect cpu;          cat_f /proc/cpuinfo
  sect devicetree;   cat_f /proc/device-tree/model /proc/device-tree/compatible
  sect cmdline;      cat_f /proc/cmdline /proc/version
  sect memory;       head -n 3 /proc/meminfo 2>/dev/null
  sect mtd;          cat_f /proc/mtd
  sect partitions;   cat_f /proc/partitions
  sect mounts;       cat_f /proc/mounts
  sect block;        for b in /sys/block/*; do [ -e "$b" ] && echo "$(basename "$b") size=$(cat "$b/size" 2>/dev/null) ro=$(cat "$b/ro" 2>/dev/null)"; done
  sect framebuffer;  cat_f /sys/class/graphics/fb0/name /sys/class/graphics/fb0/virtual_size /sys/class/graphics/fb0/bits_per_pixel /sys/class/graphics/fb0/stride
  sect backlight;    for d in /sys/class/backlight/* /sys/class/leds/*; do [ -e "$d" ] && { echo "$d"; cat_f "$d/max_brightness" "$d/brightness"; }; done
  sect power_supply; for d in /sys/class/power_supply/*; do [ -e "$d" ] && { echo "$d"; cat_f "$d/type" "$d/status" "$d/capacity" "$d/technology"; }; done
  sect input;        cat_f /proc/bus/input/devices
  sect network;      for d in /sys/class/net/*; do [ -e "$d" ] && echo "$(basename "$d") $(cat "$d/address" 2>/dev/null | sed 's/\(..:..:..\):.*/\1:xx:xx:xx/')"; done
  sect usb_gadget;   ls /sys/class/udc /sys/kernel/config/usb_gadget 2>/dev/null
  sect suspend;      cat_f /sys/power/state /sys/power/wakeup_count
  sect lab126;       cat_f /proc/board_id /proc/idme/board_id /proc/panel_id /proc/bootmode /proc/postmode; for f in /proc/usid; do [ -r "$f" ] && { printf -- '--- %s (first 4 chars only)\n' "$f"; head -c 4 "$f"; echo; }; done
  sect modules;      cat_f /proc/modules
  sect release;      cat_f /etc/os-release /etc/version /system/version.txt
} > "$out" 2>&1
echo "$out"
