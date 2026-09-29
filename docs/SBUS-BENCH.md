# Current physical control experiment

2026-09-29: Owner confirms VRX UART mode **ELRS TT**, common VRX/Pi ground, and props removed. Owner explicitly declined voltage measurement; signal-level compatibility remains unverified. The camera/OSD path works. The FC is configured for standard SBUS on UART2, with AETR channel mapping and ARM on AUX1 high.

## UART result

Pi GPIO14 / physical pin 8 was connected to VRX RX. Four finite CRSF trials at 420000, 115200, 400000 and 416666 baud each sent 195–196 fixed-disarmed channel frames over four seconds. Each trial collected 74 FC status/channel observations over USB. All observations were disarmed; no channel movement appeared. The FC's first four reported channels remained `[1500,1500,1500,885]` in MSP roll/pitch/yaw/throttle order.

This fails to demonstrate UART-to-SBUS conversion in the tested configuration; it does not establish which link stage rejected the data or prove that the hardware lacks that feature. No Ascent management commands were sent. CRSF framing follows the [TBS specification](https://github.com/tbs-fpv/tbs-crsf-spec/blob/main/crsf.md); that specification does not establish Ascent's electrical levels or configured rate.

## Direct SBUS probe — passed

`relay.sbus_probe` builds inverted 100000-baud 8E2 on GPIO14 with pigpio DMA-timed pulses. Each submission is one 25-byte, 3 ms frame, ending idle low. No repeating waveform or background daemon is used. Duration defaults to four seconds and cannot exceed ten; normal termination stops waves and leaves GPIO14 as input with pull-down. A killed sender cannot leave an indefinite repeat queue. This is a fixed-disarmed bench test, not a flight-qualified control output.

Two test snapshots alternate roll 816/1168 once per second; pitch/yaw stay 992, throttle and all AUX stay 172. The module accepts no arbitrary live channel input. It never arms or sends motor commands. [SBUS framing reference](https://github.com/bolderflight/sbus).

The private pigpio library was source-built and installed on the Pi. Its initialization check returned version 79 with GPIO14 still ALT0; no SBUS frame or pin write was made. There is no pigpio service, FIFO listener or network daemon. Source commit `c33738a320a3e28824af7807edafda440952c05d`; archive SHA-256 `805c34565986102adb0b10782ad4e6917815bf1369fb4e364f157c9f06e5cbc5`. The optional [installer](../scripts/install-pigpio-bench.sh) verifies this hash and installs only the private library/license/source identifier. It requires the Pi's compiler, make, curl and sudo; these were present on this bench Pi.

**Owner-confirmed current wiring:** Pi physical pin 8 / GPIO14 goes to **VRX SBUS**, with common ground retained. This supersedes the earlier Pi TX → VRX RX wiring. The 5 V harness lead stays separate.

The finite probe ran successfully with concurrent USB FC monitoring: 195 frames over four seconds, alternating FC roll between 1390 and 1610, pitch/yaw 1500, throttle and AUX 987. All 74 FC observations stayed disarmed. After output stopped, FC channels returned to their loss values, including throttle 885. This proves the SBUS route through these Ascent units, not RF-outage behavior, failsafe flag preservation, calibrated latency or electrical margins. Evidence: `work/fc-sbus-trial-20260929T042729Z.json`.

The explicit repeatable bench invocation on the Pi is:

```bash
cd /opt/ascent-relay
sudo python3 -m relay.sbus_probe --seconds 4 --transmit --sbus-wired
```

Without `--transmit`, the default is a dry run. `--check-driver` initializes the library without pin writes. No RC service starts at boot. Returning to UART later requires restoring GPIO14 ALT0 and moving the lead back to VRX RX; do not switch modes silently.

The host test suite now passes 26 tests, including independent waveform decoding, calibrated HID axis handling, AUX isolation, and real localhost UDP rejection of ARM-high packets, wrong authentication and replay, followed by timeout shutdown. Physical synthetic network output subsequently passed as described below.

## Calibrated HID and next network test

The owner followed the stick-movement sequence: roll is USB axis 0, pitch 1, throttle 2 and yaw 3; all observed endpoints are -32767/+32767 and no inversion is required for the requested sequence. SA position 3/high is USB axis 5 at +32767; centre is 0 and low is -32767. Owner intends SA high to arm via FC AUX1. USB axis numbering is not FC channel numbering.

`config/joystick-tx15-bench.json` uses SA high only as the **bench transport enable**. All AUX, including ARM AUX1, stay 172; this does not enable actual arming. The sender waits for SA high and low throttle before its first frame, then permits stick movement. Returning SA to centre/low sends a stop and ends the run; restarting is explicit. A radio disconnect also ends the sender and lets the Pi watchdog expire.

`relay.sbus_bench` connects the authenticated protocol to the same one-shot GPIO waveform driver. It has a maximum duration of 120 seconds, peer IP restriction, 150 ms challenge lifetime and 250 ms accepted-control timeout. It rejects any high AUX before physical output. No RC boot service is installed. The existing `relay.bench receiver` remains a separate JSON-only diagnostic.

**Resolved access blocker:** Pi at 192.168.1.104 still answered HTTP 200, but SSH commands stalled after successful authentication; ping increased to 1399–2079 ms while the laptop-to-router ping was 3–5 ms. No new receiver deployment or physical network test was attempted through this degraded connection. Ethernet was unavailable. Inspection showed onboard wlan0 active and the owner-identified Alfa disconnected; bringing Alfa wlan1 onto the existing network restored the intended route. Do not loosen freshness limits to hide this delay.

## Alfa network-to-FC result — passed

Activated the existing RTL8812AU USB adapter (`rtw88_8812au`) with an `ascent-alfa` NetworkManager profile cloned privately from the existing Wi-Fi connection. No password was displayed. Autoconnect is enabled, power save disabled, route metric 500; original onboard wlan0 remains available at metric 600. Alfa obtained **192.168.1.105**, and `ip route get 192.168.1.133` selects wlan1/source .105. Onboard address remains .104. An initial .105 reachability failure was followed by successful explicit-interface pings and SSH; DHCP addresses are not reserved.

Copied all five required Python modules to `/opt/ascent-relay` and verified their SHA-256 values. A private root-readable key in `/run/ascent-sbus-bench.key` is temporary and does not survive Pi reboot. Its laptop counterpart is ignored by Git; never print or publish it.

The four-second synthetic LAN test sent and accepted **200/200** authenticated snapshots. FC roll followed 1437–1562; pitch/yaw stayed 1500, throttle 987 and AUX1–12 987 during reception. All **116** FC observations stayed disarmed. Receiver logged `loss_latched` then stopped after the sender ended; FC returned to loss values. Both processes exited successfully. Evidence: `work/fc-network-sbus-20260929T045435Z.json`. Browser video consumers were temporarily disconnected for this baseline; simultaneous video/RC, HID movement and RF-outage tests remain separate.

Next: complete a finite live joystick trial with `config/joystick-tx15-bench.json`, then test simultaneous video traffic and source-loss behavior. Keep all AUX low until the requested ARM mapping is deliberately enabled in a later test. No RC process starts automatically.

## Simultaneous HLS/control and HID startup check

Restored one HLS viewer at `http://192.168.1.105:8888/fpv1/` and closed the duplicate agent-created viewer. Browser screenshot showed the live camera/FC OSD; MediaMTX logged the HLS reader. Pi pings while the viewer was active were 4.6–10.0 ms. Repeated the four-second synthetic control trial: another **200/200** snapshots accepted, FC roll1466–1562, all116 FC observations disarmed, loss_latched/stopped after sender exit. Evidence `work/fc-network-sbus-20260929T045809Z.json`. This is a short coexistence check, not sustained performance or internet-latency qualification.

The 100-second live-HID window transmitted **zero** packets because throttle remained near centre (axis2=-598) and SA low (axis5=-32767). The startup interlock correctly withheld output. All1687 FC samples stayed disarmed and unchanged. Evidence `work/fc-network-sbus-20260929T045527Z.json`. Live stick-to-FC movement therefore remains unverified. Ask the owner to put throttle down and SA high and confirm ready before opening another finite window.

Final readback: GPIO14 input/pull-down, no SBUS output process, both video services active. Alfa autoconnect/power-save-off/metric500 saved and read back; persistence across reboot has not yet been exercised. The temporary /run key survives until reboot. No RC autostart or actual ARM mapping is enabled.


## TX15 dashboard and indoor SA test — latest checkpoint

The subsequent live HID run accepted1,803 snapshots and recorded1,689 disarmed FC samples, with all four primary channels traversing987–2011; SA release stopped output. Evidence `work/fc-network-sbus-20260929T045937Z.json`. This supersedes earlier HID-pending statements. Ordered direction checks can now be repeated using the self-paced graphical calibration.

The field router now carries laptop192.168.8.130 and Pi192.168.8.175 on SSIDbbbb. The dashboard at http://127.0.0.1:8767/ is the normal setup/test workflow. Its latest disarmed link trial accepted200/200 frames,41 FC samples disarmed, roll1437–1553, and no arming blockers during reception (`work/console/trial-20260929T014706.json`).

Owner requested a GUI arming button and indoor operation without GPS fix. Explicit preparation writes only RAM: GPS Rescue allowArmingWithoutFix=ON (MSP225), then failsafe DROP (MSP76). Both read back, and the GPS arming blocker cleared. No EEPROM-write command is used. Original payloads are in ignored private `work/console/fc-failsafe-before-arm.json`; Restore reapplies them over USB. A full FC power-cycle reloads saved settings too. The temporary profile remains active for repeated tests until restore/power-cycle; prepare again afterward. GPS hardware itself remains enabled.

The separate arming receiver accepts centred roll/pitch/yaw, minimum throttle and AUX1 only; low ARM must precede high, accepted-control loss250ms latches stop, high lasts at most approximately2s plus scheduling, and10 low-ARM frames are sent at exit. An initial five-frame run stopped on timeout before ARM-high. The next run accepted152 frames including ARM-high, then10 disarm frames. With FC USB unplugged, the owner confirmed motors started and stopped automatically. Evidence `work/console/trial-20260929T014903.json`. Actual arming is owner-observed; no USB armed-state trace exists for that run. Flight control and full failsafe qualification remain out of scope of this test.

See [Control Room instructions](CONTROL-ROOM.md). Normal stick tests continue to hold every AUX low; only the explicit separate SA arming test permits ARM-high.
