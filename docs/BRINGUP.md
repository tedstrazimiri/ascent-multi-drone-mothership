# Bench bring-up

## First boot

The prepared personalized card is intended to boot without a keyboard or display. Use the existing router/switch LAN and a regulated Pi supply. The image configures Ethernet DHCP, the selected existing laptop Wi-Fi profile when readable, SSH public-key access and automatic package/service provisioning. See [IMAGE.md](IMAGE.md). The prepared dependency bundle supports offline installation; SSH setup is independent of relay package readiness.

From this laptop use `ssh ascent-pi` after `ascent-relay.local` appears. Check `cloud-init status --long`, `systemctl status ascent-firstboot`, and `journalctl -u ascent-firstboot -b`. Only a successful provisioning marker plus active services establishes readiness; network presence alone does not.

The startup stream is labelled SYNTHETIC BENCH VIDEO. It proves a transport path, not VRX reception. No RC output starts automatically.

First boot passed on 2026-09-28: `ssh ascent-pi` works, observed Wi-Fi address `192.168.1.104`, packages installed and synthetic video starts automatically. Laptop video decode and JSON-only LAN control/loss tests passed. DHCP addresses can change; prefer the SSH alias. See [verification details](VERIFICATION.md).

## HDMI capture

**Current saved configuration (2026-09-28):** the running Pi now uses the MacroSilicon USB capture adapter (`534d:2109`) at `/dev/v4l/by-id/usb-MACROSILICON_USB_Video-video-index0`, MJPEG 1280×720 at 30 fps, and `h264_v4l2m2m` at a requested 3 Mbit/s. The reusable profile is [video-macrosilicon-720p30.json](../config/video-macrosilicon-720p30.json); it has been applied to `/etc/ascent-relay/video-fpv1.json`. The previous synthetic configuration remains backed up as `/etc/ascent-relay/video-fpv1.json.before-hdmi-20260928T225427Z`. Generic image defaults remain synthetic.

On 2026-09-29, after the owner returned the VRX HDMI cable from the monitor to the capture card, the laptop received the live GT Pro camera picture and Betaflight OSD through the Pi RTSP path. The owner confirms `ELRS TT` and shared VRX/Pi ground. Four finite CRSF UART probes produced no FC channel movement. The next test is the dedicated SBUS input; see [current bench procedure](SBUS-BENCH.md). No persistent RC output is enabled.

Changing the USB cable resolved capture enumeration. Initial capture frames were plain colour bars; later frames showed the VRX interface. If colour bars recur, check HDMI input/output connections and the receiver's HDMI mode. The standard Ascent VRX manual specifies holding **BACK for 8 seconds** to restore 720p60 HDMI output. This changes HDMI timing; it is not the LINK/firmware-upgrade action. [Manufacturer manual](https://cdn.shopify.com/s/files/1/0036/3921/4169/files/Ascent_VRX_User_manual_V1.0.pdf?v=1769739026).

This adapter has no USB serial number. With a second identical adapter, use verified `/dev/v4l/by-path` connections to prevent ambiguous identities. `/dev/video1` on this adapter is its metadata node, not the capture stream.

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

Current radio: owner identifies a RadioMaster GX15; USB reports `OpenTX TX15 Joystick`, 8 axes and 24 buttons. Raw input reaches the Pi through a read-only SSH diagnostic, but no stick movement/direction or deadman mapping has been verified. Select the observed `...TX15_Joystick...-joystick` symlink on this laptop, not its `event-joystick` node. The owner flashed `GEPRC_TAKER_H743` to Betaflight 2026.6.2 with SBUS. Saved/rebooted readback confirms UART1 MSP + DisplayPort, UART2 Serial RX, Serial Receiver Mode and SBUS; UART4 GPS is detected. The saved active tune was migrated at the owner's request. MSP_RC now reports 18 initialized channels, but RX rate is zero and RXLOSS remains. See [current FC setup/tune](FC-2026-SETUP.md) and [manual mapping and output interface](FC-WIRING.md).

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

### Pi UART preparation and wiring

`sudo bash /opt/ascent-relay/scripts/configure-uart.sh` configures the Pi 4's full PL011 UART on GPIO14/15, disables onboard Bluetooth and serial gettys, and backs up changed boot files. Reboot to apply. The mini UART previously exposed as `ttyS0` cannot provide parity, so it is unsuitable for standard SBUS 8E2. PL011 still requires the correct external polarity/voltage interface for SBUS. This setup never opens the port or transmits RC frames. [Raspberry Pi UART documentation](https://www.raspberrypi.com/documentation/computers/configuration.html#configuring-uarts).

Verify `/dev/serial0` resolves to `ttyAMA0`, `pinctrl get 14-15` reports TXD0/RXD0, and no serial console/getty owns the port. The reusable image and installer now apply this same configuration. The already flashed image file has not been rebuilt.

Before signal wiring, measure the separately powered VRX TX relative to G with the Pi disconnected: meter in DC-voltage mode, black probe on G, red on TX. A 5 V reading rules out direct GPIO wiring; 0 V or an intermediate reading does not establish normal UART signalling. An idle reading near 3.3 V is useful evidence, but a meter does not prove peak voltage, baud rate, inversion or the RX input specification. Record the actual result and resolve uncertain levels with revision-matched specifications or a scope/appropriate interface.

For a confirmed 3.3 V UART, shut the Pi down cleanly, then remove power from both devices before fitting jumpers. Follow the harness labels, not an assumed connector orientation:

| VRX harness label | Pi 40-pin header | Direction / purpose |
|---|---|---|
| G | Physical pin 6, GND | Common reference |
| RX | Physical pin 8, GPIO14/TXD0 | Pi → VRX |
| TX | Physical pin 10, GPIO15/RXD0 | VRX → Pi |
| 5V | Unconnected and insulated | Keep supplies separate |
| SBUS | Unconnected for the UART test | Separate signalling/interface |
| Second G | Unconnected | One common ground lead is sufficient |

Physical pin numbers differ from GPIO numbers. Identify pin 1 from the board marking before counting. GPIO14 and GPIO15 are **physical pins 8 and 10**, not physical pins 14 and 15. Never feed 5 V into a Pi signal pin.

Check the VRX menu for `Ascent VRX-Uart` and its `Command`/`ELRS pass-through` options. Record running firmware and the options actually present. The supplied firmware notes describe these options, but do not establish this unit's UART baud/framing or that ELRS mode converts UART channels to the GT Pro's SBUS output. Do not select a guessed baud or send the supplied management packets as stick commands. `relay.bench` remains a JSON/SBUS-hex receiver until the physical protocol is established.

### Link checks

1. Confirm exact VRX/GT Pro firmware and connector direction/voltage. The owner-labelled `SBUS, 5V, RX, TX, G, G` list is not a pin-numbered mating-face diagram.
2. If UART signals are documented/measured as Pi-compatible, connect only crossed TX/RX and common ground. Leave 5 V unconnected. Disable the Pi serial console before opening the UART. Use Command mode only for verified management exchanges; do not route stick channels through the supplied menu packet format.
3. Confirm receiver input SBUS and VTX output SBUS using a known SBUS source and logic analyser/FC receiver page. Check normal 100000-baud inverted 8E2 versus any device-specific variant. A finite, inverted GPIO14 SBUS probe is now prepared; see [SBUS-BENCH.md](SBUS-BENCH.md) for its separate wiring and explicit start conditions.
4. Add a hardware output MCU with independent expiry. Verify all 16 channel destinations, polarity, endpoints and arm/mode mapping. Keep the initial receiver loss behavior latched.
5. Deliberately stop the sender, unplug HID, remove IP, stop Pi software, reset/power-cycle Pi, disconnect VRX input, and interrupt the Ascent RF link. Observe what arrives at the FC and whether its actual failsafe activates. No stage may indefinitely repeat a last valid armed value.
6. Measure stick-to-FC latency and stale video behavior. Only then test WAN impairment and plan field evaluation. A successful software SBUS frame or menu query does not establish radio transport or FC loss behavior.

The FC's SBUS firmware, configuration and saved-tune migration are complete; see [FC-2026-SETUP.md](FC-2026-SETUP.md) for private backups and verification limits. Still needed: physical stick/deadman mapping, actual Ascent RC transport, VRX/GT Pro running firmware and passthrough settings, signal voltage, capture retail model and the SBUS output interface.

The owner subsequently connected the VRX SBUS lead to **physical header pin 8 / BCM GPIO14**. Live Pi readback still shows ALT0 TXD0, idle high, with no UART user. Requested signal-lead disconnection and a VRX-side SBUS-to-GND voltage measurement before a direct-drive test. No transmission or pin-mode change was made. Ordinary PL011 UART needs an inverter for standard SBUS; an alternative using pigpio hardware-timed GPIO waveforms could generate inversion directly, but has not been implemented or tested here. The current Pi image has no pigpio daemon installed or package candidate; its Python client alone is insufficient. [Upstream waveform support](https://github.com/joan2937/pigpio). Neither an external inverter nor direct GPIO signalling has yet been qualified electrically against this VRX.

**Latest owner wiring update:** pin 8 / GPIO14 is back to **Pi UART TX → Ascent RX**, replacing the temporary SBUS-pin connection. That is the UART signal direction, not a verified SBUS source or evidence that Ascent converts UART input to SBUS output. No control output is enabled; voltage and the dedicated SBUS input/interface remain unresolved.


**2026-09-29 update:** The owner explicitly declined voltage measurement; electrical compatibility remains unverified and must not be represented as measured. Common VRX/Pi ground is owner-confirmed. The source-built private pigpio library and finite SBUS probe supersede the earlier statement that no GPIO implementation exists. Current wiring remains pin 8 → VRX RX until the owner confirms the move to VRX SBUS. See [SBUS-BENCH.md](SBUS-BENCH.md).
