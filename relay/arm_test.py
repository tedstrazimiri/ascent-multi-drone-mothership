"""Explicit props-off SA arming test: fixed sticks, one rising edge, two-second cap.

This separate receiver never accepts flight throttle or stick commands. Normal
stick testing continues to reject every ARM-high packet in sbus_bench.
"""
import argparse
import ipaddress
import json
from pathlib import Path
import signal
import socket
import time

from .joystick import Joystick, validate_mapping
from .protocol import Guard, decode, encode, valid_channels
from .sbus_bench import Output

OFF = [992, 992, 172, 992] + [172] * 12
ON = OFF[:4] + [1811] + OFF[5:]
DRONE = 'fpv1-arm-test'


def validate_arm_channels(channels):
    if not valid_channels(channels) or channels not in (OFF, ON):
        raise ValueError('Arming test accepts centred sticks, minimum throttle and only AUX1')


class ArmGate:
    def __init__(self):
        self.first_low = None
        self.low_frames = 0
        self.armed_at = None
        self.finished = False

    def expired(self, now):
        if self.armed_at is not None and now - self.armed_at >= 2:
            self.finished = True
        return self.finished

    def accept(self, channels, now):
        validate_arm_channels(channels)
        if self.expired(now):
            raise ValueError('Arming test ended; no automatic rearm')
        if channels == OFF:
            if self.armed_at is not None:
                self.finished = True
            if self.first_low is None:
                self.first_low = now
            self.low_frames += 1
        elif self.armed_at is None:
            if self.first_low is None or now - self.first_low < .75 or self.low_frames < 20:
                self.finished = True
                raise ValueError('SA must remain off during the initial receiver recovery period')
            self.armed_at = now
        return channels


class SwitchIntent:
    """An early high remains OFF until the operator returns low and raises again."""
    def __init__(self):
        self.off_since = None
        self.raised = False
        self.finished = False
        self.phase = 'waiting'
        self.message = 'Lower SA and throttle to begin.'

    def sample(self, throttle, selected, now):
        if self.finished:
            return OFF
        if self.raised:
            if not selected or throttle > 210:
                self.finished = True
                self.phase, self.message = 'stopping', 'Disarming…'
                return OFF
            return ON
        if throttle > 210:
            self.off_since = None
            self.phase, self.message = 'waiting', 'Lower throttle fully; ARM stays off.'
        elif selected and (self.off_since is None or now - self.off_since < 1):
            self.off_since = None
            self.phase, self.message = 'waiting', 'Move SA low/off, then wait for Ready.'
        elif not selected:
            if self.off_since is None:
                self.off_since = now
            if now - self.off_since >= 1:
                self.phase, self.message = 'ready', 'Ready — move SA high. Motors may spin for two seconds.'
            else:
                self.phase, self.message = 'recovering', 'Hold SA low for a moment…'
        else:
            self.raised = True
            self.phase, self.message = 'live', 'ARM requested · automatic cutoff in two seconds'
            return ON
        return OFF


def log(**entry):
    print(json.dumps(entry), flush=True)


def receive(args, key, output):
    guard, gate = Guard(DRONE), ArmGate()
    frames = 0
    reason = 'window_ended'
    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sock:
        sock.bind((args.bind, args.port))
        sock.settimeout(.02)
        log(state='waiting', output='ARM TEST ONLY', max_arm_seconds=2)
        end = time.monotonic() + args.seconds
        try:
            while time.monotonic() < end:
                now = time.monotonic()
                if guard.expired(now):
                    reason = 'source_loss'
                    break
                if gate.expired(now):
                    reason = 'arm_limit' if gate.armed_at is not None and now - gate.armed_at >= 2 else 'sa_low'
                    break
                try:
                    packet, peer = sock.recvfrom(2049)
                except socket.timeout:
                    continue
                if peer[0] != args.peer:
                    continue
                try:
                    message = decode(packet, key)
                    if message.get('type') == 'hello':
                        sock.sendto(encode(guard.challenge(message, peer, now), key), peer)
                        continue
                    validate_arm_channels(message.get('channels'))
                    channels = guard.accept(message, peer, now)
                except (ValueError, KeyError, TypeError):
                    continue
                try:
                    output.send(gate.accept(channels, now))
                except ValueError as exc:
                    log(state='interlock', message=str(exc))
                    reason = 'interlock'
                    break
                frames += 1
                if frames == 1 or frames % 25 == 0 or channels == ON and frames % 5 == 0:
                    log(state='accepted', frames=frames, arm_requested=channels == ON)
        finally:
            # Explicit low ARM frames also handle loss of the network sender.
            for _ in range(10):
                output.send(OFF)
                time.sleep(.02)
            log(state='stopped', frames=frames, disarm_frames=10, reason=reason)
    return frames


def sender(args, key):
    mapping = json.loads(Path(args.mapping).read_text())
    validate_mapping(mapping)
    joystick = Joystick(args.joystick)
    stopping = False
    def stop(*unused):
        nonlocal stopping
        stopping = True
    signal.signal(signal.SIGTERM, stop)
    signal.signal(signal.SIGINT, stop)
    sent = 0
    intent = SwitchIntent()
    last_phase = None
    start = time.monotonic()
    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sock:
        sock.connect((args.host, args.port))
        sock.settimeout(.1)
        def transmit(channels):
            nonlocal sent
            sock.send(encode({'type': 'hello', 'drone': DRONE}, key))
            reply = decode(sock.recv(2049), key)
            if reply.get('type') != 'challenge' or reply.get('drone') != DRONE:
                raise ValueError('Invalid arming-test challenge')
            sock.send(encode({**reply, 'type': 'control', 'channels': channels, 'deadman': True}, key))
            sent += 1
        try:
            while not stopping and time.monotonic() - start < args.seconds:
                try:
                    channels, selected = joystick.snapshot(mapping)
                except KeyError:
                    time.sleep(.02)
                    continue
                output = intent.sample(channels[2], selected, time.monotonic())
                if intent.phase != last_phase:
                    log(state='guidance', phase=intent.phase, message=intent.message)
                    last_phase = intent.phase
                transmit(output)
                if intent.finished:
                    log(state='enable_released')
                    break
                time.sleep(.02)
        except (OSError, ValueError) as exc:
            log(state='link_stopped', message=str(exc))
        finally:
            for _ in range(5):
                try:
                    transmit(OFF)
                    time.sleep(.02)
                except (OSError, ValueError):
                    break
            joystick.close()
            log(state='sender_stopped', sent=sent)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('mode', choices=['sender', 'receiver'])
    parser.add_argument('--key', required=True)
    parser.add_argument('--host')
    parser.add_argument('--bind')
    parser.add_argument('--peer')
    parser.add_argument('--port', type=int, default=14602)
    parser.add_argument('--seconds', type=float, default=30)
    parser.add_argument('--joystick')
    parser.add_argument('--mapping')
    parser.add_argument('--props-off', action='store_true')
    args = parser.parse_args()
    if not 0 < args.seconds <= 70 or not 1024 <= args.port <= 65535 or not args.props_off:
        parser.error('Explicit --props-off and a finite 0..70 second window are required')
    for value in ([args.host] if args.mode == 'sender' else [args.bind, args.peer]):
        address = ipaddress.ip_address(value)
        if address.version != 4 or address.is_unspecified or address.is_multicast:
            parser.error('Concrete unicast IPv4 required')
    key = Path(args.key).read_bytes()
    if len(key) != 32:
        parser.error('32-byte key required')
    if args.mode == 'sender':
        sender(args, key)
    else:
        def stop(*unused):
            raise SystemExit('Arming receiver interrupted')
        for sig in (signal.SIGTERM, signal.SIGINT, signal.SIGALRM):
            signal.signal(sig, stop)
        signal.setitimer(signal.ITIMER_REAL, args.seconds + 4)
        try:
            with Output(validator=validate_arm_channels) as output:
                receive(args, key, output)
        finally:
            signal.setitimer(signal.ITIMER_REAL, 0)


if __name__ == '__main__':
    main()
