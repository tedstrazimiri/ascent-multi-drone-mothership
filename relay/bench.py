"""Authenticated UDP control lab. Output is JSON/SBUS hex, NEVER a serial port."""
import argparse
import ipaddress
import json
import math
import os
from pathlib import Path
import secrets
import socket
import time
from .protocol import Guard, decode, encode, sbus_frame
from .joystick import Joystick, validate_mapping

def log(**fields):
    print(json.dumps(fields), flush=True)

def receiver(args, key):
    guard = Guard(args.drone)
    warned = False
    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sock:
        sock.bind((args.bind, args.port))
        sock.settimeout(.02)
        log(state='waiting', sink='JSON ONLY', address=sock.getsockname(), drone=args.drone)
        until = time.monotonic() + args.seconds
        while time.monotonic() < until:
            if guard.expired(time.monotonic()) and not warned:
                log(state='loss_latched', action='no more accepted control; restart required')
                warned = True
            try:
                packet, peer = sock.recvfrom(2049)
            except socket.timeout:
                continue
            if peer[0] != args.peer:
                continue
            try:
                msg = decode(packet, key)
                now = time.monotonic()
                if msg.get('type') == 'hello':
                    reply = guard.challenge(msg, peer, now)
                    sock.sendto(encode(reply, key), peer)
                else:
                    channels = guard.accept(msg, peer, now)
                    log(state='accepted', drone=args.drone, seq=msg['seq'], channels=channels,
                        sbus_hex=sbus_frame(channels).hex())
            except (ValueError, KeyError, TypeError):
                # Malformed, stale or unauthenticated traffic cannot refresh the watchdog.
                continue
    log(state='stopped', sink='JSON ONLY')

def sender(args, key):
    mapping = None
    joystick = None
    if args.joystick:
        if not args.mapping:
            raise SystemExit('--mapping required with --joystick')
        mapping = json.loads(Path(args.mapping).read_text())
        validate_mapping(mapping)
        joystick = Joystick(args.joystick)
    elif not args.synthetic:
        raise SystemExit('choose --synthetic or --joystick')
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sock:
            sock.connect((args.host, args.port))
            sock.settimeout(.10)
            until = time.monotonic() + args.seconds
            next_poll = time.monotonic()
            sent = 0
            while time.monotonic() < until:
                sock.send(encode({'type': 'hello', 'drone': args.drone}, key))
                try:
                    challenge = decode(sock.recv(2049), key)
                    if (challenge.get('type') != 'challenge' or challenge.get('drone') != args.drone
                            or type(challenge.get('token')) is not str
                            or type(challenge.get('seq')) is not int):
                        continue
                except (socket.timeout, ConnectionRefusedError, ValueError):
                    continue
                if joystick:
                    try:
                        channels, deadman = joystick.snapshot(mapping)
                    except KeyError:
                        continue  # Await initial axis reports; send no uninitialised controls.
                else:
                    channels = [992, 992, 172, 992] + [172] * 12
                    channels[0] = 992 + round(100 * math.sin(time.monotonic()))
                    deadman = True
                sock.send(encode({**challenge, 'type': 'control', 'channels': channels, 'deadman': deadman}, key))
                sent += 1
                next_poll = max(next_poll + .02, time.monotonic())
                time.sleep(max(0, next_poll - time.monotonic()))
            log(state='sender_stopped', sent=sent, source='joystick' if joystick else 'synthetic')
    finally:
        if joystick:
            joystick.close()

def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('mode', choices=['keygen', 'receiver', 'sender'])
    p.add_argument('--key', required=True)
    p.add_argument('--drone', choices=['fpv1', 'fpv2'], default='fpv1')
    p.add_argument('--bind', default='127.0.0.1')
    p.add_argument('--peer', default='127.0.0.1')
    p.add_argument('--host', default='127.0.0.1')
    p.add_argument('--port', type=int, default=14600)
    p.add_argument('--seconds', type=float, default=30)
    group = p.add_mutually_exclusive_group()
    group.add_argument('--synthetic', action='store_true')
    group.add_argument('--joystick')
    p.add_argument('--mapping')
    args = p.parse_args()
    if args.mode == 'keygen':
        with os.fdopen(os.open(args.key, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600), 'wb') as f:
            f.write(secrets.token_bytes(32))
        print('Created a private 32-byte bench key; do not commit or publish it.')
        return
    for value in (args.bind, args.peer, args.host):
        address = ipaddress.ip_address(value)
        if address.version != 4 or address.is_unspecified or address.is_multicast:
            raise SystemExit('use concrete unicast IPv4 addresses; never wildcard-bind')
    key = Path(args.key).read_bytes()
    if len(key) != 32:
        raise SystemExit('key must contain 32 random bytes')
    if args.seconds <= 0 or not 1024 <= args.port <= 65535:
        raise SystemExit('invalid duration or port')
    (receiver if args.mode == 'receiver' else sender)(args, key)

if __name__ == '__main__':
    main()
