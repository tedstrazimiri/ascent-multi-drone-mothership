# Verification record

2026-09-28 software preparation in progress.

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
