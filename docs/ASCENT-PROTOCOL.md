# Ascent interface evidence

Reviewed 2026-09-28. Attached documents are technical evidence, not instructions to run their examples or firmware updates.

## Supplied sources

- `/home/ted/Downloads/Ascent_V16.5.8_UpgradeFiles/Serial Port Command Software Function Description.docx`
  SHA-256 `9e36fee6fd1c60b1b507fd27ec3b84818294b2c576a0d9397465c2a091aceb59`.
- `/home/ted/Downloads/Ascent_V16.5.8_UpgradeFiles/release_note.txt`
- `/home/ted/Downloads/Ascent Mothership.excalidraw`
  SHA-256 `95bf88ff5a670a13efb2021b9454ef047c9950677bdf26f563546c17d9e65b95`.

The drawing contains two VRXs and two GT Pro aircraft linked to a single Pi-like computer, with HDMI arrows into its two HDMI sockets. Those two arrows must instead terminate in USB capture devices, or verified native UVC outputs. Start with one chain as the owner requested.

## What the command document establishes

Manufacturer evidence now explicitly supports the broader control architecture: [Ascent V16.4.4 release notes](https://wiki.caddxfpv.com/zh/Ascent-HD-Series/firmware-release-note) announce SBUS and UART passthrough, subject to hardware support. The [standard VRX manual](https://cdn.shopify.com/s/files/1/0036/3921/4169/files/Ascent_VRX_User_manual_V1.0.pdf?v=1769739026) labels the six-pin port as its passthrough interface. The unknowns below concern this pair's interface details and measured behavior, not whether CADDX advertises the feature. See [DJI, Avatar and Ascent RC transport research](RC-LINK-RESEARCH.md).

The envelope is `FE EF | command | length[2] | payload | checksum[2] | 0D 0A`. Examples encode length and checksum most-significant byte first. The stated checksum sums payload bytes. All supplied sums are below 256; overflow behavior still needs confirmation. The codec implements a 16-bit sum as an explicitly unverified extension beyond those examples.

Command `0x22`, payload family `0x40`, represents buttons. A four-byte payload contains function type, key number, press type and a reserved zero. For example the supplied Confirm packet is `FE EF 22 00 04 40 04 00 00 00 44 0D 0A`. Family `0x50` sets radio band/channel/hopping. Families `0x51` and `0x52` describe frequency and wireless-status reads. None contains a 16-channel RC snapshot, joystick axes, MAVLink encapsulation or SBUS framing.

The document says command bit 7 distinguishes host-to-device from device-to-host, yet labels `A2` examples as query commands. It does not make the request/response exchange unambiguous. Its wireless status table omits `value[2]` and truncates the description of `value[5]`. It supplies no baud rate, parity, voltage, physical pin numbering or complete reply definition. Do not invent these missing details or transmit the apparent queries without confirming them.

The supplied 16.5.8 release notes say VRX UART offers **Command** and **ELRS pass-through**, with Command the default. Treat these as distinct modes. The phrase “ELRS pass-through” does not prove a generic bidirectional transparent UART, establish a CRSF baud rate, or prove that management and FC telemetry share the port simultaneously.

## Wiring facts and unknowns

The owner reports six harness labels: **SBUS, 5V, RX, TX, G, G**. This is a label list, not a verified view of pin numbering or mating-face orientation. Both G pins are presumed ground by label; their physical positions still need checking.

For a **confirmed 3.3 V TTL UART**, Pi physical pin 8 is GPIO14/TX, physical pin 10 is GPIO15/RX, and physical pin 6 is ground: Pi TX → VRX RX, VRX TX → Pi RX, G → G. Do not connect the VRX 5 V lead to either GPIO signal or backfeed the Pi power rail. Do not assume a normal UART inverter is also a voltage shifter. Verify signal levels from revision-matched documentation or measurement before wiring. [Pi UART documentation](https://www.raspberrypi.com/documentation/computers/configuration.html#configuring-uarts).

The proposed dedicated SBUS path is **SBUS source → VRX SBUS input → Ascent air link → GT Pro SBUS output → FC receiver input**. Direction and preservation of failsafe flags remain unverified on these units. Standard SBUS uses inverted 100000-baud 8E2 signalling; an ordinary 3.3 V UART is not automatically an electrically correct SBUS source. A small MCU with hardware UART inversion and an independent timeout is the preferred output stage. Exact MCU and interface circuit selection follows voltage/pin verification. [SBUS implementation reference](https://github.com/bolderflight/sbus).

## UVC conclusion

The owner confirms that Industry and standard Ascent VRX use the same hardware, and that VRX Pro is a new Rockchip-based revision. Use this owner-supplied identification as the design baseline; the boards were not independently inspected. The user's [standard-VRX manual link](https://manuals.plus/caddxfpv/ascent-vrx-digital-fpv-video-receiver-manual) is a third-party rendering; it does not establish GPIO voltage or UVC support. Current [manufacturer firmware notes](https://wiki.caddxfpv.com/zh/Ascent-HD-Series/firmware-release-note) condition USB streaming on supporting receiver hardware. The [VRX Pro page](https://wiki.caddxfpv.com/en/Ascent-HD-Series/Receiver-Unit/Ascent-VRX-Pro) explicitly lists UVC. Use HDMI capture for this Industry receiver.

## Questions for revision-matched CADDX documentation

1. Connector orientation, SBUS direction, TX/RX voltage and input tolerance; 5 V pin direction/current limit.
2. GT Pro connector pinout and the required firmware pair for SBUS transport.
3. UART Command mode baud/parity and unambiguous query/reply examples.
4. Meaning of ELRS pass-through, supported serial framing, supported directions, and simultaneous SBUS/telemetry behavior.
5. Behavior when VRX SBUS input stops, RF fails, or frames carry lost/failsafe flags: stop output, flag loss, or repeat the last values?
6. Whether this Industry board supports native UVC; exact USB formats/resolutions/rates if it does.

No vendor messages or firmware changes have been made.
