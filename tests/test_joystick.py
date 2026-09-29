import copy
import json
from pathlib import Path
import unittest
from relay.joystick import Joystick, validate_mapping


class CalibratedJoystickTests(unittest.TestCase):
    def setUp(self):
        self.mapping = json.loads(Path('config/joystick-tx15-bench.json').read_text())
        self.joystick = object.__new__(Joystick)
        self.joystick.read = lambda: None
        self.joystick.axes = {0: 0, 1: 0, 2: -32767, 3: 0, 5: 32767}
        self.joystick.buttons = {}

    def test_sa_high_enables_without_arming(self):
        validate_mapping(self.mapping)
        channels, enabled = self.joystick.snapshot(self.mapping)
        self.assertTrue(enabled)
        self.assertEqual(channels, [992, 992, 172, 992] + [172] * 12)
        for value in (-32767, 0, 15999):
            self.joystick.axes[5] = value
            self.assertFalse(self.joystick.snapshot(self.mapping)[1])
        del self.joystick.axes[5]
        self.assertFalse(self.joystick.snapshot(self.mapping)[1])

    def test_calibrated_axes_and_aux_isolation(self):
        for axis in range(4):
            self.joystick.axes[axis] = 32767
            channels, _ = self.joystick.snapshot(self.mapping)
            self.assertEqual(channels[axis], 1811)
            self.assertEqual(channels[4:], [172] * 12)

    def test_invalid_enable_mapping(self):
        for gate in (None, {}, {'index': 0, 'min': 16000, 'max': 32767},
                     {'index': 5, 'min': 32767, 'max': 16000},
                     {'index': True, 'min': 16000, 'max': 32767}):
            mapping = copy.deepcopy(self.mapping)
            mapping['deadman_axis'] = gate
            with self.assertRaises(ValueError):
                validate_mapping(mapping)
        self.mapping['deadman_button'] = 1
        with self.assertRaises(ValueError):
            validate_mapping(self.mapping)


if __name__ == '__main__':
    unittest.main()
