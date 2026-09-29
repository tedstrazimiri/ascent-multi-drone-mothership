# GT Pro six-pin harness to GEPRC TAKER H743

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

Current readback confirms Serial/SBUS on UART2, UART1 MSP + DisplayPort, and compiled SBUS option 4103. Receiver initialization reports 18 channels, but RXLOSS and zero RX rate remain: this is not yet a working Ascent RC link. Use `serialrx_inverted = OFF` for standard inverted SBUS; the protocol driver already applies normal SBUS inversion. `sbus_baud_fast = OFF` selects standard 100000 baud. See the matching [2026.6.2 SBUS driver](https://github.com/betaflight/betaflight/blob/2026.6.2/src/main/rx/sbus.c).

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

## Remaining ground-side interface

The manuals confirm a separate SBUS lead at the VTX/FC end. They do not establish conversion of arbitrary UART input at the VRX into SBUS output at the GT Pro. Selecting UART passthrough is a data-mode selection, not proof of such conversion. The earlier UART-mode recommendation must be read with this limit.

For the planned SBUS route, provide a verified SBUS source to the VRX's SBUS input and observe the GT Pro output/FC channels. The Pi's current ordinary TX/RX wiring is not an SBUS source: standard SBUS requires inverted 100000-baud 8E2 and compatible electrical levels. The independent output interface, VRX voltage, passthrough behavior and loss response still need bench verification. No physical RC output has been enabled.

The owner specifically reaffirmed the VRX's dedicated SBUS pin. Use it for this route rather than relying on undocumented UART-to-SBUS conversion. The Pi receives channel values over IP, so it must generate SBUS frames and the appropriate electrical waveform. `relay.protocol.sbus_frame` already packs frames offline; that is separate from a timed, inverted physical output. PL011 with a suitable inversion/interface stage or a suitable MCU can provide the latter. Merely moving the current Pi TX lead to the VRX SBUS pin is not a verified interface.

Cached Industry guide SHA-256: `64167274f6f595dfe065efc33ec65954b29fc5b9eb838a0a6ed65d562e767eec`; GEPRC guide: `a1832f0a528179e1f295f907bd7aa035a539d87660b2226b1d99b793887f92bb`. Relevant diagrams were rendered and visually inspected.
