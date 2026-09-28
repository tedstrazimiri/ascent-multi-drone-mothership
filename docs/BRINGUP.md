# Bench bring-up

## First boot

The prepared personalized card is intended to boot without a keyboard or display. Use the existing router/switch LAN and a regulated Pi supply. The image configures Ethernet DHCP, the selected existing laptop Wi-Fi profile when readable, SSH public-key access and automatic package/service provisioning. See [IMAGE.md](IMAGE.md). The prepared dependency bundle supports offline installation; SSH setup is independent of relay package readiness.

From this laptop use `ssh ascent-pi` after `ascent-relay.local` appears. Check `cloud-init status --long`, `systemctl status ascent-firstboot`, and `journalctl -u ascent-firstboot -b`. Only a successful provisioning marker plus active services establishes readiness; network presence alone does not.

The startup stream is labelled SYNTHETIC BENCH VIDEO. It proves a transport path, not VRX reception. No RC output starts automatically.

First boot passed on 2026-09-28: `ssh ascent-pi` works, observed Wi-Fi address `192.168.1.104`, packages installed and synthetic video starts automatically. Laptop video decode and JSON-only LAN control/loss tests passed. DHCP addresses can change; prefer the SSH alias. See [verification details](VERIFICATION.md).

## HDMI capture

Connect VRX HDMI OUT to an HDMI-to-USB capture adapter and its USB output to a Pi USB 3 socket. Use the VRX's correctly rated independent supply. The Pi HDMI sockets are unused inputs because they cannot receive video. Read labels and HDMI orientation before connecting.

Run `bash scripts/probe.sh` in this checkout, or use `v4l2-ctl --list-devices` and `v4l2-ctl -d /dev/v4l/by-id/ACTUAL_DEVICE --list-formats-ext` remotely. Record the actual stable path, input formats, mode and framerate. Replace the placeholder in `/etc/ascent-relay/video-fpv1.json`, set `source` to `v4l2`, and select a supported mode. `encoder: copy` is only allowed with `input_format: h264`. For MJPEG/YUYV select a tested encoder. Restart `ascent-video@fpv1` after editing.

For the initial SSH video tunnel run:

```bash
ssh -N -L 8554:127.0.0.1:8554 ascent-pi
```

In another terminal:

```bash
ffplay -rtsp_transport tcp -fflags nobuffer -flags low_delay -framedrop rtsp://127.0.0.1:8554/fpv1
```

This viewer command is an initial buffer-reduction setting, not a latency guarantee. Check live movement or a timer in camera view; a frozen picture can otherwise look valid. Capture a bounded test, measure delay, disconnect HDMI/USB deliberately, and verify clearly reported failure and recovery before moving to WAN.

## USB HID and software control

Read the radio in joystick mode on the laptop. Find `/dev/input/by-id/*-joystick` (not `event-joystick`) and inspect it:

```bash
python3 -m relay.joystick /dev/input/by-id/ACTUAL_RADIO-joystick
```

Move one control at a time, including switches. Copy `config/joystick.example.json` to ignored `local-joystick.json`. Confirm axis order, inversion, full travel, throttle bottom and the held deadman button. The example mapping is not verified for your radio. USB HID may expose fewer channels/switches than the transmitter's RF output. The current bench only maps four axes; AUX and arming logic must be added for the actual FC later.

Run a software-only test on this laptop:

```bash
mkdir -p work
python3 -m relay.bench keygen --key work/fpv1.key
python3 -m relay.bench receiver --key work/fpv1.key --seconds 120
```

In a second terminal, hold the mapped deadman before starting:

```bash
python3 -m relay.bench sender --key work/fpv1.key --joystick /dev/input/by-id/ACTUAL_RADIO-joystick --mapping local-joystick.json --seconds 30
```

Or use `--synthetic` in place of `--joystick ... --mapping ...` for a clearly synthetic test. Receiver output is JSON only. A timeout/deadman loss is latched; stop and restart the receiver to begin a new test. Keys are random, private and never committed. Use a different key, drone ID and UDP port for `fpv2`.

For laptop→Pi bench testing, copy that key privately with `scp`, place the checkout on both ends, and specify concrete Pi `--bind` and laptop `--peer` IPv4 addresses at the receiver; specify Pi `--host` at the sender. Use actual LAN/VPN addresses, not placeholders. UDP default port is 14600. Do not expose it publicly. Keep the prepared receiver in the foreground until its behavior is understood.

## Electrical and end-to-end control validation

Leave props and suppression payloads off for these tests. This is needed to observe channel values and deliberate disconnects without actuation hazards.

1. Confirm exact VRX/GT Pro firmware and connector direction/voltage. The owner-labelled `SBUS, 5V, RX, TX, G, G` list is not a pin-numbered mating-face diagram.
2. If UART signals are documented/measured as Pi-compatible, connect only crossed TX/RX and common ground. Leave 5 V unconnected. Disable the Pi serial console before opening the UART. Use Command mode only for verified management exchanges; do not route stick channels through the supplied menu packet format.
3. Confirm receiver input SBUS and VTX output SBUS using a known SBUS source and logic analyser/FC receiver page. Check normal 100000-baud inverted 8E2 versus any device-specific variant. No GPIO SBUS output implementation is included yet.
4. Add a hardware output MCU with independent expiry. Verify all 16 channel destinations, polarity, endpoints and arm/mode mapping. Keep the initial receiver loss behavior latched.
5. Deliberately stop the sender, unplug HID, remove IP, stop Pi software, reset/power-cycle Pi, disconnect VRX input, and interrupt the Ascent RF link. Observe what arrives at the FC and whether its actual failsafe activates. No stage may indefinitely repeat a last valid armed value.
6. Measure stick-to-FC latency and stale video behavior. Only then test WAN impairment and plan field evaluation. A successful software SBUS frame or menu query does not establish radio transport or FC loss behavior.

The exact RC model, FPV FC/firmware, VRX/GT Pro running firmware, UART voltage, capture model and independent SBUS output adapter remain required inputs.
