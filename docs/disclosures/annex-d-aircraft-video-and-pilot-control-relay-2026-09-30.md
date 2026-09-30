**ANNEX D | PRIOR INVENTIONS AND INTELLECTUAL PROPERTY**

# System and Method for Relaying Aircraft Video and Pilot Control

Inventor: The undersigned    Original development: 2025  
Disclosure prepared 30 September 2026

## 1  Summary of the disclosed system

The system connects a ground operator to a small first-person-view aircraft through an intermediate relay intended for carriage by a larger aircraft. It combines a ground console, network transport, relay processor and paired radio interfaces. Pilot inputs and received video become bounded control-channel outputs, browser video and diagnostic records. The subsystem is independently usable on the bench; carrier airframes and suppression payloads remain outside its boundary. Intended users are pilots and test operators developing civilian wildfire-suppression applications.

## 2  Technical problem

Controllers and video receivers expose different electrical and software interfaces. Network delay, stale commands and frozen images can obscure whether displayed information and control inputs remain usable. Separate configuration tools and measurements make it difficult to associate an aircraft link with its operator, verify channel delivery and distinguish transport observations from demonstrated flight performance.

## 3  System and method

1. **Configure the link.** Associate controller calibration, aircraft-link identity and video profile with the relay setup. Map USB controller axes and switches into channel values. The operator explicitly starts a bounded test after its input conditions are satisfied; calibration itself transmits no control output.

2. **Relay the video.** Receive the aircraft camera signal through the paired radio receiver, capture its HDMI output through a USB adapter, and encode the captured frames as H.264. A local media service supplies browser playback over the field network. The console reports decoded-frame activity and receive-stage statistics, including interruptions.

3. **Validate and deliver control.** Sample pilot inputs after a receiver-issued challenge and authenticate complete channel snapshots. The receiver checks link identity, challenge age, increasing sequence and the held enable condition, with one operator per run. Accepted snapshots produce finite SBUS channel frames for the paired radio and aircraft flight controller. Source loss latches a stop requiring deliberate restart. Stick tests hold auxiliary channels low; a separate idle-throttle arming test has a bounded activation interval.

4. **Preserve and interpret evidence.** Retain calibration settings, trial records and exported timing reports for review. Local USB flight-controller readback supplies channel observations separately from transmitted commands. Browser statistics describe receive-stage behavior. The operator reviews these records before repeating or revising a test; displayed video and network timing do not establish end-to-end performance.

<!-- PAGE BREAK: begin page 2 before section 4. -->

## 4  Position in the operational development chain

The subsystem contributes between mission definition and field evaluation by integrating interfaces, exercising bounded control and preserving measurements for review. Airborne carriage and additional independent aircraft links are intended extensions. Optional remote backhaul and carrier telemetry remain outside the implemented local relay.

```text
[Define mission] -> [Configure] -> [Bench validate] -> [Field use*] -> [Review]
                         ^                                                 |
                         +---- Operator-led revision ----------------------+
                         |
                         v
+----------------------- RELAY SUBSYSTEM ------------------------+
| Control: [Calibrate] -> [Authenticate / freshness] -> [SBUS]   |
| Video:   [HDMI capture] -> [H.264 encode] -> [Browser]         |
| Records: [Local FC readback] + [Timing samples] -> [Reports]   |
+----------------------------------------------------------------+
                                 |
                                 v
+--------------------- OUTPUTS AND RECORDS ----------------------+
| [Channels]   [Video / warnings]   [Settings / test records]    |
+----------------------------------------------------------------+

* Intended field stage; airborne operation is not demonstrated.
  Optional, planned interfaces: remote backhaul and carrier telemetry.
```

Figure 1. Relay boundary, development lifecycle and operator-led review. Control and video are parallel paths; the feedback loop represents review and revision, not autonomous adaptation.

## 5  Illustrative operation

For illustration, an operator conducts a disarmed stick test while viewing camera video. Accepted snapshots move the observed roll channel. If network interruption exceeds the configured control-loss interval, the receiver latches its stop and ends output. A video freeze is reported separately. The operator reviews the trial record and timing report before deliberately restarting; this example does not establish aircraft behavior during an actual radio outage.

## 6  Subject matter disclosed

The disclosed subject matter is the coordinated combination of calibration mappings, aircraft-link identifiers, authenticated channel snapshots, receiver freshness and sequence checks, finite SBUS output, captured-video delivery and reviewable test records. The interfaces connect these mechanisms into a relay workflow with explicit operator initiation and restart, while keeping commanded values, observed controller responses and video-delivery measurements distinguishable.

## 7  Development status and scope

Project records document one working bench link, browser video, calibrated control transport and bounded tests. Airborne integration, simultaneous operation of two aircraft, remote backhaul, an independent hardware watchdog and suppression actuation remain intended. Capture reconnects and wireless interruptions are unresolved; full camera-to-screen delay, stick-to-controller delay and flight failsafe behavior remain unqualified. Inventorship and the 2025 development year are declarations of the undersigned. The implementation evidence reviewed is dated September 2026 and does not establish that every disclosed feature existed in 2025.
