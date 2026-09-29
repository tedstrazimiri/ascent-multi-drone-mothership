# Latency audit — 2026-09-29

**Historical audit, now followed by an active sprint:** see [current measurements and changes](LATENCY-SPRINT-2026-09-29.md). The findings below describe the earlier session; its capture-rate and control-protocol proposals remain unimplemented.

## Verified live

- Dashboard initially used HLS. One browser sample had playhead15.563929s, latest seekable point16.2s and buffered end15.999999s. Separation to the seekable edge was636ms, **not** a measurement of camera-to-screen latency. Camera/RF/capture/encoding delay is additional and unmeasured.
- Saved WebRTC through Link → Video → Save player. Browser decoded1280×720 with readyState4, pausedfalse, advancing playback. MediaMTX recorded established UDP peer connections and H264 reading. No control session started or firmware/publisher setting changed during this audit. The earlier250-frame arming session count is historical, not this audit's output.
- Pi20-ping sample while video was running: min2.086 / mean2.515 / max3.751ms;0/20loss. Short LAN sample only, not sustained jitter or WAN performance.
- Alfa wlan1:5GHz5180MHz, signal−26dBm; reported negotiated RX780/TX866.7Mbps. These are PHY rates, not throughput. USB capture negotiated480Mbps and Alfa5000Mbps.
- Pi load average0.66/1.04/0.68 and throttled=0x0 at inspection. No evidence here of CPU saturation or thermal/voltage throttling.
- Publisher: MJPEG1280×720@30 → h264_v4l2m2m1Mbps → local RTSP/TCP. H264 High profile, no B-frames. The encoder is already hardware accelerated.
- Capture advertises MJPEG720p60 but only raw YUYV720p10. Advertising60 does not prove60 distinct frames from this HDMI source or sustainable60fps encoding. Current pipeline remains30fps.

## Priority changes

1. **WebRTC for control viewing; HLS as compatibility fallback.** Already selected in private persisted dashboard settings. Keep UDP media transport where possible. Multiple dashboard viewers consume separate outgoing streams; use one active player when measuring.
2. **Measure and bound capture/encoding queues.** At30fps each frame interval is33.3ms. Current FFmpeg input-thread queue capacity is four packets; capacity does not prove four frames are constantly queued. The hardware encoder exposes buffer pools too; buffer count is not a latency measurement. Test a queue policy that discards old *unencoded* frames when overloaded, then benchmark720p60 vs720p30. Do not indiscriminately drop H264 reference frames. Keep B-frames off. Shorter GOP principally improves startup/recovery, not necessarily steady-state frame delay. Lowering bitrate below the current1Mbps is not the first fix without congestion evidence.
3. **Redesign the control protocol for WAN use.** relay/bench.py currently requests and waits for a receiver challenge before each joystick snapshot; nominal scheduling is50Hz. On a50ms RTT path this serial exchange caps update rate at roughly20Hz before other overhead. It samples the joystick *after* receiving the challenge, so this primarily limits update cadence; it is not correct to add a whole RTT to every sample's age. relay/arm_test.py additionally sleeps20ms after each exchange. Future design: session authentication plus independent fixed-rate latest-input sending, sequence/anti-replay protection and bounded receiver-verifiable freshness. Receiver should apply newest valid control, never drain a stale backlog. Retain loss/disarm behavior; do not mask latency by simply enlarging timeouts. No control protocol change deployed by this audit.
4. **Reduce network jitter under load.** Prefer wired Pi/router when practical; otherwise keep the field5GHz connection. Reserve headroom and prioritize small RC packets over video. Current shortLAN measurements suggest video buffering is a larger immediate problem than propagation through Wi-Fi. Test sustained video plus RC and p95/p99, not just average ping. Future Starlink/VPN paths need separate testing, including whether media takes a directUDP path or a distant relay.
5. **Consider capture/encoder hardware only after stage measurements.** Current USB device exposes MJPEG/YUYV, not nativeH264 input, so this setup cannot merely set codec copy. A demonstrably low-delay HDMI encoder could replace USBMJPEGdecode/re-encode on the Pi; generic H264 capture hardware is not automatically low latency. Native compressed-IP output from this Industry VRX remains unproven.

SBUS serialization in the current implementation is25bytes×12bits/100000=3ms. The unknown Ascent internal SBUS/RF handling and USB input cadence still need measurement; changing SBUS baud or removing inversion is not a valid shortcut. A hardware-timed SBUS interface with its own watchdog can improve output consistency, but cannot remove video buffering.

## Measurement sequence

1. Point the FPV camera at a millisecond counter/flashing target. Record both the target and displayed receiver image in the same high-frame-rate phone recording. Compare direct VRXHDMI against the relayed WebRTC display to isolate the added relay delay. Repeat enough transitions to see jitter; phone/display frame timing sets uncertainty.
2. Measure stick-switch/input edges against FC channel reception separately, with props removed. Video of a responding motor confounds control delay with mechanical response and video delay. FC USB polling itself has a sampling interval; use appropriate timing instrumentation for precise measurements.
3. Repeat while video is busy, then with controlled delay/loss in a software-only transport test, then the real field/WAN path. Record median,p95,p99,dropouts and maximum stale-command age.

No total glass-to-glass latency or improved stick-to-FC latency has yet been measured in this audit. WebRTC playback is verified, not flight suitability.

## Primary references

- [MediaMTX browser playback](https://mediamtx.org/docs/read/web-browsers): HLS is higher latency than WebRTC.
- [MediaMTX configuration](https://mediamtx.org/docs/references/configuration-file): HLS buffering and UDP/TCP WebRTC transport.
- [MediaMTX WebRTC](https://mediamtx.org/docs/features/webrtc-specific-features): UDP connectivity and B-frame compatibility.
- [GStreamer queue](https://gstreamer.freedesktop.org/documentation/coreelements/queue.html): explicit old-buffer dropping policy for a possible future pipeline.
- [Pi4 specifications](https://www.raspberrypi.com/products/raspberry-pi-4-model-b/specifications/): H264 hardware encoder specification;720p60 still needs this pipeline's verification.
- [CADDX Ascent VRX](https://wiki.caddxfpv.com/en/Ascent-HD-Series/Receiver-Unit/Ascent-VRX): advertised best-case35ms and supported decode modes are not a measurement of this full relay.
