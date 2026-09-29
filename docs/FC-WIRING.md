# GT Pro six-pin harness to GEPRC TAKER H743

Reviewed 2026-09-28. The owner confirms the Ascent GT Pro is plugged directly into the GEPRC TAKER H7 digital-VTX connector. USB reports `GEPRC_TAKER_H743`, Betaflight 4.5.1. Documents are reference evidence; no document commands or firmware procedures were executed.

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

The latest read-only check, after the owner enabled UART2 Serial RX, returned:

- UART1 function mask 131073: MSP and VTX MSP enabled.
- UART2 function mask 64: Serial RX enabled.
- Stored serial receiver provider 2: SBUS.
- RX_MSP feature enabled and RX_SERIAL disabled: **Receiver Mode still needs changing to Serial (via UART)** for the SBUS path.

No FC settings were written by the assistant. Private snapshots: `work/fc-after-owner-msp-change.json` (earlier, before UART2 was enabled) and `work/fc-current-serial-ports-v2.json` (latest).

## Remaining ground-side interface

The manuals confirm a separate SBUS lead at the VTX/FC end. They do not establish conversion of arbitrary UART input at the VRX into SBUS output at the GT Pro. Selecting UART passthrough is a data-mode selection, not proof of such conversion. The earlier UART-mode recommendation must be read with this limit.

For the planned SBUS route, provide a verified SBUS source to the VRX's SBUS input and observe the GT Pro output/FC channels. The Pi's current ordinary TX/RX wiring is not an SBUS source: standard SBUS requires inverted 100000-baud 8E2 and compatible electrical levels. The independent output interface, VRX voltage, passthrough behavior and loss response still need bench verification. No physical RC output has been enabled.

Cached Industry guide SHA-256: `64167274f6f595dfe065efc33ec65954b29fc5b9eb838a0a6ed65d562e767eec`; GEPRC guide: `a1832f0a528179e1f295f907bd7aa035a539d87660b2226b1d99b793887f92bb`. Relevant diagrams were rendered and visually inspected.
