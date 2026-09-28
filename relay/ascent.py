"""Offline codec for the supplied menu-command examples. No serial I/O."""
import argparse

KEYS = {'up': (0, 0), 'down': (1, 0), 'left': (2, 0), 'right': (3, 0),
        'confirm': (4, 0), 'back': (7, 0)}

def frame(command, payload):
    if not 0 <= command <= 255 or len(payload) > 65535:
        raise ValueError('invalid command or length')
    # Big-endian length and checksum match the examples; >255 checksums need hardware confirmation.
    return (b'\xfe\xef' + bytes([command]) + len(payload).to_bytes(2, 'big')
            + payload + (sum(payload) & 0xffff).to_bytes(2, 'big') + b'\r\n')

def parse(data):
    if len(data) < 9 or data[:2] != b'\xfe\xef' or data[-2:] != b'\r\n':
        raise ValueError('invalid framing')
    n = int.from_bytes(data[3:5], 'big')
    if len(data) != n + 9:
        raise ValueError('length mismatch')
    payload = data[5:5+n]
    if int.from_bytes(data[5+n:7+n], 'big') != sum(payload) & 0xffff:
        raise ValueError('checksum mismatch')
    return data[2], payload

def main():
    p = argparse.ArgumentParser(description=__doc__)
    g = p.add_mutually_exclusive_group(required=True)
    g.add_argument('--key', choices=list(KEYS))
    g.add_argument('--parse', help='hexadecimal packet copied from documentation or capture')
    a = p.parse_args()
    if a.key:
        key, press = KEYS[a.key]
        print(frame(0x22, bytes([0x40, key, press, 0])).hex(' ').upper())
    else:
        cmd, data = parse(bytes.fromhex(a.parse))
        print(f'command=0x{cmd:02X} length={len(data)} payload={data.hex(" ")}')

if __name__ == '__main__':
    main()
