import copy
import http.client
from http.server import ThreadingHTTPServer
import json
import threading
import tempfile
from pathlib import Path
from unittest.mock import patch, Mock
import termios
import unittest
from relay.console import Console, handler_for, validate_settings, saved_arm_profile, probe_video
from relay.joystick import validate_mapping


class ConsoleBoundaryTests(unittest.TestCase):
    def test_video_probe_requires_playlist_not_just_player_page(self):
        for status, content, expected in [(200,b'#EXTM3U\n#EXT-X-STREAM-INF',True),
                                           (200,b'<html>player</html>',False),
                                           (404,b'#EXTM3U',False)]:
            connection = Mock()
            connection.getresponse.return_value.status = status
            connection.getresponse.return_value.read.return_value = content
            with patch('relay.console.http.client.HTTPConnection',return_value=connection):
                self.assertEqual(probe_video('192.168.8.175'),expected)
            connection.request.assert_called_once_with('GET','/fpv1/index.m3u8')
            connection.close.assert_called_once()

    def test_video_disconnect_closes_probe_without_affecting_control(self):
        connection = Mock()
        connection.request.side_effect = TimeoutError('offline')
        with patch('relay.console.http.client.HTTPConnection',return_value=connection):
            self.assertFalse(probe_video('192.168.8.175'))
        connection.close.assert_called_once()

    def test_video_probe_follows_mediamtx_session_redirect_only_on_same_source(self):
        redirect = Mock(status=302)
        redirect.getheader.return_value = 'index.m3u8?session=test-session'
        playlist = Mock(status=200)
        playlist.read.return_value = b'#EXTM3U\n'
        connection = Mock()
        connection.getresponse.side_effect = [redirect, playlist]
        with patch('relay.console.http.client.HTTPConnection', return_value=connection):
            self.assertTrue(probe_video('192.168.8.175'))
        self.assertEqual(connection.request.call_args_list[-1].args,
                         ('GET','/fpv1/index.m3u8?session=test-session'))
        for url in ('http://external.example/fpv1/index.m3u8', '/other/index.m3u8'):
            redirect.getheader.return_value = url
            connection.reset_mock()
            connection.getresponse.side_effect = [redirect]
            with patch('relay.console.http.client.HTTPConnection', return_value=connection):
                self.assertFalse(probe_video('192.168.8.175'))
            self.assertEqual(connection.request.call_count,1)

    def test_verified_preparation_survives_console_restart_but_partial_write_does_not(self):
        with tempfile.TemporaryDirectory() as directory:
            backup = Path(directory) / 'fc.json'
            with patch('relay.console.ARM_BACKUP', backup):
                self.assertFalse(saved_arm_profile()['ready'])
                backup.write_text(json.dumps({'verified':False}))
                self.assertFalse(saved_arm_profile()['ready'])
                backup.write_text(json.dumps({'verified':True}))
                self.assertTrue(saved_arm_profile()['ready'])

    def test_usb_termios_disconnect_is_recovered_without_restarting_service(self):
        console = Console.__new__(Console)
        console.lock = threading.RLock()
        console.closing = threading.Event()
        console.fc_enabled = True
        console.arm_profile = {'ready':False}
        console.restore_needed = False
        console.session = {'active':False}
        console.job = {'busy':False}
        console.stop = Mock()
        broken, working = Mock(), Mock()
        broken.snapshot.side_effect = termios.error(5, 'Input/output error')
        def reconnected():
            console.closing.set()
            return {'connected':True,'armed':False,'channels':[]}
        working.snapshot.side_effect = reconnected
        with patch('relay.console.devices', return_value=['verified-FC']), patch('relay.console.Monitor', side_effect=[broken,working]) as factory:
            console.read_fc()
        self.assertEqual(factory.call_count,2)
        broken.close.assert_called_once()
        self.assertTrue(console.fc['connected'])

    def test_interrupted_restore_cannot_leave_arming_ready(self):
        with tempfile.TemporaryDirectory() as directory:
            backup = Path(directory) / 'fc.json'
            backup.write_text(json.dumps({'verified':True,'device':'same-FC','original':'00'*8,'gps_original':'00'*26}))
            console = Console.__new__(Console)
            console.monitor = Mock(path='same-FC')
            console.monitor.set_failsafe.side_effect = termios.error(5, 'USB disconnected')
            console.fc_enabled = True
            console.arm_profile = {'ready':True}
            console.restore_needed = False
            with patch('relay.console.ARM_BACKUP', backup):
                with self.assertRaises(termios.error):console.restore_arm_profile()
                self.assertFalse(saved_arm_profile()['ready'])
            self.assertFalse(console.arm_profile['ready'])
            self.assertTrue(console.restore_needed)

    def test_start_setup_prepares_missing_dependencies_and_can_cancel_before_output(self):
        console = Console.__new__(Console)
        console.session={'started':__import__('time').time()}
        console.stop_event=threading.Event()
        console.monitor=object()
        console.fc={'connected':True,'armed':False}
        console.hid={'connected':True,'channels':[992,992,172,992],'enabled':False}
        console.arm_profile={'ready':False}
        console.restore_needed=False
        console.prepare_pi=Mock()
        def prepared(): console.arm_profile={'ready':True}
        console.prepare_arm_profile=Mock(side_effect=prepared)
        self.assertTrue(console.arm_setup())
        console.prepare_pi.assert_called_once()
        console.prepare_arm_profile.assert_called_once()
        console.stop_event.set()
        self.assertFalse(console.arm_setup())

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
