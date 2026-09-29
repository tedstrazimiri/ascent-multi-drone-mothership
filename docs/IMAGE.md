# Raspberry Pi image preparation

Target: Pi 4B, Raspberry Pi OS Lite 64-bit Trixie, release 2026-09-15. The base image and MediaMTX 1.21.1 archives are pinned with SHA-256 in `config/downloads.json`. [Official OS downloads](https://www.raspberrypi.com/software/operating-systems/), [MediaMTX release](https://github.com/bluenviron/mediamtx/releases/tag/v1.21.1).

The image builder retains the stock Linux root filesystem and stages a relay bundle on the FAT boot partition. Personalized cloud-init files create user `ted`, hostname `ascent-relay`, SSH keys, DHCP networking and an automatic provisioning service. It starts one synthetic RTSP test stream after installing dependencies. It never auto-starts physical flight control. The personalized image contains Wi-Fi credentials and a unique SSH host key and must be kept private; it is for this one Pi, not redistribution or cloning.

The prepared card includes ARM64 dependencies resolved against the stock image and downloaded from signed Debian/Raspberry Pi repositories, so first boot can install them offline. Provisioning retries after failure. No local Pi screen/keyboard setup should be required, but this must be verified on the physical first boot. The image's UART is enabled with the serial login console disabled. No UART process opens automatically.

The current builder and installer select the full PL011 UART on physical pins 8/10 using `dtoverlay=disable-bt`; onboard Bluetooth is disabled. This was also applied to the running Pi and verified after reboot. The older staged `.img` has not been rebuilt with this change. To repeat the update on that image after boot, run `sudo bash scripts/configure-uart.sh` from the current checkout, then reboot. Changed boot files are backed up; see [bench wiring](BRINGUP.md#pi-uart-preparation-and-wiring).

## Build steps

```bash
python3 scripts/fetch.py raspios mediamtx-arm64 mediamtx-amd64
python3 scripts/build-image.py
python3 scripts/fetch-pi-packages.py
# Rebuild the staged image once more to include the downloaded package bundle.
# Move the first image aside before invoking build-image.py again.
python3 scripts/build-image.py
python3 scripts/personalize-image.py
```

`build-image.py` needs mtools. On this laptop it was extracted without changing system packages into `.cache/mtools` using `apt-get download mtools` and `dpkg-deb -x`. This user-local mtools is host-specific; a different build host should use its own mtools package.

The personalized result is `dist/ascent-relay-pi4-2026-09-15-staged.img`. Build and personalization manifests record hashes and readback results. File preparation is not evidence of a successful SD write, boot or working SSH session.

The flash script takes a private `work/flash-plan.json` containing an exact device, SD CID, byte capacity and image SHA-256. It verifies these again, refuses the system disk, unmounts only the selected card partitions, writes the image, flushes and hashes the complete image-length readback. The user explicitly authorized replacing the inserted Pi SD card; its old content will be erased. No other disk is included.

## Local access

The laptop alias `ascent-pi` uses its own key and pinned Pi host key. No default password or shared login credential is included. The Pi account has local administrative access through this key for unattended management. Private host and client keys never belong in Git or the dashboard log.

Ethernet uses DHCP on the connected router LAN. The builder may also configure the currently active laptop Wi-Fi network privately; it records whether this succeeded without printing credentials. A bare Ethernet switch with no DHCP server needs separate addressing; prefer the portable router for the first boot.

First boot status from this laptop:

```bash
ssh ascent-pi 'cloud-init status --long; systemctl status ascent-firstboot --no-pager; systemctl is-active ascent-mediamtx ascent-video@fpv1'
```

The exact capture device is configured remotely after it is connected and enumerated. Synthetic video is deliberately labelled so it cannot be mistaken for a camera feed.

## Live bench differences and recovery

The original SD write/readback and physical first boot passed; see [VERIFICATION.md](VERIFICATION.md). **The original staged image is not a snapshot of the current bench.** No new image or card was built during the documentation closeout. Rebuilding the image from current source stages that source, but does not automatically copy all live settings or install the separate pigpio dependency.

| Layer | Original image / reusable default | Current bench and recovery reference |
|---|---|---|
| UART | Original staged image predates the PL011 update | Live `disable-bt` overlay selects PL011; current installer/personalizer includes it. `configure-uart.sh` changes require a Pi reboot, unlike routine dashboard tests. |
| Video source | Labelled synthetic `video-fpv1.json` | MacroSilicon MJPEG 720p30 using [capture profile](../config/video-macrosilicon-720p30.json); live target 1 Mbps, reusable profile 3 Mbps. |
| MediaMTX | Loopback-only RTSP | [LAN profile](../config/mediamtx-lan.yml) enables WebRTC/HLS and field/house read CIDRs; apply through [LAN viewer procedure](LAN-VIEWER.md). |
| Publisher unit | Original image predates clean-EOF recovery | Current [unit](../systemd/ascent-video@.service) uses `Restart=always`; installed on live Pi. |
| GPIO dependency | Not provisioned by generic first boot | [install-pigpio-bench.sh](../scripts/install-pigpio-bench.sh) installs the pinned private library on the Pi, with compiler/make/curl prerequisites; no daemon or RC startup. |
| Network | Private first-boot DHCP/selected Wi-Fi setup | Field `ascent-field` on Alfa wlan1 plus house fallback were configured later. Preserve/recreate private NetworkManager profiles; passwords are not in Git. |
| RC receiver/key | No persistent physical RC service | Dashboard Prepare relay deploys receivers and a private key in `/run`; repeat after reboot. No output until an explicit finite test. |
| Laptop UI | Separate from Pi image | `python3 scripts/install-console.py` installs/starts the user-local dashboard and launcher; preserve private `local-console.json` and `work/console/`. |
| FC settings | Separate physical controller | Firmware/tune and saved battery/buzzer changes are not part of the Pi image. Indoor profile is RAM-only; see [FC setup](FC-2026-SETUP.md) and [Control Room](CONTROL-ROOM.md). |

For a replacement card, preserve the private recovery artifacts listed in [PROJECT-HANDOFF.md](PROJECT-HANDOFF.md), then follow the build steps with a newly verified target/write plan. Do not reuse an old device path as proof of card identity or distribute the personalized image. The initial SD-replacement authorization described above records that completed operation; it is not an instruction to erase another device during a later session.

After boot, establish pinned SSH and first-boot readiness, apply the intended live profiles/dependencies above, then verify video and explicit finite control tests separately. `install-pi.sh` preserves existing `/etc/ascent-relay` JSON/YAML configuration and does not start/restart video services itself; `firstboot.sh` explicitly enables the initial video services. A reinstall alone is not a complete restoration or a verified end-to-end test.
