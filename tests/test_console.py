import copy
import http.client
from http.server import ThreadingHTTPServer
import json
import threading
import unittest
from relay.console import handler_for, validate_settings
from relay.joystick import validate_mapping


class ConsoleBoundaryTests(unittest.TestCase):
    def test_connection_settings_cannot_be_shell_commands(self):
        settings = {'host': '192.168.8.10', 'transport': 'hls', 'seconds': 60, 'video_bitrate': 3}
        validate_settings(settings)
        for field, value in [('host', '192.168.8.10; reboot'), ('host', '0.0.0.0'),
                             ('host', '127.0.0.1'), ('seconds', 86400), ('seconds', True),
                             ('video_bitrate', 100), ('transport', 'shell')]:
            invalid = {**settings, field: value}
            with self.assertRaises(ValueError):
                validate_settings(invalid)

    def test_invalid_calibration_is_a_validation_error(self):
        mapping = {'axes': [None] * 4, 'deadman_axis': {'index': 5, 'min': 16000, 'max': 32767}}
        with self.assertRaises(ValueError):
            validate_mapping(mapping)

    def test_http_mutations_require_local_origin_and_token(self):
        class FakeConsole:
            token = 'test-token'
            actions = []
            def snapshot(self):
                return {'token': self.token}
            def action(self, action, data):
                self.actions.append((action, data))
        fake = FakeConsole()
        server = ThreadingHTTPServer(('127.0.0.1', 0), handler_for(fake, 1))
        port = server.server_address[1]
        server.RequestHandlerClass = handler_for(fake, port)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            for origin, token, expected in [('https://unrelated.example', fake.token, 403),
                                             (f'http://127.0.0.1:{port}', 'bad', 403),
                                             (f'http://127.0.0.1:{port}', fake.token, 200)]:
                client = http.client.HTTPConnection('127.0.0.1', port)
                client.request('POST', '/api/start', '{}', {'Origin': origin, 'X-Console-Token': token})
                response = client.getresponse()
                self.assertEqual(response.status, expected)
                response.read(); client.close()
            self.assertEqual(fake.actions, [('start', {})])
            client = http.client.HTTPConnection('127.0.0.1', port)
            client.request('GET', '/api/state', headers={'Host': 'unrelated.example'})
            response = client.getresponse()
            self.assertEqual(response.status, 403)
            response.read(); client.close()
        finally:
            server.shutdown(); server.server_close(); thread.join()


if __name__ == '__main__':
    unittest.main()
