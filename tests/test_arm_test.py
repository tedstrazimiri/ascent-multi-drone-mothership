import socket
import threading
import time
from types import SimpleNamespace
import unittest
from relay.arm_test import ArmGate, OFF, ON, DRONE, receive, validate_arm_channels
from relay.protocol import decode, encode


class ArmingInterlocks(unittest.TestCase):
    def test_only_arm_can_change_and_throttle_never_moves(self):
        validate_arm_channels(OFF)
        validate_arm_channels(ON)
        for index in range(16):
            altered = OFF[:]
            altered[index] += 1
            with self.assertRaises(ValueError):
                validate_arm_channels(altered)
        with self.assertRaises(ValueError):
            validate_arm_channels([True] * 16)

    def test_cannot_start_with_high_or_rearm(self):
        gate = ArmGate()
        with self.assertRaises(ValueError):
            gate.accept(ON, 0)
        with self.assertRaises(ValueError):
            gate.accept(OFF, 1)
        gate = ArmGate()
        for i in range(50):
            gate.accept(OFF, i / 50)
        gate.accept(ON, 1)
        gate.accept(OFF, 1.1)
        with self.assertRaises(ValueError):
            gate.accept(ON, 1.2)

    def test_independent_two_second_limit(self):
        gate = ArmGate()
        for i in range(50):
            gate.accept(OFF, i / 50)
        gate.accept(ON, 1)
        self.assertFalse(gate.expired(2.999))
        self.assertTrue(gate.expired(3))
        with self.assertRaises(ValueError):
            gate.accept(ON, 3)

    def test_network_loss_after_arm_sends_disarm_frames(self):
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as reserve:
            reserve.bind(('127.0.0.1', 0)); port = reserve.getsockname()[1]
        frames, errors = [], []
        args = SimpleNamespace(bind='127.0.0.1', peer='127.0.0.1', port=port, seconds=4)
        def run():
            try:
                receive(args, b'k' * 32, SimpleNamespace(send=lambda c: frames.append(c[:])))
            except BaseException as exc:
                errors.append(exc)
        thread = threading.Thread(target=run, daemon=True); thread.start()
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as client:
            client.settimeout(.1)
            def send(channels, bad=False):
                client.sendto(encode({'type':'hello','drone':DRONE}, b'k'*32), ('127.0.0.1',port))
                reply=decode(client.recv(2049),b'k'*32)
                client.sendto(encode({**reply,'type':'control','channels':channels,'deadman':True}, b'x'*32 if bad else b'k'*32), ('127.0.0.1',port))
            deadline=time.monotonic()+1
            while True:
                try:
                    send(OFF); break
                except socket.timeout:
                    if time.monotonic()>deadline: raise
            for _ in range(45):
                send(OFF); time.sleep(.02)
            send(ON, bad=True)
            time.sleep(.03)
            self.assertNotIn(ON, frames)
            send(ON)
        thread.join(2)
        self.assertFalse(thread.is_alive())
        self.assertFalse(errors)
        self.assertIn(ON, frames)
        self.assertEqual(frames[-10:], [OFF]*10)


if __name__ == '__main__':
    unittest.main()
