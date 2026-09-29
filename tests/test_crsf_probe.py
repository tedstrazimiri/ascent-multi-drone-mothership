import unittest
from relay.crsf_probe import crc8, channel_frame, probe_channels

class CrsfProbeTests(unittest.TestCase):
    def test_crc_standard_check_value(self):
        self.assertEqual(crc8(b'123456789'), 0xBC)  # CRC-8/DVB-S2 check value

    def test_wire_shape_and_channel_unpacking(self):
        source = [0, 2047, 172, 992] + list(range(12))
        frame = channel_frame(source)
        self.assertEqual(frame[:3], b'\xc8\x18\x16')
        self.assertEqual(len(frame), 26)
        bits = ''.join(f'{byte:08b}'[::-1] for byte in frame[3:25])
        decoded = [int(bits[i:i+11][::-1], 2) for i in range(0, 176, 11)]
        self.assertEqual(decoded, source)
        self.assertEqual(crc8(frame[2:]), 0)

    def test_probe_can_never_raise_throttle_or_aux(self):
        for elapsed in [i / 100 for i in range(1001)]:
            values = probe_channels(elapsed)
            self.assertEqual(values[2], 172)
            self.assertEqual(values[4:], [172] * 12)
            self.assertIn(values[0], [816, 1168])

    def test_reject_invalid_inputs(self):
        for values in [[0]*15, [2048]*16, [True]*16, [-1]*16]:
            with self.assertRaises(ValueError):
                channel_frame(values)
