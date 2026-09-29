"""Finite disarmed SBUS experiment on Pi GPIO14. No daemon or RC autostart."""
import argparse
import ctypes as C
import json
import math
import os
from pathlib import Path
import signal
import subprocess
import time

from .crsf_probe import probe_channels
from .protocol import sbus_frame

GPIO = 14
LIBRARY = '/opt/ascent-relay/vendor/pigpio/libpigpio.so.1'


def waveform(channels):
    """Inverted 100000 baud 8E2; (on mask, off mask, microseconds)."""
    levels = []
    for byte in sbus_frame(channels):
        data = [(byte >> bit) & 1 for bit in range(8)]
        logical = [0] + data + [sum(data) % 2, 1, 1]
        levels.extend(1 - bit for bit in logical)
    # Every byte includes both stop bits. End at idle low; no repeat chain.
    pulses = []
    for level in levels:
        on, off = (1 << GPIO, 0) if level else (0, 1 << GPIO)
        if pulses and pulses[-1][:2] == (on, off):
            previous = pulses.pop()
            pulses.append((on, off, previous[2] + 10))
        else:
            pulses.append((on, off, 10))
    return pulses


class Pulse(C.Structure):
    _fields_ = [('on', C.c_uint32), ('off', C.c_uint32), ('delay', C.c_uint32)]


def library():
    lib = C.CDLL(LIBRARY)
    signatures = {
        'gpioCfgInterfaces': [C.c_uint], 'gpioCfgClock': [C.c_uint] * 3,
        'gpioCfgGetInternals': [], 'gpioCfgSetInternals': [C.c_uint32],
        'gpioInitialise': [], 'gpioTerminate': [], 'gpioGetMode': [C.c_uint],
        'gpioSetMode': [C.c_uint] * 2, 'gpioSetPullUpDown': [C.c_uint] * 2,
        'gpioWrite': [C.c_uint] * 2, 'gpioWaveAddNew': [],
        'gpioWaveAddGeneric': [C.c_uint, C.POINTER(Pulse)],
        'gpioWaveCreate': [], 'gpioWaveDelete': [C.c_uint],
        'gpioWaveTxSend': [C.c_uint] * 2, 'gpioWaveTxBusy': [], 'gpioWaveTxStop': [],
    }
    for name, args in signatures.items():
        method = getattr(lib, name)
        method.argtypes = args
        method.restype = None if name == 'gpioTerminate' else C.c_int
    return lib


def checked(function, *args):
    result = function(*args)
    if result < 0:
        raise RuntimeError(f'{function.__name__} failed: {result}')
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument('--transmit', action='store_true')
    mode.add_argument('--check-driver', action='store_true', help='initialize only, no pin writes')
    parser.add_argument('--sbus-wired', action='store_true', help='GPIO14 is on VRX SBUS with common ground')
    parser.add_argument('--seconds', type=float, default=4)
    args = parser.parse_args()
    if not math.isfinite(args.seconds) or not 0 < args.seconds <= 10:
        parser.error('duration must be finite, positive, and at most 10 seconds')
    if args.transmit and not args.sbus_wired:
        parser.error('--transmit requires confirmed SBUS wiring (--sbus-wired)')
    if not (args.transmit or args.check_driver):
        pulses = waveform(probe_channels(0))
        print(json.dumps({'mode': 'DRY RUN', 'gpio': GPIO, 'baud': 100000,
                          'format': 'inverted 8E2', 'frame_us': sum(p[2] for p in pulses),
                          'channels': probe_channels(0), 'pulses': len(pulses)}))
        return
    if os.geteuid() != 0 or 'Raspberry Pi 4 Model B' not in Path('/proc/device-tree/model').read_text():
        raise SystemExit('Hardware mode requires root on the Pi 4')
    uart = subprocess.run(['fuser', '/dev/ttyAMA0'], capture_output=True)
    if uart.returncode != 1:
        raise SystemExit('UART is busy or its ownership could not be checked')

    def stop(signum, frame):
        raise SystemExit('probe interrupted')

    for sig in (signal.SIGTERM, signal.SIGINT, signal.SIGALRM):
        signal.signal(sig, stop)
    lib = library()
    checked(lib.gpioCfgInterfaces, 3)  # Disable both FIFO and socket interfaces.
    checked(lib.gpioCfgClock, 1, 1, 0)  # 1 us samples, PCM clock.
    checked(lib.gpioCfgSetInternals, lib.gpioCfgGetInternals() | (1 << 10))
    initialized = False
    changed_pin = False
    wave_ids = []
    frames = 0
    signal.setitimer(signal.ITIMER_REAL, args.seconds + 4)
    try:
        version = checked(lib.gpioInitialise)
        initialized = True
        before = checked(lib.gpioGetMode, GPIO)
        if args.check_driver:
            print(json.dumps({'driver': version, 'gpio14_mode': before, 'transmitted': False}))
            return
        if before not in (0, 4):  # INPUT or ALT0 (PL011 TX).
            raise RuntimeError(f'GPIO14 has an unexpected mode: {before}')
        for elapsed in (0, 1):
            checked(lib.gpioWaveAddNew)
            pulses = waveform(probe_channels(elapsed))
            buffer = (Pulse * len(pulses))(*(Pulse(*pulse) for pulse in pulses))
            checked(lib.gpioWaveAddGeneric, len(buffer), buffer)
            wave_ids.append(checked(lib.gpioWaveCreate))
        changed_pin = True
        checked(lib.gpioSetMode, GPIO, 0)
        checked(lib.gpioSetPullUpDown, GPIO, 1)  # Pull down = inverted SBUS idle.
        checked(lib.gpioWrite, GPIO, 0)  # Sets output with a low idle level.
        start = time.monotonic()
        print(json.dumps({'state': 'started', 'seconds': args.seconds, 'throttle': 172,
                          'all_aux': 172, 'gpio': GPIO}), flush=True)
        while time.monotonic() - start < args.seconds:
            checked(lib.gpioWaveTxSend, wave_ids[int(time.monotonic() - start) % 2], 0)
            wave_deadline = time.monotonic() + .05
            while checked(lib.gpioWaveTxBusy):
                if time.monotonic() > wave_deadline:
                    raise TimeoutError('One-shot waveform did not finish')
                time.sleep(.001)
            frames += 1
            # Each DMA submission contains ONE 3 ms frame; no indefinite replay.
            time.sleep(.017)
    finally:
        signal.setitimer(signal.ITIMER_REAL, 0)
        if initialized:
            try:
                if changed_pin:
                    lib.gpioWaveTxStop()
                    lib.gpioWrite(GPIO, 0)
                    lib.gpioSetPullUpDown(GPIO, 1)
                    lib.gpioSetMode(GPIO, 0)
                for wave_id in wave_ids:
                    lib.gpioWaveDelete(wave_id)
            finally:
                lib.gpioTerminate()
    print(json.dumps({'state': 'stopped', 'frames': frames, 'gpio14': 'input, pull-down'}), flush=True)


if __name__ == '__main__':
    main()
