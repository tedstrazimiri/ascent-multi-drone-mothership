import json
import unittest
from pathlib import Path
from relay import ascent, protocol, video
from relay.joystick import validate_mapping

class ControlGuardTests(unittest.TestCase):
    def setUp(self):
        self.g = protocol.Guard('fpv1')
        self.peer = ('127.0.0.1', 30000)
        self.hello = {'type': 'hello', 'drone': 'fpv1'}

    def packet(self, time=0):
        return {**self.g.challenge(self.hello, self.peer, time), 'type': 'control',
                'channels': [992, 992, 172, 992] + [172]*12, 'deadman': True}

    def test_valid_then_timeout_latches(self):
        packet = self.packet()
        self.g.accept(packet, self.peer, .02)
        self.assertFalse(self.g.expired(.269))
        self.assertTrue(self.g.expired(.271))
        with self.assertRaises(ValueError):
            self.g.challenge(self.hello, self.peer, .28)

    def test_replay_rejected(self):
        packet = self.packet()
        self.g.accept(packet, self.peer, .02)
        with self.assertRaises(ValueError):
            self.g.accept(packet, self.peer, .03)

    def test_delayed_first_packet_rejected_without_shared_clock(self):
        packet = self.packet()
        with self.assertRaises(ValueError):
            self.g.accept(packet, self.peer, .151)
        self.assertIsNone(self.g.last_valid)

    def test_reordering_rejected(self):
        older, newer = self.packet(), self.packet(.001)
        self.g.accept(newer, self.peer, .02)
        with self.assertRaises(ValueError):
            self.g.accept(older, self.peer, .021)

    def test_wrong_drone_and_operator(self):
        packet = self.packet()
        packet['drone'] = 'fpv2'
        with self.assertRaises(ValueError):
            self.g.accept(packet, self.peer, .02)
        with self.assertRaises(ValueError):
            self.g.challenge(self.hello, ('127.0.0.2', 30000), .02)

    def test_deadman_latches_and_does_not_refresh(self):
        packet = self.packet()
        packet['deadman'] = False
        with self.assertRaises(ValueError):
            self.g.accept(packet, self.peer, .02)
        self.assertTrue(self.g.latched)
        self.assertIsNone(self.g.last_valid)

    def test_invalid_channels_do_not_refresh(self):
        for invalid in ([1]*15, [2048]*16, [True]*16, [float('nan')]*16, '992'):
            packet = self.packet()
            packet['channels'] = invalid
            with self.assertRaises(ValueError):
                self.g.accept(packet, self.peer, .02)
            self.assertIsNone(self.g.last_valid)

    def test_restart_invalidates_prior_tokens(self):
        packet = self.packet()
        self.g = protocol.Guard('fpv1')
        self.g.challenge(self.hello, self.peer, .03)
        with self.assertRaises(ValueError):
            self.g.accept(packet, self.peer, .04)

class CodecTests(unittest.TestCase):
    def test_tampering_wrong_key_and_oversize(self):
        key = b'k'*32
        packet = protocol.encode({'type': 'hello', 'drone': 'fpv1'}, key)
        self.assertEqual(protocol.decode(packet, key)['drone'], 'fpv1')
        for data, used_key in [(packet.replace(b'fpv1', b'fpv2'), key), (packet, b'x'*32), (b'x'*2049, key)]:
            with self.assertRaises(ValueError):
                protocol.decode(data, used_key)
        with self.assertRaises(ValueError):
            protocol.decode(protocol.encode([], key), key)

    def test_sbus_extremes_and_failsafe_flags(self):
        self.assertEqual(protocol.sbus_frame([0]*16), b'\x0f' + bytes(24))
        self.assertEqual(protocol.sbus_frame([2047]*16, True, True), b'\x0f' + b'\xff'*22 + b'\x0c\x00')
        with self.assertRaises(ValueError):
            protocol.sbus_frame([0]*15)

    def test_ascent_document_golden_packets(self):
        for name, expected in [('up', 'FE EF 22 00 04 40 00 00 00 00 40 0D 0A'),
                               ('confirm', 'FE EF 22 00 04 40 04 00 00 00 44 0D 0A'),
                               ('back', 'FE EF 22 00 04 40 07 00 00 00 47 0D 0A')]:
            key, press = ascent.KEYS[name]
            built = ascent.frame(0x22, bytes([0x40, key, press, 0]))
            self.assertEqual(built, bytes.fromhex(expected))
            self.assertEqual(ascent.parse(built), (0x22, bytes([0x40, key, press, 0])))
            with self.assertRaises(ValueError):
                ascent.parse(built[:-3] + b'\xff\r\n')

    def test_video_requires_compatible_capture(self):
        c = json.loads(Path('config/video-fpv1.json').read_text())
        self.assertIn('testsrc2=size=1280x720:rate=30', video.command(c))
        c.update(source='v4l2', device='/dev/v4l/by-id/test', input_format='mjpeg', encoder='copy')
        with self.assertRaises(ValueError):
            video.command(c)
        c['input_format'] = 'h264'
        cmd = video.command(c)
        self.assertIn('copy', cmd)
        self.assertNotIn('-b:v', cmd)
        c['url'] = 'rtsp://0.0.0.0:8554/fpv1'
        with self.assertRaises(ValueError):
            video.command(c)

    def test_reject_uncalibratable_mapping(self):
        m = json.loads(Path('config/joystick.example.json').read_text())
        validate_mapping(m)
        m['axes'][0]['max'] = m['axes'][0]['min']
        with self.assertRaises(ValueError):
            validate_mapping(m)

if __name__ == '__main__':
    unittest.main()
