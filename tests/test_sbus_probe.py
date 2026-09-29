import unittest
from relay.crsf_probe import probe_channels
from relay.sbus_probe import waveform, GPIO


class WaveformTests(unittest.TestCase):
    def decode(self, channels):
        levels = []
        pulses = waveform(channels)
        for on, off, delay in pulses:
            self.assertIn((on, off), [(1 << GPIO, 0), (0, 1 << GPIO)])
            self.assertEqual(delay % 10, 0)
            levels.extend([bool(on)] * (delay // 10))
        self.assertEqual(len(levels), 300)  # 25 bytes * (start+8+parity+2stop).
        self.assertFalse(levels[-1])
        decoded = []
        for offset in range(0, 300, 12):
            bits = [int(not level) for level in levels[offset:offset + 12]]
            self.assertEqual(bits[0], 0)
            self.assertEqual(bits[-2:], [1, 1])
            self.assertEqual(sum(bits[1:10]) % 2, 0)
            decoded.append(sum(bit << i for i, bit in enumerate(bits[1:9])))
        self.assertEqual(decoded[0], 15)
        self.assertEqual(decoded[23:], [0, 0])
        data_bits = ''.join(f'{byte:08b}'[::-1] for byte in decoded[1:23])
        unpacked = [int(data_bits[i:i+11][::-1], 2) for i in range(0, 176, 11)]
        self.assertEqual(unpacked, channels)

    def test_bit_timing_parity_and_channels(self):
        for channels in ([0] * 16, [2047] * 16, list(range(16)),
                         probe_channels(0), probe_channels(1)):
            self.decode(channels)

    def test_invalid_channel_rejected(self):
        with self.assertRaises(ValueError):
            waveform([2048] * 16)
