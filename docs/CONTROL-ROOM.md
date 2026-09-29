# Ascent Control Room

Open <http://127.0.0.1:8767/> or launch **Ascent Control Room** from the laptop's app menu. This is the normal setup workflow. It listens only on laptop loopback. Install/reinstall with `python3 scripts/install-console.py`; it does not start RC output or enable login autostart.

## Controller and calibration

The reference is RadioMaster TX15 in USB joystick mode, Mode 2. The controller picture and input bars follow the actual Linux HID device. SA high means its highest reported channel value, not necessarily physical up. Current mapping: axes0/1/2/3 = roll/pitch/throttle/yaw; SA is axis5, high+32767.

**Calibration → Begin calibration** walks through roll, pitch, yaw, throttle and SA. Move only the requested control and click Next at your own pace. Nothing is transmitted. Finish SA at the desired enable end. Calibration saves only after the final step; Cancel keeps the previous mapping.

## Connections

The field Pi is currently **192.168.8.175** on `bbbb`; laptop192.168.8.130, gateway192.168.8.1. Addresses are DHCP. Save a changed Pi address here, then Check connection. SSH uses the existing pinned `ascent-pi` identity; credentials are not shown in the page.

**Prepare relay for control** deploys the finite receivers and a private shared key. Repeat after a Pi reboot; its key is in `/run`. This starts no RC output. The connection check compares the local and Pi keys before showing Prepared.

Select HLS or WebRTC playback and bitrate here. Apply bitrate restarts the publisher. Restart video restarts both video services. Open just one player using Bench test → Open live video. Capture USB reconnects now cause the publisher to retry even when FFmpeg exits successfully.

The FC USB connection supplies actual channel, battery and armed-state feedback. Release FC USB before opening Betaflight, then Connect FC USB when done. Normal monitoring is read-only; the explicitly selected indoor preparation temporarily changes the two settings described below.

## Stick test

With props removed, connect FC USB, set throttle fully down and SA to the saved high/enable position. Start stick test sends four live stick channels for30/60/90 seconds. Every AUX stays low. Lower SA, press Stop, or press Escape to end it. A disconnected dashboard stops the sender after3 seconds; the Pi independently stops accepting control after250ms of source loss. There is no automatic restart.

The 4-second link check sends a small synthetic roll motion with throttle/AUX low. It does not arm. FC bars are direct readback, not a copy of transmitted values.

## Indoor SA arming test

1. Keep props removed and connect the powered FC over USB. Under **Bench test → Test SA arming**, choose **Prepare indoor arming**.
2. Wait for **Indoor setup ready · no GPS fix required**. You may then unplug FC USB while leaving the drone powered.
3. Set throttle fully down and SA low. Click **Start SA arm test**. Hold SA low through the initial receiver recovery period, then move it high when the status says ready.
4. Motors may spin at idle. SA low or **Stop / disarm** sends ARM low. The Pi also automatically lowers ARM after approximately2 seconds of ARM-high. A second rising edge requires a new test. Throttle and other sticks cannot command motion during this test.

USB unplugged means actual FC armed state is unavailable: observe the motors/OSD. The Pi's frame count proves transmission, not reception or arming. The owner confirmed one successful start/automatic-stop trial on2026-09-29.

Preparation reads the exact FC ARM range, backs up failsafe and GPS Rescue settings, enables `gps_rescue_allow_arming_without_fix`, verifies GPS blocker clearance, then sets DROP failsafe. These changes are RAM-only: no EEPROM write and no tune change. They remain for repeat tests. **Restore original flight failsafe** with USB connected restores both payloads. A full FC power-cycle also reloads the original saved settings. Prepare again after a power-cycle or console restart. Merely unplugging USB while battery power remains connected does not restore settings.

The bench arming output is separate from normal stick testing: distinct protocol identity/UDP port, fixed centred sticks, minimum throttle, only AUX1 variable, an initial low period, one rising edge, and ten explicit disarm frames on exit. Software time limits do not qualify the complete system for flight or replace an independent hardware watchdog.

## Local state and maintenance

- Service: `systemctl --user status ascent-console.service`; launcher starts it when needed.
- Saved UI settings/calibration: ignored `local-console.json`.
- Private key, FC settings backup and finite trial evidence: ignored `work/console/`.
- Source: `relay/console.py`, `relay/fc.py`, `relay/arm_test.py`, `web/`.
- Verification: `python3 -m unittest discover -s tests -v`.

At a console restart, an outstanding FC backup is restored when USB is available, then indoor preparation must be selected again. Do not save unrelated Betaflight changes to flash while the temporary indoor profile is active; restore first.
