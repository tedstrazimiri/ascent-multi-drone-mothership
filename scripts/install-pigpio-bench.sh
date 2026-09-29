#!/usr/bin/env bash
# Optional Pi 4 bench dependency. No daemon, service, pin writes, or RC startup.
set -euo pipefail
if ! tr -d '\0' </proc/device-tree/model | grep -q 'Raspberry Pi 4 Model B'; then
    echo 'Run on the bench Pi 4.' >&2
    exit 1
fi
revision=c33738a320a3e28824af7807edafda440952c05d
digest=805c34565986102adb0b10782ad4e6917815bf1369fb4e364f157c9f06e5cbc5
build_dir=$(mktemp -d -t ascent-pigpio.XXXXXXXX)
trap 'rm -rf -- "$build_dir"' EXIT
if [[ $# -eq 1 ]]; then
    cp -- "$1" "$build_dir/source.tar.gz"
else
    curl --fail --location --proto '=https' --tlsv1.2 \
        "https://codeload.github.com/joan2937/pigpio/tar.gz/$revision" \
        -o "$build_dir/source.tar.gz"
fi
printf '%s  %s\n' "$digest" "$build_dir/source.tar.gz" | sha256sum --check --status
tar -xzf "$build_dir/source.tar.gz" --strip-components=1 -C "$build_dir"
make -C "$build_dir" -j2 libpigpio.so
sudo install -d -m 755 /opt/ascent-relay/vendor/pigpio
sudo install -m 644 "$build_dir/libpigpio.so.1" /opt/ascent-relay/vendor/pigpio/libpigpio.so.1
sudo install -m 644 "$build_dir/UNLICENCE" /opt/ascent-relay/vendor/pigpio/UNLICENCE
printf 'commit=%s\narchive_sha256=%s\n' "$revision" "$digest" >"$build_dir/SOURCE"
sudo install -m 644 "$build_dir/SOURCE" /opt/ascent-relay/vendor/pigpio/SOURCE
echo 'Installed private pigpio library only; no GPIO output started.'
