# Latency sprint — 2026-09-29

Resumed at the owner's request after the previous handoff. Current bench: Pi at `192.168.8.175`, VRX powered; **GT Pro/camera, FC and TX15 were not connected for these measurements**. The owner has a monitor displaying the Pi text console, but no separate direct-VRX display/splitter. The VRX disconnected-transmitter screen provides video for receive-stage tests; it cannot establish camera/RF delay or distinct scene-frame rate.

## Delivered

- WebRTC now renders directly in the console through the unmodified MediaMTX 1.21.1 reader. HLS remains the compatibility option; fresh console installs default to WebRTC. Saved preferences are preserved.
- A failed HLS availability probe no longer destroys an otherwise independent WebRTC connection. The reader handles source reconnects. Pausing, changing view/mode, or leaving the page closes the player.
- Live decoded FPS, receive-buffer residence, decode time and selected-media-path RTT. Stopped frame delivery displays a warning over the image; source availability alone is not called live playback.
- **Live → Video timing → Measure 30 seconds**, then **Export JSON**. Reports include sample timestamps, interval statistics, frame drops, freezes, packet loss and median/p95/p99 summaries. Hiding the tab or losing the WebRTC connection marks the run interrupted.
- Reversible **Automatic / Minimum delay** playout choice. Minimum requests `RTCRtpReceiver.jitterBufferTarget = 0` when supported. This is a preference, not a promise of zero delay. It is not persisted or promoted to the default.
- Browser visual target at `/latency-target.html`, and a text-console target deployed with matching SHA-256 to the Pi: `/home/ted/ascent-latency/latency-clock.py`.

Only viewer/diagnostic code was changed. The Pi capture/encoder configuration remains MJPEG 1280×720@30 → hardware H.264, requested 1 Mbps, no B-frames. No RC/SBUS, FC, arming, firmware or Wi-Fi configuration change or physical-control trial was made.

## Measurements and limits

Private evidence is under `work/latency-sprint/`; exported copies also went to the laptop Downloads folder. The report uses deltas of cumulative WebRTC counters, not lifetime averages. Buffer/decode values are unknown when no corresponding frames were emitted/decoded. Percentiles are across roughly one-second interval averages, **not individual frame latency**. Freeze counters may recognize a stall only when delivery resumes. Lost-packet counters may decrease when late packets arrive.

- Laptop → Pi, 150 pings over 30 seconds: **median 18.7 ms, p95 96.5 ms, p99 279 ms, max 383 ms**, 0/150 loss. Mean 31.275 ms. A later ten-ping burst averaged 631.726 ms and peaked at 1356.895 ms, with replies arriving in groups. This differs materially from the earlier session's short 2.5 ms mean sample.
- Both field interfaces report 5 GHz channel 36, with Wi-Fi power saving off. Pi reported −30 dBm and no throttling (`0x0`); laptop later reported −36 dBm. Strong signal and high negotiated PHY rates did not ensure consistent delivery.
- Kernel logs show capture USB disconnect/re-enumeration at 16:57:38, 16:59:01 and 17:00:56 EDT, in addition to earlier events. Video service restarts recovered automatically. Capture runtime PM was `auto`, state `active` when inspected; this does not establish autosuspend as the cause.
- Pi `wlan1` repeatedly retried authentication at 16:59:22, :33 and :47, then associated at 16:59:58. Station statistics subsequently recorded ten beacon losses. At least one SSH request timed out. These are verified connection failures, not a diagnosis of their cause.
- Local Pi RTSP initially produced 91 packets over a three-second media interval. A later read completed with **901 packets over 30 seconds of media** while the browser repeat was unstable. This supports investigating transport ahead of encoder throughput; it is not a delay measurement or proof that capture never stalls.
- Pi → field router, 60 pings: **mean 351.059 ms, max 2536.700 ms**, zero loss. This excludes the laptop Wi-Fi hop and implicates the Pi/router wireless segment in the observed jitter. The specific driver/RF/router/power cause remains unresolved.

The browser runs are sequential and saw changing network/capture conditions. Do not attribute their differences solely to the buffer setting.

| Run (UTC start) | Buffer median / p95 | Decoded FPS median | Freezes | Dropped frames |
|---|---:|---:|---:|---:|
| Automatic, 21:00:38 | 178.9 / 4420.0 ms | 0.0 | 4 | 228 |
| Minimum, 21:02:11 | 62.9 / 113.1 ms | 28.0 | 24 | 187 |
| Automatic repeat, 21:03:39 | 149.8 / 2234.2 ms | 1.0 | 13 | 153 |

The first run had 29 interval samples but only **9** intervals with emitted frames; its buffer distribution excludes the other 20 intervals. The minimum run had 30 samples with emitted frames. The automatic repeat had 30 samples, 17 with emitted frames. Browser decode time was about **0.6–0.7 ms median** across all three runs. The lower buffering in the minimum trial came with frequent freezes, so automatic buffering was restored. No camera-to-screen improvement is claimed.

## Next physical measurement

First establish a stable USB capture and Wi-Fi interval. The owner was asked whether the cabling had been moved during these disconnects; that answer was still pending during initial testing. Inspect the capture cable, port and power path if the setup was untouched. A wired Pi/router comparison can help separate Wi-Fi problems once a cable is available. Do not change capture rate to 60 fps while the 30 fps baseline is unstable.

For the Pi monitor, type this **on its attached console**:

```bash
python3 /home/ted/ascent-latency/latency-clock.py
```

The target runs for ten minutes and restores the terminal on Ctrl+C. It displays elapsed seconds in large digits and flashes at four transitions per second. Updates are 20 Hz (50 ms steps); printed milliseconds do not imply millisecond display accuracy. For finer visual timing, use the browser target on a visible screen and note its displayed refresh interval.

Once the FPV camera/GT Pro is powered, point it at the target. Record **both the original target and the dashboard's received image in the same phone frame**. Subtract displayed elapsed times across at least 30 readable samples, then calculate median/p95/max and count stalls. No synchronization between Pi, laptop and phone clocks is required. Keep the target tab visible if using the HTML version. Props stay removed for the bench setup; this test needs no control session.

Without a separate direct-HDMI observation this measures the full target-to-dashboard path, including the target display and camera/RF chain. It cannot isolate the Pi's added delay. Input-to-FC timing is a separate later test requiring the TX15 and FC feedback.

## Verification and sources

45 Python tests passed; four JavaScript timing-counter tests passed. HTTP checks cover new static assets, MIME types and the restricted selected-Pi signaling origin. Live Chrome decoded the VRX screen over UDP, completed/exported automatic and minimum trials, and visibly reported stalls. Target console rendering and deployed-file checksum passed. The HTML target visibly advanced in Chrome, but its reported update interval varied from 16.7 ms to a later 727 ms average during inspection. Keep it foreground and verify cadence before using it; nominal milliseconds are not display accuracy. Neither target has yet been observed through the FPV camera.

- [W3C WebRTC statistics](https://www.w3.org/TR/webrtc-stats/): cumulative counter definitions and interval derivation.
- [MDN jitterBufferTarget](https://developer.mozilla.org/en-US/docs/Web/API/RTCRtpReceiver/jitterBufferTarget): requested versus actual buffering.
- [MediaMTX WHEP](https://mediamtx.org/docs/read/webrtc): browser/WHEP playback.
- Pinned reader provenance/license: `web/vendor/README.md`.
