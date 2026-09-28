#!/usr/bin/env bash
set -euo pipefail
export DEBIAN_FRONTEND=noninteractive
install -d -m 755 /var/lib/ascent-relay
# Packages are bundled from signed repositories and checked before installation.
bash /boot/firmware/ascent/install-from-boot.sh
# One explicit labelled test stream boots automatically. Physical RC never does.
systemctl enable --now ascent-mediamtx.service ascent-video@fpv1.service
systemctl is-active --quiet ascent-mediamtx.service
systemctl is-active --quiet ascent-video@fpv1.service
sleep 3
timeout 20 ffprobe -v error -rtsp_transport tcp -show_entries stream=codec_name,width,height -of json \
  rtsp://127.0.0.1:8554/fpv1 >/var/lib/ascent-relay/firstboot-video.json
python3 - <<'PY'
import json
with open('/var/lib/ascent-relay/firstboot-video.json') as f:
    info = json.load(f)
assert any(s.get('codec_name') == 'h264' for s in info.get('streams', [])), 'No H.264 bench stream'
PY
date -u +%FT%TZ >/var/lib/ascent-relay/provisioned
echo 'Ascent provisioning finished. SSH and synthetic video ready; physical capture/control remain unverified.'
