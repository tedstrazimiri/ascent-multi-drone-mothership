"""Bench-only control framing. Authentication does not provide encryption."""
import hashlib
import hmac
import json
import secrets

def encode(message, key):
    body = json.dumps(message, sort_keys=True, separators=(',', ':'), allow_nan=False).encode()
    return hmac.digest(key, body, 'sha256').hex().encode() + b' ' + body

def decode(packet, key):
    if len(packet) > 2048:
        raise ValueError('oversized packet')
    try:
        signature, body = packet.split(b' ', 1)
        expected = hmac.digest(key, body, 'sha256').hex().encode()
        if not hmac.compare_digest(signature, expected):
            raise ValueError('authentication failed')
        message = json.loads(body)
        if type(message) is not dict:
            raise ValueError('object required')
        return message
    except (UnicodeError, json.JSONDecodeError) as e:
        raise ValueError('invalid packet') from e

def valid_channels(channels):
    return (type(channels) is list and len(channels) == 16
            and all(type(x) is int and 0 <= x <= 2047 for x in channels))

def sbus_frame(channels, failsafe=False, lost=False):
    """Encode bytes for offline analysis only; inversion/timing is a hardware concern."""
    if not valid_channels(channels):
        raise ValueError('need 16 integer channels in 0..2047')
    bits = sum(value << (11 * i) for i, value in enumerate(channels))
    return b'\x0f' + bits.to_bytes(22, 'little') + bytes([(8 if failsafe else 0) | (4 if lost else 0), 0])

class Guard:
    """Receiver-clock challenge lifetime, one operator per run, latched link loss.

    No dependency on synchronized clocks. Channels are sampled AFTER receiving
    a challenge. The 150 ms challenge budget includes both directions of travel.
    """
    def __init__(self, drone, ttl=0.150, timeout=0.250):
        self.drone, self.ttl, self.timeout = drone, ttl, timeout
        self.owner = None
        self.pending = {}
        self.counter = 0
        self.last_sequence = -1
        self.last_valid = None
        self.latched = False

    def challenge(self, message, peer, now):
        if message != {'type': 'hello', 'drone': self.drone}:
            raise ValueError('invalid hello')
        if self.owner not in (None, peer):
            raise ValueError('another operator owns this run')
        if self.latched:
            raise ValueError('loss is latched; restart receiver explicitly')
        self.owner = peer
        self.pending = {k: v for k, v in self.pending.items() if now - v[0] < self.ttl}
        if len(self.pending) >= 64:
            raise ValueError('too many pending challenges')
        self.counter += 1
        token = secrets.token_hex(16)
        self.pending[token] = (now, self.counter)
        return {'type': 'challenge', 'drone': self.drone, 'token': token, 'seq': self.counter}

    def accept(self, message, peer, now):
        self.expired(now)
        if self.latched or peer != self.owner:
            raise ValueError('inactive operator')
        if (message.get('type') != 'control' or message.get('drone') != self.drone
                or type(message.get('token')) is not str
                or type(message.get('seq')) is not int
                or type(message.get('deadman')) is not bool
                or not valid_channels(message.get('channels'))):
            raise ValueError('invalid control snapshot')
        token = message['token']
        if token not in self.pending:
            raise ValueError('unknown or replayed challenge')
        issued, seq = self.pending.pop(token)
        if now - issued >= self.ttl or seq <= self.last_sequence or message['seq'] != seq:
            raise ValueError('stale or out-of-order snapshot')
        if not message['deadman']:
            self.latched = True
            raise ValueError('deadman released; restart receiver explicitly')
        self.last_sequence = seq
        self.last_valid = now
        return message['channels']

    def expired(self, now):
        if self.last_valid is not None and now - self.last_valid >= self.timeout:
            self.latched = True
        return self.latched
