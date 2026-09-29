# Verification record

2026-09-28 initial software preparation. Physical first-boot results are recorded below.

- 13 unit tests passed: command examples, SBUS packing boundaries, invalid channel rejection, authenticated-message tamper rejection, stale/replayed/reordered control rejection, source ownership, deadman and timeout latching.
- Localhost control smoke test passed: 50 accepted synthetic snapshots and loss latch after sender stopped.
- Two independent synthetic RTSP paths passed: H.264 at 640×360, ten frames decoded from each. All test processes stopped afterward.
- Raspberry Pi OS Lite and MediaMTX arm64/amd64 downloads passed pinned SHA-256 checks.
- User confirmed one initial FPV and later expansion to two, Industry VRX and GT Pro VTX on the bench. Owner confirms Industry and standard VRX share hardware; Pro is a new Rockchip-based revision. This identity is owner-supplied, not from physical board inspection.
- SD image personalization, physical write/readback, first boot, SSH and Pi service operation are separate steps. Their final results will be appended below.

Not yet verified: actual HDMI capture, UVC, Pi encoder throughput, physical UART voltage/baud/pinout, SBUS input/output direction and loss behavior, joystick mapping, FC configuration, RF link, internet/VPN, latency under load, autonomous failsafe or flight operation.

## Prepared image checks

- Personalized Raspberry Pi OS image: 3,061,841,920 bytes. Base compressed image and both MediaMTX builds match their pinned vendor hashes.
- Boot bundle includes 160 ARM64 package files from authenticated APT repositories, resolved using the stock image's dpkg status. Solver reported 160 new packages, zero upgrades and zero removals. No packages installed on the laptop.
- Bundled source, offline installer, package checksums and firstboot video readiness probe inspected. FAT payload and all personalized boot files read back byte-for-byte. Linux root partition remained identical to the stock image before first boot.
- Cloud-init user configuration passed the Raspberry Pi schema. The bundled cloud-init network schema omits Wi-Fi definitions; network configuration instead passed an isolated Netplan generation into NetworkManager profiles. Host networking was not changed.
- Laptop SSH alias resolves to the intended hostname, user, dedicated private key, strict host checking and separate pinned known-hosts file. Wi-Fi credentials copied privately from the current laptop profile; Ethernet DHCP also configured.
- All shell scripts passed bash syntax checks; Python source compiled. Host systemd verification can only inspect syntax because Pi-specific executable paths are absent on the laptop; actual service startup remains a Pi first-boot check.
- User authorized replacing the inserted Pi SD card. Its SD identity and capacity were checked separately from the NVMe system disk; the write plan is private and rechecks both immediately before writing.

Physical SD write and full readback PASSED. Ubuntu administrator authentication was completed locally. Exactly 3,061,841,920 bytes were written and read back with SHA-256 `f03490dc0a08d500cf79a1d439d7bbbcfcd31802849d6e56b00a3ed6e76e6f58`. Both card partitions were unmounted after completion. The SD is ready to move into the Pi. Physical first boot, SSH and service startup remain pending.

Write guard checks passed against the actual plan: the NVMe target, an incorrect SD identity and a changed capacity were all rejected before any write.

## Physical Pi first boot and LAN checks — passed

Verified 2026-09-28 after the owner booted the prepared SD card.

- `ascent-pi` resolves and connects through its existing strict, pinned SSH host key. The observed address is `192.168.1.104`, reached through onboard `wlan0`; Ethernet and the USB Wi-Fi adapter were not used by this test. Effective SSH configuration enables public keys and disables password/root login.
- Device reports Raspberry Pi 4 Model B Rev 1.2, 2 GB configured RAM, aarch64. This identifies the running board but does not resolve its membership in the inventory's original two-Pi batch.
- Unattended `ascent-firstboot` exited successfully and wrote the provisioning marker at `2026-09-28T21:58:45Z`. `dpkg --audit` was empty. MediaMTX and `ascent-video@fpv1` were enabled and running with zero restarts; no systemd services were failed.
- Startup publishes labelled synthetic H.264 at 1280×720, 30 fps. The laptop opened a temporary authenticated SSH RTSP tunnel, decoded 90 frames and saved a frame showing the synthetic label. This confirms Pi-to-laptop transport, not VRX HDMI capture.
- During the video test, the laptop sent 239 authenticated synthetic channel snapshots over LAN UDP; the Pi JSON-only receiver accepted all 239. Its watchdog latched loss after sender shutdown. No UART/GPIO was opened or driven. The temporary receiver, SSH tunnel and temporary key were removed afterward.
- Pi temperature after the tests was 42.8 °C and `get_throttled` returned `0x0`. This short test is not a thermal or sustained-throughput qualification.
- UART is enabled and `/dev/serial0` currently resolves to `ttyS0`; the kernel command line has no serial console. No GPIO electrical compatibility or SBUS timing was tested.
- USB enumeration found the attached RTL8812AU Wi-Fi adapter but no UVC capture device. Listed V4L2 devices were onboard codec/ISP devices; their existence is not a camera feed or an encoder-throughput test.

Cloud-init reported `degraded done`, no errors, and one recoverable warning: missing `cc_netplan_nm_patch`. The installed cloud-init package configuration references that module, but the file is absent; `dpkg -V cloud-init` reported no modified package files. Networking and relay provisioning succeeded. The warning remains recorded; cloud-init was not cleaned or rerun, and its configuration was not changed.

Private local evidence: `work/pi-firstboot-verification.json`, `work/pi-control-smoke.jsonl`, and `work/pi-synthetic-video.png`. Next: identify/connect HDMI capture and verify the Ascent UART/SBUS interfaces and loss behavior. Physical control, RF, FC behavior, internet/VPN and end-to-end latency remain unverified.

## Capture connection check — USB device not detected

Later on 2026-09-28, the owner reported powering the VRX and connecting its HDMI output to a capture adapter attached to the Pi. Repeated SSH checks still showed only the external RTL8812AU Wi-Fi adapter, with no capture USB device or UVC video node. A bounded 45-second USB/video udev monitor observed no connection events. No USB enumeration error or undervoltage condition was found. The adapter's model and USB data connection remain unresolved; reconnecting it directly to another Pi USB-A port is the next step. No capture configuration was guessed or enabled; the labelled synthetic stream remains active.

Independently, Pi `h264_v4l2m2m` encoded 90 synthetic 1280×720 frames successfully, and ffprobe decoded/count-verified all 90. This proves the hardware encoder can operate on generated frames, not that the absent capture device works or that sustained capture/encode latency is acceptable. The temporary encoded file was deleted. Check summary: `work/pi-capture-check.json`.

## USB capture and VRX HDMI through RTSP — passed; FPV trial paused

After the owner changed the USB cable, the capture adapter enumerated as `534d:2109`, manufacturer string `MACROSILICON`, product `USB Video`, without a serial number. It operates through `uvcvideo` at USB 2.0 high speed (480 Mbit/s). The video node is `/dev/video0` with stable single-adapter alias `/dev/v4l/by-id/usb-MACROSILICON_USB_Video-video-index0`; `/dev/video1` is metadata. Retail brand/model remain unknown.

- Advertised formats are MJPEG and YUYV, not H.264. Selected MJPEG 1280×720 at 30 fps. Higher advertised modes were not tested and do not establish unique camera-frame rates.
- Direct capture → hardware H.264 test encoded 90 frames in approximately 3.63 seconds including startup; ffprobe decoded/count-verified all 90. This is a functionality check, not a glass-to-glass latency measurement.
- Saved the prior Pi video configuration, installed `config/video-macrosilicon-720p30.json` as `/etc/ascent-relay/video-fpv1.json`, and restarted the already enabled publisher. It remained running with zero automatic restarts. MediaMTX reported its H.264 stream online.
- Pi-side RTSP inspection reported H.264, 1280×720, 30 fps. Laptop RTSP through a temporary authenticated SSH tunnel decoded 90 frames. An initial attempt encountered transient hostname/network access trouble; the successful retry used the known Pi IP with the existing pinned host key. The temporary tunnel was closed afterward.
- First direct capture showed plain colour bars. The later RTSP frame visibly showed the CADDX VRX interface, 0 Mbps, No Sig, and “Transmitter is disconnected.” This proves VRX HDMI → capture USB → Pi encoding → RTSP → laptop. It does not prove a VTX camera link, usable FPV latency, or RC transport. The cause of the HDMI picture transition was not independently established.
- Temperature was 43.3 °C, with no throttling recorded during the check. No UART/GPIO control output was enabled.

Evidence: `work/vrx-capture-first.jpg`, `work/vrx-capture-rtsp.jpg`, and `work/pi-capture-rtsp-verification.json`. The owner requested a pause to prepare an FPV. Capture configuration remains saved and its enabled service remains running; the next test is the GT Pro camera link when the owner resumes.

## GPIO/HID preparation resumed — Pi UART prepared

The owner resumed wiring preparation while finishing the FPV. The live Pi initially exposed `/dev/serial0 -> ttyS0`, with no serial console/getty and no process using the UART. The mini UART does not support parity; switched GPIO14/15 to PL011 using the official `disable-bt` overlay. Added `scripts/configure-uart.sh` and updated the repeatable installer/image personalizer. The existing staged image was not rebuilt or reflashed.

- Applied the helper to the Pi, preserving the previous boot configuration in a timestamped backup; reboot completed and strict pinned SSH access returned.
- `/dev/serial0 -> ttyAMA0`; `pinctrl get 14-15` reports GPIO14 TXD0 and GPIO15 RXD0. Serial getty and hciuart are inactive, and no process owns `ttyAMA0`. Onboard Bluetooth is disabled; Wi-Fi access remains operational.
- Re-running the helper left both boot configuration file hashes unchanged. Shell syntax, Python compilation and Git whitespace checks passed.
- Both video services returned active after reboot. Pi-side RTSP probe reports H.264 1280×720. No new VTX camera image or latency measurement was taken.
- Laptop input enumeration still shows no USB joystick. VRX voltage measurement, running firmware/menu options, RC model and FPV FC/firmware have been requested. No VRX signal wire connection, physical serial frame transmission, or FC channel movement has been verified.

Private check summary: `work/pi-uart-preparation.json`. Next: obtain VRX signal levels and USB joystick detection, fit the conditional UART wiring in `docs/BRINGUP.md`, and establish the actual passthrough protocol before enabling physical output.

## Radio HID detected and FC configuration read — physical relay still pending

The owner confirmed props removed, UART leads connected to Pi GPIO, and a RadioMaster GX15 connected to the laptop in USB joystick mode. No voltage result was supplied; requested TX/RX disconnection if their level had not been checked. The Pi still reports PL011 on GPIO14/15, no process using the UART, and both video services active. Connection by the owner does not verify signal levels or jumper orientation.

- Linux identifies the radio as `1209:4f54`, `OpenTX TX15 Joystick`, with 8 axes and 24 buttons. Preserve the owner's GX15 identification separately from the USB descriptor. Axis 2 initially reads -32767; axes 0, 1 and 3 read zero. Physical stick identities have not been assigned from those values.
- A bounded 60-second USB read captured only the initial snapshot, with no subsequent state changes. No stick directions, endpoints or deadman switch were calibrated.
- A separate 10-second diagnostic sent 500 real, unmapped HID snapshots to a JSON-only reader on the Pi through authenticated SSH. All 500 arrived in sequence, with no state changes. This verifies raw USB-input-to-Pi delivery over SSH; it is not the existing authenticated UDP control test, a calibration result, or a serial/RF/FC control test. Both diagnostic processes exited afterward.
- A USB Betaflight STM32H743 controller answered read-only MSP queries: API 1.46, Betaflight 4.5.1, board name `GEPRC_TAKER_H743`, manufacturer `GEPR`. Its receiver provider byte is 9 (CRSF); serial port identifier 6 (UART7) has function mask 64 (serial RX). No settings, CLI commands, motor outputs or RC override messages were written. Physical board identity and its VTX wiring remain to be confirmed by the owner.
- Decoding follows the matching [4.5.1 MSP reply implementation](https://github.com/betaflight/betaflight/blob/4.5.1/src/main/msp/msp.c), [receiver enumeration](https://github.com/betaflight/betaflight/blob/4.5.1/src/main/rx/rx.h), and [serial port enumeration](https://github.com/betaflight/betaflight/blob/4.5.1/src/main/io/serial.h). Configured CRSF input does not establish what the Ascent UART transports.

Private evidence: `work/radio-hid-inspection.json`, `work/radio-hid-movement.json`, `work/radio-hid-pi-raw.json`, `work/fc-msp-readonly.json`, and `work/fc-bench-summary.json`. Shared inventory records the owner-identified radio and USB-observed FC separately, with the latter's ownership/physical identity unresolved. Next: obtain voltage and VRX Command/ELRS mode, confirm VTX-to-FC wiring, then calibrate moving sticks and the held deadman before physical relay output.

## GT Pro / TAKER six-pin mapping confirmed in manuals

The owner confirmed the FC is the GEPRC TAKER H7 used for this FPV, with the GT Pro connected directly to its digital-VTX socket. CADDX's standard/Industry GT Pro V1.0 guides show a dedicated SBUS conductor; GEPRC's English VTX diagram shows SBUS to R2, UART TX/RX to RX1/TX1, UART1 MSP and UART2 Serial RX. Rendered Industry and GEPRC diagrams were visually inspected. See [FC-WIRING.md](FC-WIRING.md) for sources, settings and limits.

After the owner selected MSP Receiver Mode, read-only USB queries confirmed RX_MSP enabled, RX_SERIAL disabled, stored serial provider SBUS and initially no serial RX port. The owner then enabled UART2 Serial RX. A later full-width MSP2 read verified UART1 mask 131073 (MSP + VTX MSP) and UART2 mask 64 (Serial RX), while Receiver Mode remained MSP. The owner was advised to change only Receiver Mode to Serial (via UART) for this SBUS route; SBUS was already selected. No FC settings were changed by the assistant. One intervening read could not start while USB was briefly absent; the successful later read is the current snapshot.

The manual evidence does not prove that the VRX's UART input converts to the VTX's SBUS output. Ordinary Pi TX/RX wiring is still not a verified SBUS source. Physical output remains disabled pending the electrical/output-interface work and end-to-end loss tests. The inventory now records the owner-confirmed FC and connected GT Pro as in use for the project.

## Serial Receiver Mode verified; missing SBUS firmware driver identified

After the owner changed Receiver Mode, read-only MSP confirms RX_SERIAL enabled, RX_MSP disabled, provider 2 (SBUS), UART2 Serial RX and UART1 MSP + VTX MSP. MSP_RC returns an empty payload, meaning zero runtime RC channels; this is not a successful receiver initialization or RF test.

A live MSP_BUILD_INFO query reports the installed build's serial receiver option as CRSF (4097), with no SBUS option (4103). Decoded against Betaflight 4.5.1's generated build-option table and conditional driver reporting. Its SBUS initializer normally sets the channel count before any valid input frame, so the missing compiled driver explains the zero-channel result. Firmware identity: Betaflight 4.5.1, Jan 10 2025 01:13:49, revision 77d01ba. No FC settings or firmware were changed by the assistant.

Private evidence: `work/fc-serial-sbus-mode-verified.json` and `work/fc-build-options-verified.json`. Next: preserve the FC configuration and prepare firmware with SBUS included, alongside the Pi-to-VRX SBUS electrical interface. The owner reiterated the VRX's separate SBUS pin; this remains the intended input, avoiding any reliance on undocumented UART-to-SBUS conversion inside Ascent.

Configuration backup subsequently completed in `work/fc-backup-20260929T032146Z/`: version/status, 2,672-byte complete `diff all`, 39,558-byte complete `dump all`, and SHA-256 manifest. The first dump capture mistook an intermediate comment prefix for the CLI prompt and the next write timed out. The remaining output was drained, CLI exited, and the full dump was reread with a settled-prompt check; both final exports include their closing save section. The partial file is retained under an explicit `.partial.txt` name. After CLI exit/reboot, the FC answered MSP API 1.46 again. No save, configuration write, motor command or flash was transmitted. Firmware binary backup and restoration have not been performed.

## Owner flashed 2026.6.2; FC setup and saved tune migrated

The owner flashed the correct GEPRC_TAKER_H743 target and requested configuration. Live USB confirms Betaflight 2026.6.2 / MSP 1.48, SBUS build option 4103 and 18 initialized RC channels. A complete fresh-build dump/diff was captured and checksummed before changes. Receiver/OSD/GPS, saved switch assignments and OSD layout were saved. The owner then explicitly requested the previous flight tune; migrated profile 0, renamed D-min/D-max settings, dynamic idle, filters and compatible ancillary settings. See [FC-2026-SETUP.md](FC-2026-SETUP.md) for exact scope and semantic differences.

- Every configuration command was accepted, saved and read back after reboot. All 105 retained-name profile-0 values match the full old dump; all four rate profiles match. Renamed/converted values also matched the migration manifest. Complete final dump/diff/status/options have SHA-256 checksums.
- Normal MSP communication after final CLI exit confirms UART1 mask 131073, UART2 mask 64 and UART4 mask 2. The first serial assertion used old port IDs and failed; the corrected read uses the matching 2026.6.2 IDs 51/52/54. No setting write occurred during either verification read.
- GPS M10 connected/configured on UART4 at 57600, no satellite fix. MPU6000 active, DPS310 detected, MSP OSD 53 × 20. RX rate zero and RXLOSS remain. No claim of received SBUS packets, flight response, board alignment, motor direction or failsafe behavior.
- FC serial handle closed. No motor/arm/RC override command sent. No Pi UART/GPIO physical RC output enabled.
- Owner reports VRX SBUS connected to Pi GPIO14 / physical pin 8. Read-only Pi check shows ALT0 TXD0 idle high and no UART owner; video services remain active. Asked for signal disconnection and VRX-side voltage measurement. Direct inverted GPIO waveforms via pigpio are a potential alternative to a UART inverter, not an installed or verified output path.

Evidence: `work/fc-postflash-backup-20260929T033756Z/`, `work/fc-2026-sbus-setup-responses/`, `work/fc-2026-tune-responses/`, `work/fc-2026-configured-backup/`, `work/fc-2026-setup-verified.json`, and `work/fc-2026-final-msp.json`.


## Live camera, bounded RC probes and bench mute — 2026-09-29

- Owner confirms `ELRS TT` and shared VRX/Pi ground, and explicitly declines voltage measurement. Electrical compatibility remains unverified.
- After VRX HDMI returned from the monitor to the Pi capture card, `work/vrx-reconnected.jpg` showed the actual GT Pro camera image and Betaflight OSD through RTSP. This supersedes the earlier transmitter-disconnected checkpoint. The Ascent 85 ms overlay is not a measured total camera-to-screen delay.
- Installed Pi `python3-serial` 3.5-2 for bounded CRSF probes. Four 4-second tests at 420000, 115200, 400000 and 416666 baud completed with 195–196 frames each. Each of the four USB observations contains 74 samples: all disarmed, no FC channel change. Private evidence: `work/fc-crsf-trial-*.json`. No continuous serial output remains.
- Built/installed a private pinned pigpio library and prepared the finite direct-SBUS probe. Driver initialization passed (v79, GPIO14 ALT0). This check made no SBUS transmission or pin write. UART remained unowned; GPIO14/15 remained TXD0/RXD0. No pigpio daemon or output service runs. Nineteen host tests passed, including independent SBUS waveform decoding. See [SBUS bench procedure](SBUS-BENCH.md).
- RX-loss beeper mute persisted on readback, but owner reported further noise. Battery status was OK at 21.99 V / 6S. Saved `beeper -ALL` and retained both motor-beacon disables; post-reboot readback confirms all FC buzzer events muted. Voltage thresholds and flight failsafe policy unchanged. The sound source if it persists is unresolved; ESC autonomous settings were not changed. See [restore instructions](FC-2026-SETUP.md#bench-buzzer-mute--2026-09-29).

## LAN browser viewer — passed, 2026-09-29

At the owner's request, enabled MediaMTX WebRTC and HLS listeners on the Pi using `config/mediamtx-lan.yml`. Existing configuration backed up first. Video publishing reconnected after the MediaMTX restart; both video services are active and enabled. RTSP remains loopback-only and LAN clients have read-only permissions on the two named stream paths.

The laptop at 192.168.1.133 loaded both `http://192.168.1.104:8889/fpv1/` and `http://192.168.1.104:8888/fpv1/`. Browser screenshots visibly showed the live workshop camera picture and FC OSD. WebRTC logs confirm an established peer connection and H.264 reading; the HLS playlist returned HTTP 200 after following its session redirect. No extra video transcoder was added. Playback was verified, not end-to-end latency or WAN operation. See [LAN-VIEWER.md](LAN-VIEWER.md).

Current muted-FC complete backup captured in `work/fc-bench-muted-backup-20260929T041655Z/` (39,565-byte dump, 3,266-byte diff, checksum manifest); closing save marker verified. CLI exited with USB closed.
