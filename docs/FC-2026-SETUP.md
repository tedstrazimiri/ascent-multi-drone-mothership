# TAKER H743 configuration after SBUS firmware flash

Verified 2026-09-28 local / 2026-09-29 UTC. The owner flashed Betaflight **2026.6.2** on **GEPRC_TAKER_H743**. USB MSP reports API 1.48 and compiled SBUS option 4103. The owner explicitly requested FC setup and applying the old flight tune as a starting point.

## Saved configuration and readback

| Connection/setting | Verified result |
|---|---|
| UART1 | MSP + VTX MSP/DisplayPort, function mask 131073 |
| UART2 | Serial RX only, mask 64; SBUS |
| Receiver mode | RX_SERIAL enabled; RX_MSP and RX_UDP disabled |
| SBUS | Standard rate; fast mode off; half-duplex off; `serialrx_inverted = OFF` |
| Channel order | AETR1234, matching the backup; actual HID axes still need calibration |
| OSD | MSP, HD, observed canvas 53 × 20; saved layout restored |
| UART4 | UBLOX GPS, 57600 baud; M10 connected/configured, no fix indoors |
| Motors | Saved DSHOT600, bidirectional DShot and reversed-yaw mixer restored; no motor command sent |
| Failsafe | Saved GPS-RESCUE policy, STAGE2 switch, require GPS fix retained; behavior untested |
| Modes | Saved AUX1 high arm; AUX2 high Angle/middle Horizon; AUX5 high Failsafe |
| Sensors | MPU6000 selected, ICM42688P also detected, DPS310 barometer; saved accelerometer calibration restored |

The driver's normal SBUS input is already inverted; `serialrx_inverted = OFF` does not mean electrically uninverted input. [Matching driver](https://github.com/betaflight/betaflight/blob/2026.6.2/src/main/rx/sbus.c).

CLI serial commands now accept names such as `UART2`. MSP serial identifiers also changed: on this build UART1/2/4 are 51/52/54, rather than the old 0/1/3. Final verification uses the [matching serial enumeration](https://github.com/betaflight/betaflight/blob/2026.6.2/src/main/io/serial.h). An initial readback assertion using old numeric IDs failed; no serial configuration was changed by that failed read. The corrected read confirms all three masks.

## Saved flight tune migration

Active profile 0 and rate profile 0 retained. All **105 shared-name settings in profile 0** match the saved full 4.5.1 dump after reboot; all four rate profiles match the backup. Restored dynamic notch/RPM/D-term filters, feedforward, I-term settings, battery sag compensation, simplified tuning sliders, dynamic idle and 4 kHz PID-loop selection.

| Axis | P | I | D base / maximum | Feedforward |
|---|---:|---:|---:|---:|
| Roll | 35 | 63 | 30 / 30 | 156 |
| Pitch | 37 | 67 | 30 / 30 | 162 |
| Yaw | 35 | 63 | 0 / 0 | 156 |

The old firmware stored the peak as `d_*` and the base as `d_min_*`; the new firmware stores base `d_*` and peak `d_max_*`. This tune had equal base/peak, so both remain 30 on roll/pitch. `simplified_dmax_gain = 0` maps to `simplified_d_max_gain = 0`. Compare [4.5.1 initialization](https://github.com/betaflight/betaflight/blob/4.5.1/src/main/flight/pid_init.c) and [2026.6.2 initialization](https://github.com/betaflight/betaflight/blob/2026.6.2/src/main/flight/pid_init.c).

Dynamic idle remains 2000 rpm. New `motor_idle = 500` preserves the old active dynamic-idle startup cap of 5% (`dyn_idle_start_increase = 50`), whose units changed by a factor of ten. Previously separate static idle was 3%; the new shared parameter cannot independently preserve both values. This choice preserves the active dynamic-idle setup. See [old mixer initialization](https://github.com/betaflight/betaflight/blob/4.5.1/src/main/flight/mixer_init.c) and [new mixer initialization](https://github.com/betaflight/betaflight/blob/2026.6.2/src/main/flight/mixer_init.c).

Saved GPS Rescue hover throttle 1300, angle limit 60 degrees and throttle bounds 1100–1700 map to the new shared `ap_*` settings; cruise speed remains 900 cm/s. Removed standalone rescue PID parameters and removed Absolute Control/I-term-limit settings were not guessed. New control algorithms and settings without an old equivalent retain new defaults. Thus this is a migration of the saved starting tune, not proof of identical flight response. The existing GPS-Rescue policy was retained, not flight-tested. Board orientation and motor direction still need physical verification.

## Evidence and remaining receiver test

- Original complete 4.5.1 backup: `work/fc-backup-20260929T032146Z/`.
- Fresh 2026.6.2 baseline before changes: `work/fc-postflash-backup-20260929T033756Z/`.
- Exact accepted commands/responses: `work/fc-2026-sbus-setup.cli`, `work/fc-2026-sbus-setup-responses/`, `work/fc-2026-tune-migration.cli`, `work/fc-2026-tune-migration.json`, `work/fc-2026-tune-responses/`.
- Final full dump/diff/options/status and SHA-256 manifest: `work/fc-2026-configured-backup/`.
- Automated comparison: `work/fc-2026-setup-verified.json`; final normal MSP read: `work/fc-2026-final-msp.json`.

All configuration commands were accepted, saved and read back after reboot. USB is closed and available to the configurator. No arm, RC override, motor test or Pi GPIO/UART RC output was sent.

The initialized receiver exposes **18 channels**, but runtime RX rate is **0**, and **RXLOSS** remains. These channel values do not prove received SBUS frames. Next: verify a correctly timed, inverted SBUS source and electrical levels at the VRX's dedicated SBUS input; then calibrate HID channels and observe actual FC channel movement and loss response. Ordinary Pi TX/RX wiring alone is still not that interface.


## Bench buzzer mute — 2026-09-29

The owner reported painful repeated beeping. Initially `beeper -RX_LOST` was saved; both motor beacon triggers were already disabled. When beeping recurred, readback confirmed the earlier mute persisted and battery status was OK (21.99 V, 6S). Saved `beeper -ALL`, retaining `beacon -RX_LOST` and `beacon -RX_SET`. Readback after reboot confirms all Betaflight buzzer events and both beacon triggers disabled. This silences audible battery warnings too; the flight failsafe policy and voltage thresholds were not altered. An autonomous ESC buzzer, if present, is separate and has not been reconfigured.

Restore the buzzer selection that existed immediately before the all-event bench mute with:

```text
beeper ALL
beeper -RX_LOST
save
```

Use `beeper ALL` plus `save` to restore all FC buzzer events, including RX loss. Leave motor beacon flags as separately intended. The earlier full configured backup predates this bench mute; current readback/evidence is in ignored `work/fc-bench-mute-*` and `work/fc-bench-mute-verify-*`. Restore intended audible warnings before flight evaluation.

Four subsequent UART trial records contain no FC channel movement and no armed status; bounded Pi CRSF output has now been exercised. The former statement that no Pi serial frame had ever been transmitted describes the earlier setup checkpoint only. Actual SBUS reception and end-to-end control remain unverified.

Complete current bench-muted dump/diff/status/beeper/beacon export with SHA-256 manifest: `work/fc-bench-muted-backup-20260929T041655Z/`. Full dump closing save section verified. CLI exited and USB handle closed.
