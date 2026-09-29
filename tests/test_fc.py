import threading
import unittest
from unittest.mock import patch
from relay.fc import Monitor, request


class FCIndoorProfileTests(unittest.TestCase):
    def test_ram_profile_changes_only_requested_fields_and_restores(self):
        monitor = Monitor.__new__(Monitor)
        monitor.lock = threading.RLock()
        monitor.version = '26.6.2'
        monitor.port = object()
        monitor._snapshot = lambda: {'armed': False}
        original = bytes([15,60,232,3,2,100,0,2])
        gps = bytes(range(20)) + b'\x00' + bytes(range(21,26))
        config = {75: original, 135: gps, 34: bytes([0,0,32,48]), 238: bytes([1,0,0,0])}
        writes = []
        def fake_request(port, command, payload=b''):
            if command in (76,225):
                writes.append((command,payload))
                config[75 if command == 76 else 135] = payload
                return b''
            return config[command]
        with patch('relay.fc.request', side_effect=fake_request):
            old, bench, gps_old, gps_bench = monitor.bench_profile()
            self.assertEqual([i for i in range(8) if old[i]!=bench[i]], [7])
            self.assertEqual([i for i in range(26) if gps_old[i]!=gps_bench[i]], [20])
            monitor.set_gps_rescue(gps_bench); monitor.set_failsafe(bench)
            self.assertTrue(monitor.profile_matches(bench,gps_bench))
            monitor.set_failsafe(old); monitor.set_gps_rescue(gps_old)
            self.assertEqual(config[75],original);self.assertEqual(config[135],gps)
            self.assertEqual([c for c,_ in writes],[225,76,76,225])
            monitor._snapshot=lambda:{'armed':True}
            with self.assertRaises(ValueError):monitor.set_failsafe(bench)
            self.assertEqual(len(writes),4)

    def test_no_motor_or_eeprom_command_is_permitted(self):
        for command in (99,214,250):
            with self.assertRaises(ValueError):request(None,command)
        with self.assertRaises(ValueError):request(None,76,b'bad')
        with self.assertRaises(ValueError):request(None,225,b'bad')


if __name__ == '__main__':
    unittest.main()
