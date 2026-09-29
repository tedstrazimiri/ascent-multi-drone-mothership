"""Read Linux USB HID joystick via joydev. Never sends RC output."""
import argparse
import os
import select
import struct
import time

EVENT = struct.Struct('IhBB')

class Joystick:
    def __init__(self, path):
        self.fd = os.open(path, os.O_RDONLY | os.O_NONBLOCK)
        self.axes, self.buttons = {}, {}

    def close(self):
        os.close(self.fd)

    def read(self):
        # Initial events are valid snapshots. No event while a stick is stationary
        # is normal; use FD disconnect detection, not an event-age timeout.
        while select.select([self.fd], [], [], 0)[0]:
            data = os.read(self.fd, EVENT.size)
            if len(data) != EVENT.size:
                raise OSError('joystick disconnected or truncated event')
            _, value, kind, index = EVENT.unpack(data)
            kind &= 0x7f
            if kind == 2:
                self.axes[index] = value
            elif kind == 1:
                self.buttons[index] = bool(value)

    def snapshot(self, mapping):
        self.read()
        channels = [172] * 16
        for i, axis in enumerate(mapping['axes']):
            value = self.axes[axis['index']]
            fraction = (value - axis['min']) / (axis['max'] - axis['min'])
            if axis['invert']:
                fraction = 1 - fraction
            channels[i] = round(172 + max(0, min(1, fraction)) * 1639)
        if 'deadman_axis' in mapping:
            gate = mapping['deadman_axis']
            value = self.axes.get(gate['index'])
            enabled = value is not None and gate['min'] <= value <= gate['max']
        else:
            enabled = self.buttons.get(mapping['deadman_button'], False)
        return channels, enabled

def validate_mapping(mapping):
    axes = mapping.get('axes')
    if type(axes) is not list or len(axes) != 4:
        raise ValueError('bench requires exactly four calibrated axes')
    for a in axes:
        if (type(a) is not dict or not all(type(a.get(k)) is int for k in ('index', 'min', 'max'))
                or not 0 <= a['index'] <= 255 or not -32768 <= a['min'] < a['max'] <= 32767
                or type(a.get('invert')) is not bool):
            raise ValueError('invalid axis calibration')
    if len({a['index'] for a in axes}) != 4:
        raise ValueError('axes must be distinct')
    if ('deadman_button' in mapping) == ('deadman_axis' in mapping):
        raise ValueError('choose exactly one enable button or axis')
    if 'deadman_axis' in mapping:
        gate = mapping['deadman_axis']
        if (type(gate) is not dict
                or not all(type(gate.get(k)) is int for k in ('index', 'min', 'max'))
                or not 0 <= gate['index'] <= 255
                or not -32768 <= gate['min'] < gate['max'] <= 32767
                or gate['index'] in {a['index'] for a in axes}):
            raise ValueError('invalid enable axis or range')
    elif type(mapping['deadman_button']) is not int or not 0 <= mapping['deadman_button'] <= 255:
        raise ValueError('invalid deadman button')

def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('device', help='/dev/input/by-id/...-joystick (not event-joystick)')
    p.add_argument('--seconds', type=float, default=30)
    a = p.parse_args()
    joystick = Joystick(a.device)
    try:
        until = time.monotonic() + a.seconds
        while time.monotonic() < until:
            joystick.read()
            print({'axes': joystick.axes, 'buttons': joystick.buttons}, flush=True)
            time.sleep(.2)
    finally:
        joystick.close()

if __name__ == '__main__':
    main()
