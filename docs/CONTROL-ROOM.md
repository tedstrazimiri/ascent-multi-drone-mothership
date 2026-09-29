# Ascent Control Room

Open <http://127.0.0.1:8767/> or launch **Ascent Control Room** from the laptop's app menu. This is the normal setup workflow. It listens only on laptop loopback. Install/reinstall with `python3 scripts/install-console.py`; it does not start RC output or enable login autostart.

## Live console

The default **Live** view puts FPV video first. The right-hand control deck moves below the video on narrow screens. Icon tabs open Live, TX15 input, Calibration and Link settings; icons have accessible names and tooltips. No output starts on page load.

- **ARM**: two-second, idle-throttle SA arming test. **Start arm test** automatically prepares dependencies. **Start again** repeats it.
- **STICKS**: 30/60/90-second calibrated stick test, all AUX low.
- **LINK**: four-second synthetic roll check, all AUX low.
- **STOP**: stops the current test. An additional Stop bar appears on other tabs or when the primary controls scroll out of view. Escape also stops an active test and exits expanded view.

Video opens automatically when the source playlist is available. Power pauses/resumes playback, the circular arrow reconnects the player, and the corner icon expands the video while keeping test controls accessible. One player is mounted at a time; setup tabs suspend it. Availability checks follow MediaMTX session redirects on the configured source only, retry after source loss and do not emit RC traffic. “Stream available” reports the source, not proof that the browser has decoded a frame.

FC state, voltage and RX bars come from USB readback. Missing/disconnected data shows unknown or dashes. PI RTT is the last measured network round trip, not video latency; use Link → Check to refresh it. Format and bitrate in the video footer are configured targets, not measured quality. Full events remain available in the collapsed bottom activity bar.

The layout adapts to phone-sized viewports, but the service still binds to laptop loopback only. This update does **not** expose RC control to other devices on the LAN.

## Controller and calibration

The reference is RadioMaster TX15 in USB joystick mode, Mode 2. The controller picture and input bars follow the actual Linux HID device. SA high means its highest reported channel value, not necessarily physical up. Current mapping: axes0/1/2/3 = roll/pitch/throttle/yaw; SA is axis5, high+32767.

**Calibrate → Begin calibration** walks through roll, pitch, yaw, throttle and SA. Move only the requested control and click Next at your own pace. Nothing is transmitted. Finish SA at the desired enable end. Calibration saves only after the final step; Cancel keeps the previous mapping.

## Link settings

The field Pi is currently **192.168.8.175** on `bbbb`; laptop192.168.8.130, gateway192.168.8.1. Addresses are DHCP. Save a changed Pi address here, then Check. SSH uses the existing pinned `ascent-pi` identity; credentials are not shown in the page.

**Prepare relay** deploys the finite receivers and a private shared key. Repeat after a Pi reboot; its key is in `/run`. This starts no RC output. The connection check compares the local and Pi keys before showing Prepared.

Select HLS or WebRTC playback and bitrate here. Apply bitrate restarts the publisher. Restart video restarts both video services. Live opens one embedded player automatically. Capture USB reconnects now cause the publisher to retry even when FFmpeg exits successfully.

The FC USB connection supplies actual channel, battery and armed-state feedback. Release FC USB before opening Betaflight, then Connect FC USB when done. Normal monitoring is read-only; the explicitly selected indoor preparation temporarily changes the two settings described below.

## Stick test

With props removed, connect FC USB, set throttle fully down and SA to the saved high/enable position. Live → STICKS → Start test sends four live stick channels for30/60/90 seconds. Every AUX stays low. Lower SA, press Stop, or press Escape to end it. A disconnected dashboard stops the sender after3 seconds; the Pi independently stops accepting control after250ms of source loss. There is no automatic restart.

The 4-second link check sends a small synthetic roll motion with throttle/AUX low. It does not arm. FC bars are direct readback, not a copy of transmitted values.

## Indoor SA arming test — no reboots

Open **Live → ARM**, or go directly to <http://127.0.0.1:8767/#live>. Older #arming links also open this mode.

1. Keep props removed. Click **Start arm test**. Start checks/prepares the Pi receiver and key automatically, then verifies or applies indoor FC settings over USB when needed.
2. Follow the large prompt: connect the TX15 if missing, lower throttle, and move SA low/off. No RC output starts until the initial conditions are met. The first indoor setup needs FC USB; you can leave it connected for feedback or unplug it afterward while keeping the FC powered.
3. When the prompt turns green and says **SA → HIGH**, move SA high. An early SA-high movement keeps ARM off and asks for SA low again; it no longer forces a restart.
4. SA low or **Stop / disarm** ends the test. The Pi also lowers ARM automatically after approximately two seconds. Click **Start again** for another attempt. Every arm cycle needs a new click and a fresh low-to-high switch sequence.

Start allows up to90 seconds for setup/inputs, then a60-second switch-test window. Only ARM-high has the two-second limit. Output remains centred sticks/minimum throttle, with only AUX1 variable. No automatic rearming. Browser loss and network loss still stop output. USB unplugged means actual FC armed state is unavailable; observe the motors/OSD.

**Link → Indoor profile → Restore flight settings** restores both original payloads live over FC USB. Neither preparation, repeat tests nor restore requires a laptop, Pi or FC reboot. A partial/failed restore clears the ready state until recovery, preserving the original backup.

Preparation checks the FC ARM range, backs up failsafe and GPS Rescue settings, enables `gps_rescue_allow_arming_without_fix`, verifies GPS blocker clearance, then sets DROP failsafe. These are RAM-only changes with no EEPROM write or tune change. Verified preparation survives a console service restart; reconnecting FC USB rechecks the actual settings. If the FC loses power, reconnect USB and Start will reapply indoor settings. A power-cycle happens to reload saved FC settings, but is not part of the normal workflow.

The owner confirmed a successful SA motor start and automatic stop on2026-09-29 before this usability update. The update was checked using automatic preparation, zero-frame waiting/cancellation, live restore/reprepare and tests for early switch movement and USB reconnection. It did not repeat the physical motor test.

## Local state and maintenance

- Service: `systemctl --user status ascent-console.service`; launcher starts it when needed.
- Saved UI settings/calibration: ignored `local-console.json`.
- Private key, FC settings backup and finite trial evidence: ignored `work/console/`.
- Source: `relay/console.py`, `relay/fc.py`, `relay/arm_test.py`, `web/`.
- Verification: `python3 -m unittest discover -s tests -v`.

At a console restart, verified indoor preparation is retained and checked against the FC when USB is connected. An incomplete preparation or restore is recovered from its original backup. Do not save unrelated Betaflight changes to flash while the temporary indoor profile is active; restore first.

## Offline UI preview

Run `python3 scripts/preview-console.py` and open <http://127.0.0.1:8768/> for layout and interaction checks without hardware. The banner and video pattern explicitly mark simulation. This standalone fixture imports no hardware/control/SSH modules; its actions only change in-memory sample data. It is not installed as a persistent service and does not alter saved production settings.
