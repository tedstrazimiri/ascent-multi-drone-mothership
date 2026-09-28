# Verification record

2026-09-28 initial software preparation. Physical first-boot results are recorded below.

- 13 unit tests passed: command examples, SBUS packing boundaries, invalid channel rejection, authenticated-message tamper rejection, stale/replayed/reordered control rejection, source ownership, deadman and timeout latching.
- Localhost control smoke test passed: 50 accepted synthetic snapshots and loss latch after sender stopped.
- Two independent synthetic RTSP paths passed: H.264 at 640×360, ten frames decoded from each. All test processes stopped afterward.
- Raspberry Pi OS Lite and MediaMTX arm64/amd64 downloads passed pinned SHA-256 checks.
- User confirmed one initial FPV and later expansion to two, Industry VRX and GT Pro VTX on the bench. Owner confirms Industry and standard VRX share hardware; Pro is a new Rockchip-based revision. This identity is owner-supplied, not from physical board inspection.
- SD image personalization, physical write/readback, first boot, SSH and Pi service operation are separate steps. Their final results will be appended below.

Not yet verified: actual HDMI capture, UVC, Pi encoder throughput, physical UART voltage/baud/pinout, SBUS input/output direction and loss behavior, joystick mapping, FC configuration, RF link, internet/VPN, latency under load, autonomous failsafe or flight operation.

## Prepared image checks

- Personalized Raspberry Pi OS image: 3,061,841,920 bytes. Base compressed image and both MediaMTX builds match their pinned vendor hashes.
- Boot bundle includes 160 ARM64 package files from authenticated APT repositories, resolved using the stock image's dpkg status. Solver reported 160 new packages, zero upgrades and zero removals. No packages installed on the laptop.
- Bundled source, offline installer, package checksums and firstboot video readiness probe inspected. FAT payload and all personalized boot files read back byte-for-byte. Linux root partition remained identical to the stock image before first boot.
- Cloud-init user configuration passed the Raspberry Pi schema. The bundled cloud-init network schema omits Wi-Fi definitions; network configuration instead passed an isolated Netplan generation into NetworkManager profiles. Host networking was not changed.
- Laptop SSH alias resolves to the intended hostname, user, dedicated private key, strict host checking and separate pinned known-hosts file. Wi-Fi credentials copied privately from the current laptop profile; Ethernet DHCP also configured.
- All shell scripts passed bash syntax checks; Python source compiled. Host systemd verification can only inspect syntax because Pi-specific executable paths are absent on the laptop; actual service startup remains a Pi first-boot check.
- User authorized replacing the inserted Pi SD card. Its SD identity and capacity were checked separately from the NVMe system disk; the write plan is private and rechecks both immediately before writing.

Physical SD write and full readback PASSED. Ubuntu administrator authentication was completed locally. Exactly 3,061,841,920 bytes were written and read back with SHA-256 `f03490dc0a08d500cf79a1d439d7bbbcfcd31802849d6e56b00a3ed6e76e6f58`. Both card partitions were unmounted after completion. The SD is ready to move into the Pi. Physical first boot, SSH and service startup remain pending.

Write guard checks passed against the actual plan: the NVMe target, an incorrect SD identity and a changed capacity were all rejected before any write.

## Physical Pi first boot and LAN checks — passed

Verified 2026-09-28 after the owner booted the prepared SD card.

- `ascent-pi` resolves and connects through its existing strict, pinned SSH host key. The observed address is `192.168.1.104`, reached through onboard `wlan0`; Ethernet and the USB Wi-Fi adapter were not used by this test. Effective SSH configuration enables public keys and disables password/root login.
- Device reports Raspberry Pi 4 Model B Rev 1.2, 2 GB configured RAM, aarch64. This identifies the running board but does not resolve its membership in the inventory's original two-Pi batch.
- Unattended `ascent-firstboot` exited successfully and wrote the provisioning marker at `2026-09-28T21:58:45Z`. `dpkg --audit` was empty. MediaMTX and `ascent-video@fpv1` were enabled and running with zero restarts; no systemd services were failed.
- Startup publishes labelled synthetic H.264 at 1280×720, 30 fps. The laptop opened a temporary authenticated SSH RTSP tunnel, decoded 90 frames and saved a frame showing the synthetic label. This confirms Pi-to-laptop transport, not VRX HDMI capture.
- During the video test, the laptop sent 239 authenticated synthetic channel snapshots over LAN UDP; the Pi JSON-only receiver accepted all 239. Its watchdog latched loss after sender shutdown. No UART/GPIO was opened or driven. The temporary receiver, SSH tunnel and temporary key were removed afterward.
- Pi temperature after the tests was 42.8 °C and `get_throttled` returned `0x0`. This short test is not a thermal or sustained-throughput qualification.
- UART is enabled and `/dev/serial0` currently resolves to `ttyS0`; the kernel command line has no serial console. No GPIO electrical compatibility or SBUS timing was tested.
- USB enumeration found the attached RTL8812AU Wi-Fi adapter but no UVC capture device. Listed V4L2 devices were onboard codec/ISP devices; their existence is not a camera feed or an encoder-throughput test.

Cloud-init reported `degraded done`, no errors, and one recoverable warning: missing `cc_netplan_nm_patch`. The installed cloud-init package configuration references that module, but the file is absent; `dpkg -V cloud-init` reported no modified package files. Networking and relay provisioning succeeded. The warning remains recorded; cloud-init was not cleaned or rerun, and its configuration was not changed.

Private local evidence: `work/pi-firstboot-verification.json`, `work/pi-control-smoke.jsonl`, and `work/pi-synthetic-video.png`. Next: identify/connect HDMI capture and verify the Ascent UART/SBUS interfaces and loss behavior. Physical control, RF, FC behavior, internet/VPN and end-to-end latency remain unverified.

## Capture connection check — USB device not detected

Later on 2026-09-28, the owner reported powering the VRX and connecting its HDMI output to a capture adapter attached to the Pi. Repeated SSH checks still showed only the external RTL8812AU Wi-Fi adapter, with no capture USB device or UVC video node. A bounded 45-second USB/video udev monitor observed no connection events. No USB enumeration error or undervoltage condition was found. The adapter's model and USB data connection remain unresolved; reconnecting it directly to another Pi USB-A port is the next step. No capture configuration was guessed or enabled; the labelled synthetic stream remains active.

Independently, Pi `h264_v4l2m2m` encoded 90 synthetic 1280×720 frames successfully, and ffprobe decoded/count-verified all 90. This proves the hardware encoder can operate on generated frames, not that the absent capture device works or that sustained capture/encode latency is acceptable. The temporary encoded file was deleted. Check summary: `work/pi-capture-check.json`.
