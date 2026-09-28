#!/usr/bin/env bash
# Read-only enumeration; does not capture video or open a serial port.
set -u
printf 'Hardware model: '
if [[ -r /proc/device-tree/model ]]; then tr -d '\0' </proc/device-tree/model; fi
printf '\nOperating system:\n'
cat /etc/os-release
uname -m
for utility in lsusb v4l2-ctl ffmpeg; do
  if ! command -v "$utility" >/dev/null; then printf 'Missing: %s\n' "$utility"; fi
done
command -v lsusb >/dev/null && lsusb
command -v lsusb >/dev/null && lsusb -t
if command -v v4l2-ctl >/dev/null; then
  v4l2-ctl --list-devices
  for node in /dev/video*; do
    [[ -e "$node" ]] || continue
    printf '\nVideo node %s\n' "$node"
    v4l2-ctl -d "$node" --list-formats-ext || true
  done
fi
for directory in /dev/v4l/by-id /dev/v4l/by-path /dev/input/by-id /dev/serial/by-id; do
  [[ ! -d "$directory" ]] || ls -l "$directory"
done
if command -v ffmpeg >/dev/null; then
  ffmpeg -hide_banner -encoders 2>/dev/null | rg '264|265' || true
fi
if command -v vcgencmd >/dev/null; then
  vcgencmd get_throttled
  vcgencmd measure_temp
fi
