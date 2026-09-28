#!/usr/bin/env bash
set -euo pipefail
[[ $(id -u) == 0 ]] || { echo 'Run with sudo on the Pi.' >&2; exit 1; }
root=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
(cd "$root" && sha256sum --check ascent-relay-bundle.tar.gz.sha256)
temp_dir=$(mktemp -d)
trap 'rm -rf -- "$temp_dir"' EXIT
tar -xzf "$root/ascent-relay-bundle.tar.gz" -C "$temp_dir" --no-same-owner
bash "$temp_dir/ascent-relay/scripts/install-pi.sh"
