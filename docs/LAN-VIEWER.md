# Local network video viewer

Enabled and visually verified in the laptop browser on 2026-09-29:

- Main viewer: <http://192.168.1.104:8889/fpv1/> (WebRTC).
- Fallback: <http://192.168.1.104:8888/fpv1/> (HLS; more buffering).
- HLS playlist for compatible players: <http://192.168.1.104:8888/fpv1/index.m3u8>.

Both players showed the live GT Pro camera picture and Betaflight OSD. MediaMTX logs also confirm the laptop WebRTC peer connection and H.264 reader. This is functional browser playback, not a measured camera-to-screen latency result. [MediaMTX browser player documentation](https://mediamtx.org/docs/read/web-browsers).

The Pi serves these pages through the existing `ascent-mediamtx.service`. It and `ascent-video@fpv1.service` are enabled for startup. No laptop tunnel or laptop web process is required. The Pi's address is currently DHCP; `ascent-relay.local` can be used instead on clients that support mDNS. On another subnet, update the read-access CIDR deliberately.

Applied configuration: `/etc/ascent-relay/mediamtx.yml`, from [mediamtx-lan.yml](../config/mediamtx-lan.yml). The previous configuration is backed up on the Pi at `/etc/ascent-relay/mediamtx.yml.before-lan-20260929`. The generic image configuration still defaults to loopback-only RTSP; the running Pi's saved configuration includes the LAN viewer.

LAN clients on `192.168.1.0/24` have anonymous **read** access to `fpv1` and the future `fpv2`. Publishing remains restricted to localhost, and RTSP still listens only on `127.0.0.1:8554`. Browser signalling uses TCP 8889, WebRTC media uses UDP 8189 with TCP 8189 fallback, and HLS uses TCP 8888. No router port forwarding, STUN/TURN server, public stream or control-output service was configured.

To apply this saved profile again after copying it to the Pi:

```bash
sudo cp -a /etc/ascent-relay/mediamtx.yml /etc/ascent-relay/mediamtx.yml.before-viewer-$(date -u +%Y%m%dT%H%M%SZ)
sudo install -m 644 /path/to/mediamtx-lan.yml /etc/ascent-relay/mediamtx.yml
sudo systemctl restart ascent-mediamtx.service
systemctl is-active ascent-mediamtx.service ascent-video@fpv1.service
```

Restoring the backed-up configuration and restarting MediaMTX removes LAN playback. A restart briefly interrupts video and the enabled publisher reconnects automatically.

## Address troubleshooting

The bare WebRTC root (`http://192.168.1.104:8889/`) returns 404 because MediaMTX has no homepage there. Include `/fpv1/`; `/fpv1` also redirects correctly. On 2026-09-29, following an owner-reported 404, both full WebRTC and HLS URLs returned HTTP 200 and visibly played the camera/OSD in the laptop browser. Both Pi services remained active. The exact failing device/address was requested; no server outage or required restart was established. Private HTTP check evidence: `work/lan-viewer-404-check.json`.
