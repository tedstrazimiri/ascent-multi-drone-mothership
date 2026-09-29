# Current physical control experiment

2026-09-29: Owner confirms VRX UART mode **ELRS TT**, common VRX/Pi ground, and props removed. Owner explicitly declined voltage measurement; signal-level compatibility remains unverified. The camera/OSD path works. The FC is configured for standard SBUS on UART2, with AETR channel mapping and ARM on AUX1 high.

## UART result

Pi GPIO14 / physical pin 8 was connected to VRX RX. Four finite CRSF trials at 420000, 115200, 400000 and 416666 baud each sent 195–196 fixed-disarmed channel frames over four seconds. Each trial collected 74 FC status/channel observations over USB. All observations were disarmed; no channel movement appeared. The FC's first four reported channels remained `[1500,1500,1500,885]` in MSP roll/pitch/yaw/throttle order.

This fails to demonstrate UART-to-SBUS conversion in the tested configuration; it does not establish which link stage rejected the data or prove that the hardware lacks that feature. No Ascent management commands were sent. CRSF framing follows the [TBS specification](https://github.com/tbs-fpv/tbs-crsf-spec/blob/main/crsf.md); that specification does not establish Ascent's electrical levels or configured rate.

## Prepared direct SBUS probe

`relay.sbus_probe` builds inverted 100000-baud 8E2 on GPIO14 with pigpio DMA-timed pulses. Each submission is one 25-byte, 3 ms frame, ending idle low. No repeating waveform or background daemon is used. Duration defaults to four seconds and cannot exceed ten; normal termination stops waves and leaves GPIO14 as input with pull-down. A killed sender cannot leave an indefinite repeat queue. This is a fixed-disarmed bench test, not a flight-qualified control output.

Two test snapshots alternate roll 816/1168 once per second; pitch/yaw stay 992, throttle and all AUX stay 172. The module accepts no arbitrary live channel input. It never arms or sends motor commands. [SBUS framing reference](https://github.com/bolderflight/sbus).

The private pigpio library was source-built and installed on the Pi. Its initialization check returned version 79 with GPIO14 still ALT0; no SBUS frame or pin write was made. There is no pigpio service, FIFO listener or network daemon. Source commit `c33738a320a3e28824af7807edafda440952c05d`; archive SHA-256 `805c34565986102adb0b10782ad4e6917815bf1369fb4e364f157c9f06e5cbc5`. The optional [installer](../scripts/install-pigpio-bench.sh) verifies this hash and installs only the private library/license/source identifier. It requires the Pi's compiler, make, curl and sudo; these were present on this bench Pi.

**Awaiting owner wiring confirmation:** move the VRX end of the Pi pin 8 / GPIO14 lead from **VRX RX** to **VRX SBUS**, retaining common ground. The 5 V harness lead stays separate. Do not assume the wire moved merely because the software is ready.

After that confirmation, with a concurrent USB monitor verifying the FC stays disarmed, the explicit bench invocation on the Pi is:

```bash
cd /opt/ascent-relay
sudo python3 -m relay.sbus_probe --seconds 4 --transmit --sbus-wired
```

Without `--transmit`, the default is a dry run. `--check-driver` initializes the library without pin writes. No RC service starts at boot. Returning to UART later requires restoring GPIO14 ALT0 and moving the lead back to VRX RX; do not switch modes silently.

The host test suite passes 19 tests, including independently decoded waveform start/data/parity/stop bits, channel boundaries and fixed-low throttle/AUX values. Actual output timing at the connector, VRX-to-VTX SBUS transfer, live joystick calibration and end-to-end loss behavior remain unverified. The previous authenticated IP receiver is still JSON/SBUS-hex only; it has not been connected to physical output.
