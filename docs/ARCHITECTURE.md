# Video and control architecture

## One FPV first

Use one bound VRX/GT Pro pair, one video capture path and one dedicated channel/control identity. Bring up the second pair only after measuring the first. Multiple paired receivers are the conservative design for independently piloted concurrent FPVs; multi-aircraft control or simultaneous video from one VRX has not been established. Switching a single pilot's selection does not provide continuing manual control to another airborne aircraft. Separate pilots or proven onboard autonomy are needed for concurrent flight.

The two antennas on one Ascent receiver belong to its radio system. They are not independent per-aircraft links. Receivers must also be tested for mutual interference when co-located. Do not treat advertised RF range as tested relay range.

## Video

HDMI capture options should be selected by **actual USB output format and latency**, not the advertised HDMI input resolution. First enumerate `v4l2-ctl --list-formats-ext` with the actual VRX HDMI mode. A capture device that accepts 1080p60 may only deliver 1080p30 or MJPEG over USB. Native H.264 output permits `-c:v copy`, avoiding a decode/encode cycle on the Pi. MJPEG or YUYV input needs encoding; the prepared pipeline offers `h264_v4l2m2m` for a separately verified Pi kernel/driver and `libx264` for the initial synthetic demonstration. [FFmpeg V4L2 reference](https://ffmpeg.org/ffmpeg-devices.html#video4linux2_002c-v4l2).

Pi 4 H.264 encoding is specified at 1080p30. Do not promise two 1080p60 encodes or assume listing an encoder proves it operates. Start with one 720p30 compressed stream, then measure capture, encode, temperature, USB load and viewing delay. A dedicated HDMI-to-H.264 Ethernet encoder is an alternative if capture/encoding is the bottleneck; the Pi can then concentrate on control and telemetry. No unverified capture product has been selected for purchase. [Pi 4 codec specification](https://magazine.raspberrypi.com/articles/raspberry-pi-4-vs-raspberry-pi-3b-plus).

Raw YUYV422 needs width × height × 2 × frame rate bytes/s: 720p60 is about 110.6 MB/s; 1080p60 is about 248.8 MB/s before USB overhead. That is why format discovery matters. Two capture devices also share Pi resources. Use stable `/dev/v4l/by-id` paths; identical adapters without unique serials may need `/dev/v4l/by-path` and fixed USB sockets.

MediaMTX serves `fpv1` and later `fpv2`. Bench RTSP uses TCP and loopback, reached through SSH. This is easy to verify but TCP loss can cause stalls; it is not the final low-latency WAN choice by default. Compare RTP/UDP inside a VPN, WebRTC and SRT under measured packet loss. SRT retransmission adds its configured latency. RTSP is a session protocol; its media transport and player buffer determine much of the behavior. The application does not infer whether a still/frozen image is current. A production viewer needs capture-time/frame-age indication and a loss interlock. [MediaMTX configuration](https://mediamtx.org/docs/references/configuration-file).

An initial test setting of 3 Mbit/s per 720p30 stream is a starting point, not a quality or link guarantee. Two such streams with 30% planning headroom require about 7.8 Mbit/s **sustained mothership upload**, plus other traffic. Measure achievable upload and bursts, then limit video below the sustainable rate so control traffic is not queued behind video.

## Control and telemetry

Do not tunnel joystick events or raw bytes through a reliable backlog. Read USB HID, calibrate axes, form a full current channel snapshot at 50 Hz, and discard stale/reordered snapshots at the Pi. Bind each pilot key/session to a drone ID and output port. The provided bench receiver requires a fresh receiver-generated challenge, authentication, increasing sequence and held deadman. A 150 ms challenge lifetime bounds a full challenge-response round trip without requiring clock synchronization. A 250 ms gap latches loss; those are experimental bench limits, not flight acceptance thresholds. Restart is deliberate; reconnect cannot silently resume output.

The current sink logs JSON and packed SBUS bytes. The future MCU must enforce its own timeout if the Pi hangs, stops scheduling, disconnects USB, or resets. It must start inactive and never repeat a cached armed snapshot indefinitely. Validate the real Ascent/FC result for loss at each hop. Decide between stopped SBUS and marked failsafe frames only after observing which is preserved over the radio and recognized by the selected FC. Do not invent a universal “neutral” channel pattern for a flying aircraft.

SBUS is an RC channel stream, not bidirectional telemetry. FC OSD through MSP DisplayPort is also not automatically a ground-station telemetry stream. Betaflight, INAV and ArduPilot require different FC configurations. Establish the actual FC, receiver input, UART transport and telemetry protocol before enabling a bridge. The Ascent Command port is receiver management; it should not be assigned to arbitrary MAVLink until transparent transport is proven.

Mothership MAVLink/SiK remains a distinct route and authority domain. SiK is appropriate for telemetry/control messages, not these video streams. Use distinct MAVLink system IDs and explicit routing if later bridging multiple vehicles. A common ground-station laptop does not mean Mission Planner or Kite can natively control an Ascent SBUS FPV via USB HID. The dedicated mapper owns that input; avoid two apps simultaneously interpreting the same radio as different vehicle controls.

## Internet backhaul

Use a router for DHCP/NAT and a switch for port fan-out. A switch alone does not supply Internet service. Starlink's default IPv4 service uses CGNAT; do not depend on inbound port forwarding. Use an outbound-established VPN, such as WireGuard through a reachable hub or a managed mesh VPN, on the laptop and Pi/router. Only authenticated peers should reach the relay and MAVLink endpoints. The UDP lab includes authentication but no encryption; use it on loopback/LAN or inside that VPN. [Starlink IP behavior](https://starlink.com/sg/support/article/ac09301b-cef6-a125-c251-856196a77f92).

Starlink hardware, service plan, airborne use eligibility, antenna sky view, power and mass remain design inputs; having Internet on the ground does not settle airborne suitability. Check the actual terminal and service before choosing it as the flight backhaul. [Starlink in-motion information](https://starlink.com/sr/support/article/50e933eb-54f5-1a77-cc85-c6c8325564cf).

Measure glass-to-glass video delay separately from stick-to-FC delay. The control feedback loop includes both directions: joystick uplink + Ascent command hop + aircraft response + Ascent video + capture/encode + WAN downlink + decode/display. Ping measures only one portion, and receiver OSD latency omits downstream capture/WAN/player time. Record median, p95, p99 and longest stall under competing upload and outages. Those measurements decide whether manual FPV piloting is usable; no end-to-end delay or flight fitness has yet been demonstrated.
