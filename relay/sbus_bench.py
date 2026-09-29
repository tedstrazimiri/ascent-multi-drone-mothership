"""Authenticated, finite Pi SBUS bench receiver. AUX stays low; no arming support."""
import argparse
import ctypes as C
import ipaddress
import json
import math
import os
from pathlib import Path
import signal
import socket
import subprocess
import time

from .protocol import Guard, decode, encode, valid_channels
from .sbus_probe import GPIO, Pulse, checked, library, waveform


def validate_bench_channels(channels):
    if (not valid_channels(channels) or any(not 172 <= value <= 1811 for value in channels[:4])
            or channels[4:] != [172] * 12):
        raise ValueError('bench requires four bounded stick channels and every AUX fixed at 172')


class Output:
    """One finite 3 ms waveform per accepted snapshot, never repeated by DMA."""
    def __init__(self, validator=validate_bench_channels):
        self.lib = None
        self.pin_changed = False
        self.validator = validator

    def __enter__(self):
        if os.geteuid() != 0 or 'Raspberry Pi 4 Model B' not in Path('/proc/device-tree/model').read_text():
            raise RuntimeError('Physical output requires root on the Pi 4')
        if subprocess.run(['fuser', '/dev/ttyAMA0'], capture_output=True).returncode != 1:
            raise RuntimeError('UART busy or ownership check failed')
        lib = library()
        checked(lib.gpioCfgInterfaces, 3)
        checked(lib.gpioCfgClock, 1, 1, 0)
        checked(lib.gpioCfgSetInternals, lib.gpioCfgGetInternals() | (1 << 10))
        checked(lib.gpioInitialise)
        self.lib = lib
        try:
            mode = checked(lib.gpioGetMode, GPIO)
            if mode not in (0, 4):
                raise RuntimeError(f'Unexpected GPIO14 mode {mode}')
            self.pin_changed = True
            checked(lib.gpioSetMode, GPIO, 0)
            checked(lib.gpioSetPullUpDown, GPIO, 1)
            return self
        except BaseException:
            self.close()
            raise

    def send(self, channels):
        self.validator(channels)
        lib = self.lib
        if lib is None:
            raise RuntimeError('Output not initialized')
        checked(lib.gpioWaveAddNew)
        pulses = waveform(channels)
        buffer = (Pulse * len(pulses))(*(Pulse(*pulse) for pulse in pulses))
        checked(lib.gpioWaveAddGeneric, len(buffer), buffer)
        wave_id = checked(lib.gpioWaveCreate)
        try:
            checked(lib.gpioWrite, GPIO, 0)
            checked(lib.gpioWaveTxSend, wave_id, 0)
            deadline = time.monotonic() + .05
            while checked(lib.gpioWaveTxBusy):
                if time.monotonic() >= deadline:
                    raise TimeoutError('SBUS one-shot waveform did not finish')
                time.sleep(.001)
        finally:
            lib.gpioWaveTxStop()
            lib.gpioWaveDelete(wave_id)

    def close(self):
        if self.lib is not None:
            try:
                if self.pin_changed:
                    self.lib.gpioWaveTxStop()
                    self.lib.gpioWrite(GPIO, 0)
                    self.lib.gpioSetPullUpDown(GPIO, 1)
                    self.lib.gpioSetMode(GPIO, 0)
            finally:
                self.lib.gpioTerminate()
                self.lib = None

    def __exit__(self, *exc):
        self.close()


def receive(args, key, output):
    guard = Guard('fpv1')
    frames = 0
    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sock:
        sock.bind((args.bind, args.port))
        sock.settimeout(.02)
        print(json.dumps({'state': 'waiting', 'address': sock.getsockname(),
                          'output': 'GPIO14 SBUS BENCH', 'all_aux': 172}), flush=True)
        deadline = time.monotonic() + args.seconds
        while time.monotonic() < deadline:
            if guard.expired(time.monotonic()):
                print(json.dumps({'state': 'loss_latched', 'frames': frames}), flush=True)
                break
            try:
                packet, peer = sock.recvfrom(2049)
            except socket.timeout:
                continue
            if peer[0] != args.peer:
                continue
            try:
                message = decode(packet, key)
                now = time.monotonic()
                if message.get('type') == 'hello':
                    reply = guard.challenge(message, peer, now)
                    sock.sendto(encode(reply, key), peer)
                    continue
                validate_bench_channels(message.get('channels'))
                channels = guard.accept(message, peer, now)
            except (ValueError, KeyError, TypeError):
                if guard.latched:
                    print(json.dumps({'state': 'loss_latched', 'frames': frames}), flush=True)
                    break
                continue
            output.send(channels)
            frames += 1
            if frames == 1 or frames % 50 == 0:
                print(json.dumps({'state': 'accepted', 'frames': frames,
                                  'channels': channels, 'seq': message['seq']}), flush=True)
    print(json.dumps({'state': 'stopped', 'frames': frames}), flush=True)
    return frames


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--key', required=True)
    p.add_argument('--bind', required=True)
    p.add_argument('--peer', required=True)
    p.add_argument('--port', type=int, default=14601)
    p.add_argument('--seconds', type=float, default=30)
    p.add_argument('--transmit', action='store_true')
    p.add_argument('--sbus-wired', action='store_true')
    a = p.parse_args()
    for value in (a.bind, a.peer):
        address = ipaddress.ip_address(value)
        if address.version != 4 or address.is_unspecified or address.is_multicast:
            p.error('use concrete unicast IPv4 addresses')
    if not math.isfinite(a.seconds) or not 0 < a.seconds <= 120 or not 1024 <= a.port <= 65535:
        p.error('finite duration 0..120 seconds and unprivileged UDP port required')
    key = Path(a.key).read_bytes()
    if len(key) != 32:
        p.error('32-byte private key required')
    if not a.transmit:
        print('DRY RUN: no socket, GPIO, or UART opened. Requires --transmit --sbus-wired.')
        return
    if not a.sbus_wired:
        p.error('confirm GPIO14 goes to VRX SBUS using --sbus-wired')

    def stop(signum, frame):
        raise SystemExit('bench receiver interrupted')

    for sig in (signal.SIGTERM, signal.SIGINT, signal.SIGALRM):
        signal.signal(sig, stop)
    signal.setitimer(signal.ITIMER_REAL, a.seconds + 4)
    try:
        with Output() as output:
            receive(a, key, output)
    finally:
        signal.setitimer(signal.ITIMER_REAL, 0)


if __name__ == '__main__':
    main()
