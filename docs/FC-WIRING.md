# GT Pro six-pin harness to GEPRC TAKER H743

**Current checkpoint:** the dedicated SBUS path, live HID transport and owner-operated motor start/automatic stop have passed. Pi physical pin 8 / GPIO14 is wired to VRX **SBUS**, not VRX RX. See [project handoff](PROJECT-HANDOFF.md) for current state; the missing-driver section below is historical.

Reviewed 2026-09-28. The owner confirms the Ascent GT Pro is plugged directly into the GEPRC TAKER H7 digital-VTX connector. USB now reports `GEPRC_TAKER_H743`, Betaflight 2026.6.2, after the owner flashed it. The assistant configured and verified receiver/OSD/GPS and migrated the saved tune under the owner's explicit instructions. Documents remain reference evidence. See [current configuration and migration](FC-2026-SETUP.md).

## Manufacturer evidence

CADDX's **Ascent GT PRO Quick Start Guide V1.0**, Connection and FC OSD sections on PDF page 1, labels six wires: VCC, GND, RX, TX, GND, SBUS. It describes the blue/green UART pair as the FC OSD connection and specifies MSP plus VTX (MSP + DisplayPort). The separately titled Industry V1.0 guide shows the same six signals and OSD use.

- [CADDX GT Pro V1.0 manufacturer PDF, mirrored copy](https://manuals.plus/m/eb368fd0564983e1287ff200b9377801f6b1113a0ef9d12eeec52edf71f5df57_optim.pdf)
- [CADDX GT Pro Industry V1.0 manufacturer PDF, dealer-hosted copy](https://fx-drones.com/content/files/ascent_gt_pro_industry_manual_v1.0-94217145.pdf)
- [GEPRC TAKER H743 BT V1.0 manual](https://geprc.com/wp-content/uploads/2025/10/TAKER-H743-BT-FC-Manual.pdf), English PDF pages 2 (Interface definition) and 6 (VTX).

GEPRC's VTX diagram connects the digital unit's SBUS output to R2, its TX to RX1, and its RX to TX1. Its illustrated receiver setup is Serial (Via UART), SBUS, and UART2 Serial RX, alongside UART1 MSP for OSD. This supports the owner's RX2 interpretation. These are signal functions, not pin numbers viewed from an unspecified connector face:

| FC digital-VTX connection | VTX signal / direction | Use |
|---|---|---|
| Positive supply, default 12 V per GEPRC manual | → VCC | Power |
| GND | ↔ GND | Ground |
| RX1 | ← VTX UART TX | OSD/MSP UART receive |
| TX1 | → VTX UART RX | OSD/MSP UART transmit |
| GND | ↔ GND | Ground reference |
| RX2 / R2 | ← SBUS | RC channel input |

The owner-reported harness connection is not an independent continuity or voltage measurement. No extra wire is needed at the FC when that SBUS conductor is populated and connected as shown.

## Betaflight settings for this SBUS path

| Setting | Required value |
|---|---|
| UART1 MSP | Enabled |
| UART1 peripheral | VTX (MSP + DisplayPort) |
| UART1 Serial RX | Disabled |
| UART2 MSP | Disabled |
| UART2 Serial RX | Enabled |
| Receiver Mode | Serial (via UART) |
| Serial Receiver Provider | SBUS |

MSP on the **Ports** page supports the VTX OSD connection. **MSP Receiver Mode** selects a different source of stick/channel data; it does not make an SBUS stream on RX2 into an MSP receiver. A real MSP-RC implementation would need actual MSP RC packets and a proven transport to the FC. The current relay does not provide that implementation.

Post-flash readback confirmed Serial/SBUS on UART2, UART1 MSP + DisplayPort, and compiled SBUS option 4103. Initially the receiver exposed 18 channels but had zero RX rate; later physical SBUS tests established actual reception and channel movement. Use `serialrx_inverted = OFF` for standard inverted SBUS; the protocol driver already applies normal SBUS inversion. `sbus_baud_fast = OFF` selects standard 100000 baud. See the matching [2026.6.2 SBUS driver](https://github.com/betaflight/betaflight/blob/2026.6.2/src/main/rx/sbus.c).

## Historical missing-driver diagnosis, before owner flash

The earlier read-only check, after the owner changed Receiver Mode to Serial on 4.5.1, returned:

- UART1 function mask 131073: MSP and VTX MSP enabled.
- UART2 function mask 64: Serial RX enabled.
- Stored serial receiver provider 2: SBUS.
- RX_MSP disabled and RX_SERIAL enabled: **Receiver Mode is now correct for the SBUS path**.
- MSP_RC returns zero channels. The firmware build-options query includes CRSF (4097) and omits SBUS (4103): **the installed firmware lacks the SBUS receiver driver**.

The driver issue was independent of wiring and RF reception. In Betaflight 4.5.1, compiled receiver drivers are reported by [MSP build information](https://github.com/betaflight/betaflight/blob/4.5.1/src/main/msp/msp_build_info.c); [option IDs](https://github.com/betaflight/betaflight/blob/4.5.1/src/main/msp/msp_build_info.h) distinguish CRSF and SBUS. The SBUS initializer sets its channel count before checking the serial port or receiving RF data. Choosing SBUS in configuration does not add its missing driver. The owner's later 2026.6.2 flash resolved this build issue.

The existing configuration is backed up privately in `work/fc-backup-20260929T032146Z/`: version, status, complete `diff all`, complete `dump all`, and checksummed manifest. Both configuration exports include their closing save section. Full dump is 39,558 bytes. An initial incomplete full-dump capture remains explicitly named `dump-all.partial.txt`; **do not use that partial file for restoration**. CLI exit rebooted the FC, and a subsequent MSP API query verified normal communication resumed. A text configuration backup is not a firmware binary backup or a tested restoration to a different build.

No FC settings were written by the assistant during that diagnosis. Historical private snapshots: `work/fc-after-owner-msp-change.json`, `work/fc-current-serial-ports-v2.json`, `work/fc-serial-sbus-mode-verified.json` and `work/fc-build-options-verified.json`. The former build reported Jan 10 2025, 01:13:49, revision `77d01ba`, Betaflight 4.5.1. These are superseded by the current post-flash evidence.

## Ground-side interface: implemented SBUS, unresolved UART

The manuals confirm a separate SBUS lead at the VTX/FC end. They do not establish conversion of arbitrary UART input at the VRX into SBUS output at the GT Pro. Selecting UART passthrough is a data-mode selection, not proof of such conversion. The earlier UART-mode recommendation must be read with this limit.

The current Pi source generates inverted 100000-baud 8E2 on GPIO14 using pigpio one-shot waveforms. With that lead on the VRX SBUS pin, finite synthetic and live-HID trials produced matching FC channel changes. An ordinary UART byte write would not reproduce this waveform. Signal voltage margins and RF-outage behavior remain unverified; the independent hardware watchdog is future work.

The owner specifically reaffirmed the VRX's dedicated SBUS pin and confirmed moving the wire there. The Pi still has to translate IP channel values into packed SBUS and the timed inverted waveform; the VRX passes that stream through the Ascent link. `relay.protocol.sbus_frame` packs it; `relay.sbus_probe`/`relay.sbus_bench` provide the finite physical bench output. See [SBUS evidence](SBUS-BENCH.md) and the [dashboard workflow](CONTROL-ROOM.md). Earlier failed CRSF UART trials do not invalidate this separately proven SBUS route.

Cached Industry guide SHA-256: `64167274f6f595dfe065efc33ec65954b29fc5b9eb838a0a6ed65d562e767eec`; GEPRC guide: `a1832f0a528179e1f295f907bd7aa035a539d87660b2226b1d99b793887f92bb`. Relevant diagrams were rendered and visually inspected.
