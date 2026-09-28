#!/usr/bin/env bash
# Run on a booted Pi 4B. Leaves services stopped/disabled on first install.
set -euo pipefail
[[ $(id -u) == 0 ]] || { echo 'Run with sudo on the Raspberry Pi.' >&2; exit 1; }
[[ $(uname -m) == aarch64 ]] || { echo 'Requires 64-bit Raspberry Pi OS; refusing this host.' >&2; exit 1; }
[[ -r /proc/device-tree/model ]] && model=$(tr -d '\0' </proc/device-tree/model)
[[ ${model:-} == *'Raspberry Pi 4 Model B'* ]] || { echo 'Pi 4B model not detected; refusing this host.' >&2; exit 1; }
source /etc/os-release
[[ ${VERSION_CODENAME:-} == trixie ]] || { echo 'Prepared for Raspberry Pi OS Trixie.' >&2; exit 1; }
root=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)
target=/opt/ascent-relay
[[ ! -d "$target" || -f "$target/.managed-by-ascent-relay" ]] || { echo 'Existing unmanaged /opt/ascent-relay; stopping.' >&2; exit 1; }
archive="$root/.cache/mediamtx_v1.21.1_linux_arm64.tar.gz"
[[ -f "$archive" ]] || { echo 'Run scripts/fetch.py mediamtx-arm64 before packaging.' >&2; exit 1; }
printf '%s  %s\n' '6a3aa635fb60ea9b8d566ec306f0a42ff1b6b52a3942bc2baffbe55880d4c3dd' "$archive" | sha256sum --check --status
if [[ -f "$root/.cache/debs/SHA256SUMS" ]]; then
  (cd "$root/.cache/debs" && sha256sum --check --status SHA256SUMS)
  printf 'iperf3 iperf3/start_daemon boolean false\n' | debconf-set-selections
  DEBIAN_FRONTEND=noninteractive dpkg --force-confdef --force-confold -i "$root"/.cache/debs/*.deb
else
  apt-get update
  apt-get install -y --no-install-recommends python3 ffmpeg v4l-utils usbutils iperf3 wireguard-tools ripgrep
fi
getent group ascent-relay >/dev/null || groupadd --system ascent-relay
id ascent-relay >/dev/null 2>&1 || useradd --system --gid ascent-relay --no-create-home --shell /usr/sbin/nologin ascent-relay
install -d -m 755 "$target" "$target/bin" "$target/scripts" /etc/ascent-relay
touch "$target/.managed-by-ascent-relay"
cp -r "$root/relay" "$target/"
install -m 755 "$root/scripts/probe.sh" "$target/scripts/probe.sh"
find "$target/relay" -type d -name __pycache__ -exec rm -r -- {} +
tar -xzf "$archive" -C "$target/bin" mediamtx LICENSE
chmod 755 "$target/bin/mediamtx"
for file in mediamtx.yml video-fpv1.json video-fpv2.json joystick.example.json; do
  if [[ ! -e /etc/ascent-relay/$file ]]; then
    install -m 644 "$root/config/$file" "/etc/ascent-relay/$file"
  fi
done
for source_file in "$root"/systemd/*.service; do
  dest="/etc/systemd/system/$(basename "$source_file")"
  if [[ -f "$dest" ]] && ! cmp -s "$source_file" "$dest"; then
    cp -a "$dest" "$dest.before-ascent-$(date -u +%Y%m%dT%H%M%SZ)"
  fi
  install -m 644 "$source_file" "$dest"
done
systemctl daemon-reload
echo 'Installed. Existing configuration preserved. No services enabled, restarted, or started.'
echo 'Read docs/BRINGUP.md; default video sources are SYNTHETIC.'
