# Local network video viewer

Enabled and visually verified in the laptop browser on 2026-09-29:

- Main viewer: <http://192.168.8.175:8889/fpv1/> (WebRTC).
- Fallback: <http://192.168.8.175:8888/fpv1/> (HLS; more buffering).
- HLS playlist for compatible players: <http://192.168.8.175:8888/fpv1/index.m3u8>.

Both players showed the live GT Pro camera picture and Betaflight OSD. MediaMTX logs also confirm the laptop WebRTC peer connection and H.264 reader. This is functional browser playback, not a measured camera-to-screen latency result. [MediaMTX browser player documentation](https://mediamtx.org/docs/read/web-browsers).

The Pi serves these pages through the existing `ascent-mediamtx.service`. It and `ascent-video@fpv1.service` are enabled for startup. No laptop tunnel or laptop web process is required. The Pi's address is currently DHCP; `ascent-relay.local` can be used instead on clients that support mDNS. On another subnet, update the read-access CIDR deliberately.

Applied configuration: `/etc/ascent-relay/mediamtx.yml`, from [mediamtx-lan.yml](../config/mediamtx-lan.yml). The previous configuration is backed up on the Pi at `/etc/ascent-relay/mediamtx.yml.before-lan-20260929`. The generic image configuration still defaults to loopback-only RTSP; the running Pi's saved configuration includes the LAN viewer.

LAN clients on `192.168.1.0/24` and `192.168.8.0/24` have anonymous **read** access to `fpv1` and the future `fpv2`. Publishing remains restricted to localhost, and RTSP still listens only on `127.0.0.1:8554`. Browser signalling uses TCP 8889, WebRTC media uses UDP 8189 with TCP 8189 fallback, and HLS uses TCP 8888. No router port forwarding, STUN/TURN server, public stream or control-output service was configured.

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

## Alfa address — 2026-09-29

The USB Alfa adapter was present but disconnected; activated it on the existing Wi-Fi network. Its DHCP address is now **192.168.1.105**, preferred route metric500. Onboard .104 remains connected as fallback metric600. Use `http://192.168.1.105:8888/fpv1/` for HLS or port8889 for WebRTC when reaching the Alfa. Both listeners bind the LAN interfaces; read permissions already include this subnet. These DHCP addresses may change.

Two browser consumers on onboard Wi-Fi coincided with >1s ping times and stalled SSH. Both viewers were temporarily disconnected for diagnosis; video services stayed active. The subsequent physical RC baseline used Alfa without browser consumers. Simultaneous video/control remains to be checked before drawing conclusions about stream capacity.

Subsequent coexistence check passed: one HLS viewer at the .105 address visibly showed live camera/OSD; MediaMTX confirmed its reader. With that viewer playing,200/200 authenticated synthetic control snapshots produced matching FC movement, all116 observations disarmed. Pi ping4.6–10.0ms. The HLS tab remains open; the duplicate agent-created WebRTC tab was closed. Both video services stayed active. This short test does not establish sustained or WAN performance.


## Current field network and dashboard

Both devices moved to owner-selected SSID `bbbb`: laptop 192.168.8.130 and Pi Alfa wlan1 192.168.8.175, gateway 192.168.8.1. Pinned SSH and Internet connectivity verified. Alfa profile ascent-field uses 5 GHz, autoconnect priority30, power saving disabled, route metric500. Laptop bbbb uses 5 GHz and power saving disabled. Old house profiles remain available; Pi wlan0 is still192.168.1.104/metric600. No credentials are stored in this repository.

Use the Control Room's Bench test → Open live video, or the updated URLs at the top of this page. The owner selected 1 Mbps using the new bitrate control; earlier trials used 3 Mbps. WebRTC candidate interfaces now include wlan1. Capture USB disconnected/re-enumerated repeatedly during this session; FFmpeg exited successfully and the old on-failure unit stayed stopped. The publisher now uses Restart=always so a clean capture EOF also retries. Manual stops remain stopped. Capture hardware/power stability still requires investigation if this recurs.
