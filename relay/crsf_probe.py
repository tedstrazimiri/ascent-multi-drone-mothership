"""Bounded, disarmed CRSF UART probe. No HID, network, arming, or autostart."""
import argparse
import json
import math
import signal
import time
from .protocol import valid_channels

def crc8(data):
    crc = 0
    for byte in data:
        crc ^= byte
        for _ in range(8):
            crc = ((crc << 1) ^ (0xD5 if crc & 0x80 else 0)) & 255
    return crc

def channel_frame(channels):
    if not valid_channels(channels):
        raise ValueError('16 integer channels in 0..2047 required')
    packed = sum(value << (11 * index) for index, value in enumerate(channels))
    body = b'\x16' + packed.to_bytes(22, 'little')
    return b'\xc8\x18' + body + bytes([crc8(body)])

def probe_channels(elapsed):
    # AETR: throttle CH3 and all AUX, including saved ARM AUX1, stay low.
    return [816 if int(elapsed) % 2 == 0 else 1168, 992, 172, 992] + [172] * 12

def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--baud', type=int, choices=[115200, 400000, 416666, 420000], default=420000)
    p.add_argument('--seconds', type=float, default=4)
    p.add_argument('--transmit', action='store_true', help='explicitly transmit on /dev/serial0')
    a = p.parse_args()
    if not math.isfinite(a.seconds) or not 0 < a.seconds <= 10:
        p.error('duration must be finite, positive and at most 10 seconds')
    if not a.transmit:
        print(json.dumps({'mode': 'DRY RUN', 'baud': a.baud,
                          'channels': probe_channels(0), 'frame_hex': channel_frame(probe_channels(0)).hex()}))
        return
    from pathlib import Path
    model = Path('/proc/device-tree/model').read_text().rstrip('\0')
    if 'Raspberry Pi 4 Model B' not in model or Path('/dev/serial0').resolve().name != 'ttyAMA0':
        raise SystemExit('Requires this Pi 4 PL011 UART configuration')
    import serial
    def stop(signum, frame):
        raise SystemExit('probe interrupted')
    signal.signal(signal.SIGTERM, stop)
    count = 0
    # A separate process wall-clock alarm also bounds a stalled loop/write.
    signal.signal(signal.SIGALRM, stop)
    signal.setitimer(signal.ITIMER_REAL, a.seconds + 2)
    try:
        with serial.Serial('/dev/serial0', a.baud, bytesize=8, parity='N', stopbits=1,
                           timeout=0, write_timeout=.1, exclusive=True,
                           xonxoff=False, rtscts=False, dsrdtr=False) as port:
            start = time.monotonic()
            print(json.dumps({'state': 'started', 'baud': a.baud, 'seconds': a.seconds,
                              'throttle': 172, 'all_aux': 172}), flush=True)
            while time.monotonic() - start < a.seconds:
                packet = channel_frame(probe_channels(time.monotonic() - start))
                if port.write(packet) != len(packet):
                    raise RuntimeError('short UART write')
                count += 1
                # No catch-up bursts, repeat queue, or background output thread.
                time.sleep(.02)
            port.reset_output_buffer()
    finally:
        signal.setitimer(signal.ITIMER_REAL, 0)
    print(json.dumps({'state': 'stopped', 'frames': count, 'baud': a.baud}), flush=True)

if __name__ == '__main__':
    main()
