import unittest
import socket
import threading
import time
from types import SimpleNamespace
from relay.protocol import decode, encode
from relay.sbus_bench import Output, receive, validate_bench_channels


class BenchRestrictions(unittest.TestCase):
    def test_only_sticks_can_change(self):
        validate_bench_channels([172, 1811, 172, 992] + [172] * 12)
        for index in range(4, 16):
            channels = [992, 992, 172, 992] + [172] * 12
            channels[index] = 1811
            with self.assertRaises(ValueError):
                validate_bench_channels(channels)

    def test_out_of_range_and_malformed_values(self):
        for channels in (None, {}, [0] * 16, [2047] * 16, [True] * 16, [172] * 15):
            with self.assertRaises(ValueError):
                validate_bench_channels(channels)

    def test_cannot_send_before_initialization(self):
        output = Output()
        with self.assertRaises(RuntimeError):
            output.send([992, 992, 172, 992] + [172] * 12)

    def test_network_rejects_arm_tamper_replay_and_stops_on_loss(self):
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as reservation:
            reservation.bind(('127.0.0.1', 0))
            port = reservation.getsockname()[1]
        args = SimpleNamespace(bind='127.0.0.1', peer='127.0.0.1', port=port, seconds=2)
        frames, errors = [], []
        accepted = threading.Event()

        def send(channels):
            frames.append(channels[:])
            accepted.set()

        def run():
            try:
                receive(args, b'k' * 32, SimpleNamespace(send=send))
            except BaseException as exc:
                errors.append(exc)

        thread = threading.Thread(target=run, daemon=True)
        thread.start()
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as client:
                client.settimeout(.1)
                deadline = time.monotonic() + 1
                while True:
                    client.sendto(encode({'type': 'hello', 'drone': 'fpv1'}, b'k' * 32),
                                  ('127.0.0.1', port))
                    try:
                        reply = decode(client.recv(2048), b'k' * 32)
                        break
                    except socket.timeout:
                        if time.monotonic() >= deadline:
                            self.fail('receiver did not become ready')
                channels = [992, 992, 172, 992] + [172] * 12
                control = {**reply, 'type': 'control', 'channels': channels, 'deadman': True}
                arm_channels = channels[:]
                arm_channels[4] = 1811
                for packet in (encode({**control, 'channels': arm_channels}, b'k' * 32),
                               encode(control, b'x' * 32),
                               encode(control, b'k' * 32),
                               encode(control, b'k' * 32)):
                    client.sendto(packet, ('127.0.0.1', port))
                self.assertTrue(accepted.wait(.5))
                thread.join(1)
                self.assertFalse(thread.is_alive(), 'receiver must stop after loss')
                self.assertEqual(frames, [channels])
                self.assertEqual(errors, [])
        finally:
            thread.join(3)
