# Project handoff — 2026-09-29

**Status: latency sprint active (resumed 2026-09-29).** Read [current sprint measurements](LATENCY-SPRINT-2026-09-29.md) first. Pi/VRX video has been rechecked; TX15, FC and GT Pro/camera are off/disconnected for this sprint. The console now measures WebRTC receive timing and offers a reversible minimum-buffer trial. USB capture reconnects and Wi-Fi authentication failures currently prevent a stable full-path comparison. No physical RC output or FC setting change was performed.

The Pi's attached text-monitor timer is prepared at `/home/ted/ascent-latency/latency-clock.py`. Next: establish stable capture/Wi-Fi, then point the powered FPV camera at the timer and record the original and dashboard image together. Automatic playout buffering remains selected; the minimum-delay trial froze frequently.

This page is the current project summary. [VERIFICATION.md](VERIFICATION.md) preserves chronological evidence, including earlier failures and subsequently resolved blockers. “Verified” below means the stated test passed, not qualification for flight.

## Objective and scope

Relay video and ground-pilot RC from one small FPV through a mothership carrying an Ascent Industry VRX and Pi 4B; later expand to two independent FPVs. The application is civilian wildfire-suppression experimentation. The current implementation is on the bench.

Implemented: HDMI video capture and browser playback, USB-HID TX15 calibration, authenticated LAN channel transport, timed SBUS output, FC feedback over local USB, finite disarmed tests, and an explicit two-second idle-throttle arming test. The graphical dashboard is the normal setup tool.

Not implemented: mothership flight/launch integration, suppression payload actuation, Starlink or other WAN backhaul, VPN deployment, remote bidirectional FC telemetry, integrated Mission Planner/Kite control, a separate hardware output watchdog, full piloting with ARM plus live sticks, or simultaneous operation of two FPVs. `fpv2` configuration and synthetic tests are scaffolding only.

## Previous-session observed state

Read from the local dashboard API at **2026-09-29 08:50 EDT** during documentation preparation. These are time-bound observations, not a promise that devices remain connected after the session.

| Item | Observed state |
|---|---|
| Control | Session stopped; no active dashboard RC run; background job idle |
| FC | Connected over USB, Betaflight `26.6.2`, SBUS present, disarmed |
| FC blockers | `RX_FAILSAFE`, consistent with no active bench channel stream |
| Indoor profile | Ready; allow arming without GPS fix; DROP failsafe in RAM |
| Battery report | 21.39 V, FC detected 5 cells; older logs recorded 6 cells, so confirm actual pack configuration later |
| Radio | RadioMaster TX15 HID connected; enable condition false |
| Video | Source available; saved player WebRTC; requested bitrate 1 Mbps |
| Pi | Saved field address `192.168.8.175`; connected flag came from an earlier check, not a fresh SSH audit in this closeout |

The API retained a completed 250-frame arm-session record. It was not a new test performed by the latency audit or documentation closeout. The indoor RAM profile was left as found; no restore or power-cycle was performed. Motor beeping investigation remains stopped at the owner's request.

## Equipment and identity

The shared [hardware registry](</home/ted/Documents/ChatGPT/Hardware Inventory/INVENTORY.md>) remains canonical. A narrow project query at closeout found six existing allocations, HW-0021 through HW-0026. No allocation was added or released when pausing this session.

| Equipment | Established facts and limits |
|---|---|
| Raspberry Pi | Running board: Pi 4 Model B Rev 1.2, 2 GB, Raspberry Pi OS Lite Trixie 64-bit. Which member of the original inventoried two-Pi batch remains unresolved; do not add another Pi count. |
| Industry VRX, HW-0021 | Owner identifies this as standard Ascent VRX hardware. The Rockchip-based VRX Pro is a different revision. Actual running Ascent firmware version is not confirmed. |
| Ascent GT Pro, HW-0022 | Bound FPV VTX; camera/OSD and separate SBUS transport passed. |
| HDMI USB capture, HW-0023 | MacroSilicon `534d:2109`, `uvcvideo`, USB 480 Mbps. Retail model unknown; no unique USB serial. |
| Reference controller, HW-0024 | User selected **TX15** for the tool; USB identifies OpenTX TX15, `1209:4f54`, 8 axes/24 buttons. Earlier owner identification was GX15; the inventory preserves that history. |
| FC, HW-0025 | GEPRC TAKER H7 digital-VTX connector; actual target `GEPRC_TAKER_H743`, Betaflight 2026.6.2 with SBUS. |
| Alfa Wi-Fi, HW-0026 | `0bda:8812`, RTL8812AU, `rtw88_8812au`; Pi `wlan1`. |
| Field router | Owner-selected SSID `bbbb`, gateway `192.168.8.1`; model not independently identified in this project. |
| Battery / ESC | Owner identifies a Li-ion pack. Actual pack configuration should be confirmed against the changing FC cell reports. ESC model/firmware unresolved; no ESC configuration was changed. |

## Actual wiring and data paths

**RC:** TX15 USB HID → laptop mapper → authenticated UDP → Pi GPIO14 → VRX dedicated SBUS input → Ascent RF → GT Pro dedicated SBUS lead → FC RX2/UART2.

**Video:** camera → GT Pro → Ascent RF → VRX HDMI OUT → MacroSilicon USB capture → Pi MJPEG decode / hardware H.264 encode → local RTSP → MediaMTX WebRTC → laptop dashboard.

**Feedback:** FC USB → laptop read-only MSP monitoring. The GT Pro UART1 pair carries MSP DisplayPort/OSD; this is not evidence of a general remote telemetry bridge.

| Connection | Current role |
|---|---|
| Pi **physical pin 8 / BCM GPIO14** → VRX **SBUS** | Inverted 100000-baud 8E2, generated as timed one-shot frames. This supersedes pin 8 → VRX RX UART experiments. |
| Pi GND, e.g. physical pin 6 ↔ VRX G/GND | Shared ground confirmed by owner. |
| VRX harness 5 V | Kept separate from Pi GPIO signals; not the data connection. |
| Pi physical pin 10 / GPIO15 | Not required by the working RC path. A VRX TX connection was discussed/used earlier; present attachment is not reconfirmed. |
| GT Pro SBUS → FC RX2/R2 | Separate conductor in the six-pin digital-VTX harness; Serial RX on UART2. |
| GT Pro TX → FC RX1; GT Pro RX ← FC TX1 | UART1 MSP + DisplayPort for OSD. |
| GT Pro power and grounds | Supplied through the existing FC digital-VTX harness. Connector functions and vendor diagrams: [FC wiring](FC-WIRING.md). |
| VRX HDMI → capture; capture USB → Pi | Required video input path. Pi HDMI ports cannot ingest video. |

Owner-reported VRX labels are `SBUS, 5V, RX, TX, G, G`; this is not a mating-face pin-order diagram. Signal voltages have not been measured; owner declined that measurement. Successful reception does not establish input tolerance/electrical margins. Do not silently repurpose the SBUS lead as ordinary UART.

VRX UART menu was reported as **ELRS TT**. Four CRSF-over-UART tests at 115200, 400000, 416666 and 420000 baud did not move FC channels. The dedicated SBUS path works without relying on undocumented UART-to-SBUS translation. This result does not prove all UART modes are unusable.

## Network and service map

| Service/path | Location and behavior |
|---|---|
| Dashboard | `http://127.0.0.1:8767/#live`; laptop user service `ascent-console.service`, loopback only |
| Laptop field Wi-Fi | Last `192.168.8.130`, DHCP, 5 GHz, power saving disabled |
| Pi field Wi-Fi | Alfa `wlan1`, last `192.168.8.175`, DHCP; `ascent-field`, autoconnect, route metric 500, 5 GHz, power saving disabled |
| Pi house fallback | Onboard `wlan0`, last `192.168.1.104`, route metric 600; older Alfa `.105` address is historical |
| SSH | Alias `ascent-pi`, user `ted`, dedicated local identity and pinned `ascent-relay.local` host key |
| Video publisher | `ascent-video@fpv1.service`; `/etc/ascent-relay/video-fpv1.json` |
| MediaMTX | `ascent-mediamtx.service`; `/etc/ascent-relay/mediamtx.yml`; version 1.21.1 |
| RTSP | Pi `127.0.0.1:8554/fpv1`, local only; SSH tunnel if a laptop RTSP client is needed |
| WebRTC | `http://192.168.8.175:8889/fpv1/`; media UDP 8189, TCP 8189 fallback |
| HLS | `http://192.168.8.175:8888/fpv1/`; playlist `/fpv1/index.m3u8` |
| Physical control | Finite UDP receivers: 14601 LINK/STICKS, 14602 ARM; no persistent RC service |
| JSON-only diagnostic | `relay.bench receiver`, default UDP 14600; no GPIO/UART output |

The Pi video services are enabled at boot. The laptop launcher starts the dashboard; login autostart is not enabled. Responsive phone layout does not expose the control dashboard to a phone on the LAN. Video reads are allowed from `192.168.1.0/24` and `192.168.8.0/24`; publishing is localhost-only. No public forwarding, VPN or WAN relay was configured. Wi-Fi credentials remain in private OS profiles and are not copied into this repository.

Current capture is MJPEG **1280×720 at 30 fps**, hardware encoder `h264_v4l2m2m`, requested **1 Mbps**, GOP 30, no B-frames. Stable single-adapter path: `/dev/v4l/by-id/usb-MACROSILICON_USB_Video-video-index0`. A second identical adapter needs unambiguous physical USB paths. Capture advertises MJPEG 720p60; unique 60 fps and sustained encoding at that rate have not been tested.

## Control mapping and boundaries

| Function | Mapping |
|---|---|
| Roll / pitch / throttle / yaw | USB axes 0 / 1 / 2 / 3; observed endpoints −32767 to +32767, no inversion |
| SA | USB axis 5; low −32767, middle 0, high +32767; saved high selection 16000–32767 |
| SBUS scale | Low 172, centre 992, high 1811 |
| FC mapping | AETR1234; ARM AUX1 range 1700–2100 |
| MSP readback order | Roll, pitch, yaw, throttle; dashboard reorders its presentation |

“SA high” means the highest reported channel value and the owner's intended third/arm position; physical up/down alone is not a universal definition. The graphical calibration walks through each control without transmitting and saves only on completion.

| Dashboard mode | Output and interlocks |
|---|---|
| LINK | Four-second synthetic roll movement; throttle and every AUX low; FC USB disarmed/SBUS check required. |
| STICKS | 30/60/90-second live primary-channel test; every AUX low. Low throttle and SA high to start; SA release stops. FC USB required. |
| ARM | Fixed centred roll/pitch/yaw and minimum throttle; only AUX1 varies. Start prepares dependencies, waits for throttle down and SA low, then requires a fresh SA-high edge. ARM-high is bounded to about two seconds; ten disarm frames are attempted on receiver exit. No free-flight stick authority. |

ARM permits a 90-second preparation/input wait and a 60-second output/test window; two seconds is the ARM-high limit. Early SA high remains inhibited until SA returns low. Receiver independently requires low frames before high and does not rearm in the same run. Repeat by **Start again**; no reboot is needed.

Transport uses HMAC authentication, receiver-issued freshness challenges (150 ms), increasing sequences, and one operator per run. Accepted-control loss for 250 ms latches stop. Dashboard absence stops its sender after three seconds. These limits were not loosened to hide latency. The protocol authenticates but does not encrypt; Internet use needs a private authenticated network and additional validation.

Pi output uses the private pigpio 79 library, without a daemon, network listener or endlessly repeating waveform. A 25-byte SBUS frame takes 3 ms. Normal cleanup returns GPIO14 to input/pull-down. Boot configuration selects PL011 ALT0 on pins 8/10, so the cleanup pin state must not be assumed to persist across reboot. Linux scheduling and independent hardware failure containment remain unqualified for flight.

## FC saved configuration versus indoor RAM profile

Saved configuration: Betaflight 2026.6.2 / MSP 1.48; UART1 MSP + DisplayPort at 115200, UART2 Serial RX/SBUS, UART4 UBLOX GPS at 57600. Standard SBUS rate, `serialrx_inverted=OFF`, half-duplex off. The SBUS driver supplies normal protocol inversion. GPS remains enabled; the M10 has no fix indoors.

At the owner's request, the old 4.5.1 tune was migrated: profile 0's 105 retained-name settings and all four rate profiles matched their backup after save/readback. Renamed D-min/D-max, dynamic idle and GPS Rescue settings were reviewed separately. The migration is a starting tune, not proof of identical flight response. Exact settings, caveats and backups: [FC setup](FC-2026-SETUP.md).

Saved battery minimum is **3.20 V/cell** in active profile 0; warning remains **3.50 V/cell**. FC buzzer events and RX motor-beacon triggers were muted at the owner's request. ESC configuration was not changed. Intended audible warnings, pack configuration, motor direction and board orientation need review before flight evaluation.

The **temporary indoor profile** backs up the original failsafe and GPS Rescue MSP payloads, enables arming without a GPS fix, then selects DROP failsafe and reads both back. It does not write EEPROM, alter the tune, or send MSP motor commands. The saved GPS-Rescue policy remains in flash.

Use **Link → Indoor profile → Restore flight settings** with FC USB connected to restore both payloads live. Keep the private backup until restoration succeeds. Console restarts retain verified preparation and USB reconnection checks actual values. FC power loss reloads saved settings; reconnect FC USB for preparation on the next attempt. Do not save unrelated Betaflight changes to flash while the temporary indoor profile is active; restore first.

## Restart and recovery reference

For normal use, open the app launcher or `http://127.0.0.1:8767/#live`. Follow the graphical setup; no terminal-driven arm test is required. These are reference steps for the next session, not actions performed during closeout.

1. Connect laptop and Pi to field Wi-Fi `bbbb`; verify the Pi address in **Link** and run **Check**. DHCP may assign a new address.
2. Use one WebRTC viewer; reconnect the player if needed. “Stream available” is a source check, not proof of decoded/current frames. Observe camera movement to confirm live playback.
3. Connect the TX15 in USB joystick mode. Use the saved calibration or the graphical wizard if the radio model/output mapping changed.
4. For a requested physical bench test, keep props removed. **Start arm test** prepares the relay key automatically; first indoor setup or an FC power-cycle requires FC USB. Follow the SA/throttle prompt. STICKS/LINK need actual USB feedback.
5. Stop ends the finite run. Restore the indoor profile over USB when leaving bench configuration. If using Betaflight Configurator, first **Release FC USB** in the dashboard; reconnect it in the dashboard afterward.

| Symptom | Existing recovery path |
|---|---|
| Pi reboot / relay key missing | **Prepare relay**, or ARM Start's automatic preparation; `/run/ascent-sbus-bench.key` is volatile. This does not itself transmit RC. |
| FC reboot / GPS blocker returns | Connect FC USB and prepare the indoor profile again; ordinary repeats do not need a reboot. |
| FC USB unplugged | Armed/channel feedback becomes unknown; reconnect the stable device. Reader now recovers from termios disconnect errors and rejects stale telemetry. |
| Web player 404 | Include `/fpv1/` and the correct Pi address; bare MediaMTX root is not a homepage. |
| Capture lost / colour bars / no transmitter | Check HDMI/source/USB connection and pairing first. The publisher retries on clean EOF and errors (`Restart=always`); underlying USB interruption cause is unresolved. |
| Dashboard unavailable | `systemctl --user start ascent-console.service`; inspect its journal if it fails. Reinstall launcher/service only if needed. |
| No input in STICKS | It requires low throttle and saved SA-high enable before starting; every AUX intentionally remains low. |
| ARM does not start while FC USB is plugged in | Read actual blockers; USB/MSP arming inhibition is separate from GPS. Unplug USB only after indoor preparation, keep the FC powered, and observe motors/OSD for the deliberate bench test. |

Read-only laptop diagnostics:

```bash
systemctl --user status ascent-console.service --no-pager
journalctl --user -u ascent-console.service -n 60 --no-pager
```

Read-only Pi service check, using the existing pinned identity and explicit last field address:

```bash
ssh -o ControlPath=none -o BatchMode=yes -o ConnectTimeout=5 \
  -o HostName=192.168.8.175 -o HostKeyAlias=ascent-relay.local ascent-pi \
  'systemctl is-active ascent-mediamtx.service ascent-video@fpv1.service'
```

Use the FC's stable `/dev/serial/by-id/usb-Betaflight_Betaflight_-_GEPRC_TAKER_H743_335A33643333-if00` path. Do not substitute an arbitrary `ttyACM0`; this laptop also has an unrelated u-blox serial device. The radio alias is `/dev/input/by-id/usb-OpenTX_TX15_Joystick_200364500000-joystick` (the joystick node, not `event-joystick`).

## Software and reproducibility map

Repository: `/home/ted/Documents/ChatGPT/ASCENT MULTI DRONE MOTHERSHIP`, branch `codex/ascent-relay-bench`. The completed dashboard implementation checkpoint is `e6dcf3e`; the recorded latency audit is `400dbc6`. This handoff follows those commits and changes documentation only.

| Files | Responsibility |
|---|---|
| `relay/console.py`, `web/` | Loopback dashboard, tasks, source availability, calibration and recovery |
| `relay/fc.py` | MSP readback and explicit RAM-profile preparation/restore; no motor/EEPROM command path |
| `relay/joystick.py`, `relay/protocol.py`, `relay/bench.py` | HID, channel packing/authentication/freshness, sender and JSON-only diagnostic receiver |
| `relay/sbus_bench.py`, `relay/sbus_probe.py` | Finite physical SBUS receiver and synthetic waveform probe |
| `relay/arm_test.py` | Separate constrained SA arm-test sender/receiver |
| `relay/crsf_probe.py` | Historical finite CRSF UART diagnostic; not the working route |
| `relay/video.py`, `config/mediamtx-lan.yml` | Capture/encoding and LAN video-serving configuration |
| `relay/ascent.py` | Offline management-packet codec; does not transmit or update firmware |
| `scripts/install-console.py`, `scripts/open-console.py` | Laptop service/launcher installation and opening |
| `scripts/preview-console.py` | Isolated simulated UI on port 8768; no hardware imports or persisted changes |
| Image/install scripts and `systemd/` | Pinned downloads, image preparation, guarded flash, first boot and Pi services |
| `tests/` | Protocol, waveform, receiver constraints, profile/USB recovery and source-probe checks |

Live Pi source is `/opt/ascent-relay/relay`; video configuration is under `/etc/ascent-relay`. The private pigpio library is `/opt/ascent-relay/vendor/pigpio/libpigpio.so.1`. Image creation and pigpio installation are separate steps. See [image recovery and drift](IMAGE.md#live-bench-differences-and-recovery) before rebuilding: the original staged image is not a current full backup.

Private recovery material remains on this laptop, ignored by Git:

| Path | Contents / caution |
|---|---|
| `local-console.json` | Saved Pi address, player/bitrate preferences and calibration |
| `work/console/` | Control key, trial evidence and original `fc-failsafe-before-arm.json` payloads; keep originals for restore |
| `work/fc-backup-20260929T032146Z/` | Original complete 4.5.1 configuration and hashes; do not use `dump-all.partial.txt` |
| `work/fc-postflash-backup-20260929T033756Z/` | 2026.6.2 baseline before setup |
| `work/fc-2026-configured-backup/` | Saved migrated tune/configuration; predates later mute/minimum changes |
| `work/fc-bench-muted-backup-20260929T041655Z/` | Later complete muted configuration; predates 3.20 V minimum |
| `work/fc-lion-minimum-*`, `work/fc-lion-minimum-verify-*` | Accepted battery-minimum change and readback |
| `dist/`, `.cache/`, image manifests under `work/` | Pinned assets, personalized image and build/write evidence; images contain private credentials/keys |

No single old FC dump captures every later bench change. Restore procedures must account for these dates and current firmware rather than blindly applying the oldest backup. Git alone does not contain private keys, current device state, personalized images or trial logs.

## Verification summary

| Check | Evidence/result |
|---|---|
| SD and first boot | Full image-length write/readback matched; SSH, unattended install and video startup passed. One non-blocking cloud-init missing-module warning remains documented. |
| Physical SBUS | 195 frames; 74 FC samples all disarmed; roll alternated 1390/1610. `work/fc-sbus-trial-20260929T042729Z.json` |
| LAN control with video | 200/200 synthetic frames while HLS played; 116 FC samples all disarmed. `work/fc-network-sbus-20260929T045809Z.json` |
| Live TX15 sticks | 1,803 accepted frames, 1,689 FC samples all disarmed, primary range 987–2011; SA release stopped. `work/fc-network-sbus-20260929T045937Z.json` |
| Field dashboard LINK | 200/200 frames, 41 disarmed FC samples. `work/console/trial-20260929T014706.json` |
| Owner motor test | 152 accepted frames including ARM-high, then ten disarm frames; owner confirmed start/automatic stop with USB unplugged. `work/console/trial-20260929T014903.json` |
| Repeat/recovery UX | Live automatic prepare, zero-frame cancellation, restore/reprepare and console-only restart verified without reboot; redesigned workflow did not repeat a physical motor trial. |
| Software | 45 tests passed at last implementation checkpoint; JS syntax, Python compilation and whitespace checks passed then. Not rerun for documentation-only closeout. |
| Responsive UI | 320×568, 390×844, 768×1024, 844×390, 1280×720, 1440×900, 1920×1080; no horizontal overflow, Stop availability and explicit simulation checked. |
| Current video | Later latency audit verified actual 1280×720 playback in redesigned dashboard and WebRTC UDP reading; supersedes the redesign's offline-only video check. |

Receiver timeout/source-stop behavior passed bounded tests. Actual RF loss, reboot during ARM, independent hardware failure containment and all real flight failsafe outcomes have not been qualified. A successful idle motor test does not establish flight readiness.

## Latency handoff and next session

The complete measured findings and proposed experiments are in [LATENCY.md](LATENCY.md). **Only the saved viewer selection changed to WebRTC during that audit**; no control-protocol, capture-rate, queue, encoder or firmware change was deployed.

- HLS was about **636 ms behind its latest seekable edge** in one browser sample. That is not total camera-to-screen latency.
- Field LAN ping with video running: **2.086 / 2.515 / 3.751 ms min/mean/max**, 20 samples, no loss. This does not establish sustained jitter or WAN performance.
- Current Pi encoding is already hardware H.264, 720p30 at 1 Mbps, no B-frames; no throttling was observed in that audit.
- Per-snapshot challenge/response limits RC update cadence as RTT grows. Sampling happens after challenge receipt; do not describe a whole RTT as added age for every sampled joystick value.
- Capture/encoder buffering, distinct 60 fps capability, direct HDMI baseline and total stick-to-FC delay remain unmeasured.

**Measurement plan (now in progress; see current sprint above):** confirm devices/current settings, compare direct VRX HDMI against dashboard WebRTC with the same timed visual stimulus, then measure input-to-FC separately. Record distributions and stalls, not just ping. After a baseline, evaluate bounded fresh-frame capture queues / 720p60, and a fixed-rate authenticated latest-input protocol that preserves freshness, anti-replay and stop behavior. Those are proposals, not installed improvements.

Later work remains electrical/interface documentation, Ascent RF-loss qualification, stable capture power/USB, private WAN/backhaul tests, flight failsafe/tune verification, and eventually a second independent link. Do not resume motor-beeper troubleshooting or change the working SBUS route merely because an older checkpoint says “pending.”

The [README documentation map](../README.md#documentation-map) links every specialist page and the source-document audit. No further latency work is scheduled automatically by this handoff.
