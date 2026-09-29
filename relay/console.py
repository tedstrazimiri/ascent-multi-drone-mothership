"""Local Ascent console with disarmed stick tests and explicit idle-only arm tests."""
import argparse
import base64
import copy
import glob
import hashlib
import http.client
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import ipaddress
import json
import mimetypes
import os
from pathlib import Path
import re
import secrets
import signal
import socket
import subprocess
import sys
import termios
import threading
import time
from urllib.parse import urljoin, urlsplit

from .joystick import Joystick, validate_mapping
from .fc import Monitor, devices

ROOT = Path(__file__).resolve().parent.parent
WEB = ROOT / 'web'
SETTINGS = ROOT / 'local-console.json'
WORK = ROOT / 'work' / 'console'
ARM_BACKUP = WORK / 'fc-failsafe-before-arm.json'
SSH = ['/usr/bin/ssh', '-o', 'ControlPath=none', '-o', 'BatchMode=yes',
       '-o', 'ConnectTimeout=5', '-o', 'ServerAliveInterval=3', '-o', 'ServerAliveCountMax=2']


def validate_settings(value):
    if type(value) is not dict or set(value) != {'host', 'transport', 'seconds', 'video_bitrate'}:
        raise ValueError('Invalid connection settings')
    address = ipaddress.ip_address(value['host'])
    if address.version != 4 or address.is_unspecified or address.is_multicast or address.is_loopback:
        raise ValueError('Enter the Pi IPv4 address on your network')
    if value['transport'] not in ('hls', 'webrtc'):
        raise ValueError('Choose HLS or WebRTC')
    if type(value['seconds']) is not int or value['seconds'] not in (30, 60, 90):
        raise ValueError('Choose a 30, 60 or 90 second bench session')
    if type(value['video_bitrate']) is not int or value['video_bitrate'] not in (1, 2, 3, 4, 6, 8):
        raise ValueError('Choose a supported video bitrate')
    return value


def private_json(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix('.tmp')
    with os.fdopen(os.open(temporary, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600), 'w') as f:
        json.dump(value, f, indent=2)
        f.write('\n')
    temporary.replace(path)


def saved_arm_profile():
    if ARM_BACKUP.exists() and json.loads(ARM_BACKUP.read_text()).get('verified') is True:
        return {'ready': True, 'message': 'Indoor setup retained · reconnect USB if the FC lost power',
                'failsafe': 'DROP (RAM only)', 'gps_required': False}
    return {'ready': False, 'message': 'Start will prepare indoor settings over FC USB. No reboot needed.'}


def probe_video(host):
    """Read stream availability; an HTTP player page alone also exists without video."""
    connection = http.client.HTTPConnection(host, 8888, timeout=2)
    try:
        url = f'http://{host}:8888/fpv1/index.m3u8'
        for _ in range(4):
            parsed = urlsplit(url)
            connection.request('GET', parsed.path + ('?' + parsed.query if parsed.query else ''))
            response = connection.getresponse()
            if response.status not in (301, 302, 303, 307, 308):
                return response.status == 200 and response.read(8192).lstrip().startswith(b'#EXTM3U')
            # MediaMTX adds an HLS session via a redirect. Keep probes on this source.
            location = response.getheader('Location')
            if not location:
                return False
            url = urljoin(url, location)
            target = urlsplit(url)
            if (target.scheme != 'http' or target.hostname != host or target.port != 8888
                    or not target.path.startswith('/fpv1/') or target.username or target.password):
                return False
            connection.close()
        return False
    except (OSError, ValueError, http.client.HTTPException):
        return False
    finally:
        connection.close()


class Console:
    def __init__(self):
        self.lock = threading.RLock()
        self.closing = threading.Event()
        self.stop_event = threading.Event()
        self.token = secrets.token_urlsafe(32)
        self.settings = {'host': '192.168.8.175', 'transport': 'webrtc', 'seconds': 60, 'video_bitrate': 3}
        self.mapping = json.loads((ROOT / 'config/joystick-tx15-bench.json').read_text())
        if SETTINGS.exists():
            saved = json.loads(SETTINGS.read_text())
            self.settings = validate_settings(saved['settings'])
            validate_mapping(saved['mapping'])
            self.mapping = saved['mapping']
        self.hid = {'connected': False, 'axes': {}, 'buttons': {}, 'channels': [], 'enabled': False}
        self.fc = {'connected': False, 'channels': [], 'error': 'Looking for the FC'}
        self.pi = {'connected': False, 'checking': False, 'error': 'Check the relay connection'}
        self.video = {'available': False, 'updated': None}
        self.job = {'busy': False, 'message': ''}
        self.session = {'active': False, 'state': 'idle', 'message': 'Ready when you are', 'frames': 0}
        self.logs = []
        self.fc_enabled = True
        self.monitor = None
        self.arm_profile = saved_arm_profile()
        self.restore_needed = ARM_BACKUP.exists() and not self.arm_profile['ready']
        self.last_ui = time.monotonic()
        self.session_thread = None
        WORK.mkdir(parents=True, exist_ok=True)
        os.chmod(WORK, 0o700)
        for target in (self.read_hid, self.read_fc, self.read_video, self.watchdog):
            threading.Thread(target=target, daemon=True).start()

    def log(self, text, level='info'):
        with self.lock:
            self.logs.append({'time': time.strftime('%H:%M:%S'), 'text': str(text), 'level': level})
            self.logs = self.logs[-60:]

    def snapshot(self):
        with self.lock:
            self.last_ui = time.monotonic()
            result = copy.deepcopy({'settings': self.settings, 'mapping': self.mapping,
                                  'hid': self.hid, 'fc': self.fc, 'pi': self.pi, 'job': self.job,
                                  'video': self.video,
                                  'session': self.session, 'logs': self.logs,
                                  'arm_profile': self.arm_profile,
                                  'fc_enabled': self.fc_enabled, 'token': self.token})
            if result['fc'].get('connected') and time.time() - result['fc'].get('updated', 0) > 2:
                result['fc'] = {'connected': False, 'channels': [], 'error': 'FC USB connection is being recovered'}
            return result

    def read_video(self):
        while not self.closing.is_set():
            with self.lock:
                host = self.settings['host']
                watching = time.monotonic() - self.last_ui < 10
            if watching:
                available = probe_video(host)
                with self.lock:
                    if self.settings['host'] == host:
                        self.video = {'available': available, 'updated': time.time()}
            self.closing.wait(5)

    def save(self):
        private_json(SETTINGS, {'settings': self.settings, 'mapping': self.mapping})

    def read_hid(self):
        joystick = None
        path = None
        while not self.closing.is_set():
            try:
                if joystick is None:
                    found = [p for p in glob.glob('/dev/input/by-id/usb-OpenTX_TX15_Joystick_*-joystick')
                             if not p.endswith('-event-joystick')]
                    if len(found) != 1:
                        raise OSError('Connect the TX15 in USB joystick mode')
                    path = found[0]
                    joystick = Joystick(path)
                with self.lock:
                    mapping = copy.deepcopy(self.mapping)
                channels, enabled = joystick.snapshot(mapping)
                with self.lock:
                    self.hid = {'connected': True, 'name': 'RadioMaster TX15',
                                'device': Path(path).name, 'axes': joystick.axes.copy(),
                                'buttons': joystick.buttons.copy(), 'channels': channels,
                                'enabled': enabled, 'updated': time.time()}
                self.closing.wait(.02)
            except (OSError, KeyError, ValueError) as exc:
                if joystick:
                    joystick.close()
                    joystick = None
                with self.lock:
                    self.hid = {'connected': False, 'axes': {}, 'buttons': {}, 'channels': [],
                                'enabled': False, 'error': str(exc)}
                self.closing.wait(1)
        if joystick:
            joystick.close()

    def read_fc(self):
        monitor = None
        while not self.closing.is_set():
            try:
                if not self.fc_enabled:
                    if monitor:
                        monitor.close()
                        monitor = None
                        self.monitor = None
                    with self.lock:
                        self.fc = {'connected': False, 'channels': [], 'error': 'USB released for Betaflight'}
                    self.closing.wait(.2)
                    continue
                if monitor is None:
                    found = devices()
                    if len(found) != 1:
                        raise OSError('Connect the TAKER H743 to laptop USB')
                    monitor = Monitor(found[0])
                    self.monitor = monitor
                    if self.arm_profile.get('ready') and ARM_BACKUP.exists():
                        saved = json.loads(ARM_BACKUP.read_text())
                        if not monitor.profile_matches(bytes.fromhex(saved['bench']), bytes.fromhex(saved['gps_bench'])):
                            saved['verified'] = False
                            private_json(ARM_BACKUP, saved)
                            self.arm_profile = {'ready': False, 'message': 'FC setup changed or power-cycled. Prepare indoor arming again.'}
                if self.restore_needed and not self.session['active'] and not self.job['busy']:
                    self.restore_arm_profile()
                snapshot = monitor.snapshot()
                with self.lock:
                    self.fc = snapshot
                if snapshot['armed'] and self.session.get('kind') != 'arming':
                    self.stop('FC reports armed; bench output stopped')
                self.closing.wait(.12)
            except (OSError, ValueError, TimeoutError, termios.error) as exc:
                if monitor:
                    monitor.close()
                    monitor = None
                    self.monitor = None
                with self.lock:
                    self.fc = {'connected': False, 'channels': [], 'error': str(exc)}
                if self.session.get('kind') != 'arming':
                    self.stop('FC telemetry disconnected')
                self.closing.wait(1)
        if monitor:
            monitor.close()

    def ssh(self, command, **kwargs):
        host = self.settings['host']
        return subprocess.run(SSH + ['-o', f'HostName={host}', '-o', 'HostKeyAlias=ascent-relay.local',
                                     'ascent-pi', command], capture_output=True, timeout=20, **kwargs)

    def remote_script(self, script):
        result = self.ssh('sudo python3 -', input=script.encode())
        if result.returncode:
            raise RuntimeError(result.stderr.decode(errors='replace').strip()[-600:] or 'Pi operation failed')
        return result.stdout.decode().strip()

    def run_job(self, label, function):
        with self.lock:
            if self.session['active'] or self.job['busy']:
                raise ValueError('Stop the active operation first')
            self.job = {'busy': True, 'message': label}
        def run():
            try:
                function()
                self.log(label + ' complete')
                with self.lock:
                    self.job = {'busy': False, 'message': label + ' complete'}
            except Exception as exc:
                self.log(str(exc), 'error')
                with self.lock:
                    self.job = {'busy': False, 'message': str(exc), 'error': True}
        threading.Thread(target=run, daemon=True).start()

    def check_pi(self):
        host = self.settings['host']
        with self.lock:
            self.pi['checking'] = True
        try:
            ping = subprocess.run(['ping', '-n', '-c', '1', '-W', '2', host],
                                  capture_output=True, text=True, timeout=4)
            match = re.search(r'time[=<]([\d.]+)', ping.stdout)
            script = """import json,subprocess,pathlib,hashlib
def run(args):
 p=subprocess.run(args,capture_output=True,text=True);return p.stdout.strip()
print(json.dumps({'hostname':run(['hostname']),'interfaces':json.loads(run(['ip','-j','-4','address'])),
 'video':run(['systemctl','is-active','ascent-video@fpv1.service']),
 'media':run(['systemctl','is-active','ascent-mediamtx.service']),
 'pin':run(['pinctrl','get','14']),
 'driver':pathlib.Path('/opt/ascent-relay/vendor/pigpio/libpigpio.so.1').exists(),
 'receiver':pathlib.Path('/opt/ascent-relay/relay/sbus_bench.py').exists(),
 'key_hash':hashlib.sha256(pathlib.Path('/run/ascent-sbus-bench.key').read_bytes()).hexdigest() if pathlib.Path('/run/ascent-sbus-bench.key').exists() else None}))
"""
            info = json.loads(self.remote_script(script))
            local_key = WORK / 'control.key'
            info['key'] = info.pop('key_hash') == (hashlib.sha256(local_key.read_bytes()).hexdigest() if local_key.exists() else '')
            with self.lock:
                self.pi = {**info, 'connected': True, 'checking': False, 'host': host,
                           'ping_ms': float(match[1]) if match else None, 'updated': time.time()}
            self.log('Relay connected at ' + host)
        except Exception as exc:
            with self.lock:
                self.pi = {'connected': False, 'checking': False, 'error': str(exc)}
            raise

    def prepare_pi(self):
        key_path = WORK / 'control.key'
        if not key_path.exists():
            with os.fdopen(os.open(key_path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600), 'wb') as f:
                f.write(secrets.token_bytes(32))
        files = {}
        for name in ('__init__.py', 'protocol.py', 'crsf_probe.py', 'sbus_probe.py', 'sbus_bench.py', 'arm_test.py', 'joystick.py'):
            files[name] = base64.b64encode((ROOT / 'relay' / name).read_bytes()).decode()
        payload = {'files': files, 'key': base64.b64encode(key_path.read_bytes()).decode()}
        script = """import base64,json,os,pathlib,hashlib
data=json.loads(PAYLOAD)
root=pathlib.Path('/opt/ascent-relay/relay')
if not pathlib.Path('/opt/ascent-relay/vendor/pigpio/libpigpio.so.1').exists():
 raise RuntimeError('Install the project pigpio bench driver before preparing control')
root.mkdir(parents=True,exist_ok=True)
for name,encoded in data['files'].items():
 path=root/name;raw=base64.b64decode(encoded);path.write_bytes(raw);path.chmod(0o644)
 assert hashlib.sha256(path.read_bytes()).digest()==hashlib.sha256(raw).digest()
key=pathlib.Path('/run/ascent-sbus-bench.key');key.unlink(missing_ok=True)
with os.fdopen(os.open(key,os.O_WRONLY|os.O_CREAT|os.O_EXCL,0o600),'wb') as f:f.write(base64.b64decode(data['key']))
print('Receiver installed and key ready. No RC output started.')
""".replace('PAYLOAD', repr(json.dumps(payload)))
        self.remote_script(script)
        self.check_pi()

    def prepare_arm_profile(self):
        monitor = self.monitor
        if not monitor or not self.fc_enabled:
            raise ValueError('Connect FC USB and enable its connection to prepare the indoor arming test')
        if ARM_BACKUP.exists():
            saved = json.loads(ARM_BACKUP.read_text())
            if saved.get('verified') and monitor.path == saved['device'] and monitor.profile_matches(bytes.fromhex(saved['bench']), bytes.fromhex(saved['gps_bench'])):
                self.arm_profile = {'ready': True, 'message': 'Indoor setup verified · no GPS fix required',
                                    'failsafe': 'DROP (RAM only)', 'gps_required': False}
                self.restore_needed = False
                return
            self.restore_arm_profile()
        original, bench, gps_original, gps_bench = monitor.bench_profile()
        private_json(ARM_BACKUP, {'original': original.hex(), 'bench': bench.hex(), 'device': monitor.path,
                                 'gps_original': gps_original.hex(), 'gps_bench': gps_bench.hex(), 'verified': False})
        self.restore_needed = False
        try:
            monitor.set_gps_rescue(gps_bench)
            deadline = time.monotonic() + 2
            while True:
                status = monitor.snapshot()
                if status['arming_flags'] is not None and 'GPS' not in status['arming_blockers']:
                    break
                if time.monotonic() >= deadline:
                    raise ValueError('GPS arming blocker did not clear')
                time.sleep(.1)
            monitor.set_failsafe(bench)
            saved = json.loads(ARM_BACKUP.read_text())
            saved.update(verified=True, verified_at=time.time())
            private_json(ARM_BACKUP, saved)
            self.arm_profile = {'ready': True, 'message': 'Indoor setup ready · no GPS fix required · USB can be unplugged',
                                'failsafe': 'DROP (RAM only)', 'gps_required': False}
            self.log('FC bench setup verified: arming without GPS enabled and DROP failsafe in RAM; original settings backed up.')
        except Exception:
            self.restore_needed = True
            raise

    def restore_arm_profile(self):
        monitor = self.monitor
        if not monitor or not self.fc_enabled:
            raise ValueError('Reconnect FC USB to restore the original settings live. No reboot needed.')
        if ARM_BACKUP.exists():
            saved = json.loads(ARM_BACKUP.read_text())
            if saved['device'] != monitor.path:
                raise ValueError('Connect the same FC to restore the saved failsafe')
            saved['verified'] = False
            private_json(ARM_BACKUP, saved)
            self.arm_profile = {'ready': False, 'message': 'Restoring original settings over USB…'}
            self.restore_needed = True
            monitor.set_failsafe(bytes.fromhex(saved['original']))
            if 'gps_original' in saved:
                monitor.set_gps_rescue(bytes.fromhex(saved['gps_original']))
            ARM_BACKUP.unlink()
        self.restore_needed = False
        self.arm_profile = {'ready': False, 'message': 'Original flight failsafe restored; prepare again for indoor arming'}
        self.log('Original FC failsafe restored and read back')

    def arm_setup(self):
        """One Start action prepares dependencies, then waits for the operator."""
        self.session.update(state='preparing', message='Checking and preparing the relay…')
        self.prepare_pi()
        if self.stop_event.is_set():
            return False
        if self.monitor and self.fc.get('connected'):
            self.session.update(message='Checking indoor FC settings…')
            self.prepare_arm_profile()
        while not self.stop_event.is_set():
            if time.time() - self.session['started'] > 90:
                raise ValueError('Setup window ended. Click Start again when ready; no reboot needed.')
            if not self.arm_profile.get('ready') or self.restore_needed:
                self.session.update(state='waiting', message='Connect FC USB once; indoor settings will prepare automatically.')
                if not self.fc_enabled:
                    self.fc_enabled = True
                if self.monitor and self.fc.get('connected'):
                    self.prepare_arm_profile()
                else:
                    self.stop_event.wait(.2)
                    continue
            if not self.hid.get('connected'):
                message = 'Connect the TX15 in USB joystick mode.'
            elif self.hid['channels'][2] > 210:
                message = 'Lower throttle fully. Nothing is being transmitted yet.'
            elif self.hid['enabled']:
                message = 'Move SA to low/off. Then wait for the green ready message.'
            elif self.fc.get('connected') and self.fc.get('armed'):
                message = 'FC reports armed. Disarm before starting another test.'
            else:
                return True
            self.session.update(state='waiting', message=message)
            self.stop_event.wait(.1)
        return False

    def video_action(self, operation):
        if operation == 'bitrate':
            bitrate = self.settings['video_bitrate']
            script = """import json,pathlib,datetime,subprocess
p=pathlib.Path('/etc/ascent-relay/video-fpv1.json')
old=p.read_text();c=json.loads(old);c['bitrate']='BITRATEM'
backup=p.with_name(p.name+'.before-console-'+datetime.datetime.now().strftime('%Y%m%dT%H%M%S'))
backup.write_text(old);p.write_text(json.dumps(c,indent=2)+'\\n')
subprocess.run(['systemctl','restart','ascent-video@fpv1.service'],check=True)
print('Video bitrate saved and publisher restarted')
""".replace('BITRATE', str(bitrate))
        else:
            script = """import subprocess,pathlib,datetime
p=pathlib.Path('/etc/ascent-relay/mediamtx.yml');old=p.read_text()
new=old.replace('webrtcIPsFromInterfacesList: [wlan0, eth0]', 'webrtcIPsFromInterfacesList: [wlan0, wlan1, eth0]')
if new!=old:
 p.with_name(p.name+'.before-alfa-'+datetime.datetime.now().strftime('%Y%m%dT%H%M%S')).write_text(old)
 p.write_text(new)
subprocess.run(['systemctl','restart','ascent-mediamtx.service'],check=True)
subprocess.run(['systemctl','restart','ascent-video@fpv1.service'],check=True)
print('Video restarted; Alfa interface included for WebRTC')
"""
        self.remote_script(script)
        self.check_pi()

    def stop(self, reason='Stopped by operator'):
        with self.lock:
            if self.session['active']:
                self.session['message'] = reason
                self.stop_event.set()

    def start(self, kind):
        with self.lock:
            if kind not in ('joystick', 'synthetic', 'arming'):
                raise ValueError('Unknown bench test')
            if self.session['active'] or self.job['busy']:
                raise ValueError('An operation is already running')
            if kind != 'arming' and not self.pi.get('connected'):
                raise ValueError('Check the relay connection first')
            if kind != 'arming' and (not self.fc.get('connected') or self.fc.get('armed') or not self.fc.get('sbus') or time.time() - self.fc.get('updated', 0) > 1):
                raise ValueError('Connect the disarmed SBUS flight controller over USB')
            if kind == 'joystick':
                if not self.hid['connected'] or not self.hid['enabled']:
                    raise ValueError('Set SA to the highlighted enable position')
                if self.hid['channels'][2] > 210:
                    raise ValueError('Move throttle fully down before starting')
            if kind != 'arming' and (not (WORK / 'control.key').exists() or not self.pi.get('key')):
                raise ValueError('Use Prepare relay first; the Pi key must be recreated after reboot')
            self.stop_event.clear()
            self.last_ui = time.monotonic()
            self.session = {'active': True, 'state': 'starting', 'kind': kind,
                            'message': 'Connecting the control receiver', 'frames': 0,
                            'started': time.time(), 'seconds': 4 if kind == 'synthetic' else 90 if kind == 'arming' else self.settings['seconds']}
            private_json(WORK / 'joystick.json', self.mapping)
            self.session_thread = threading.Thread(target=self.run_session, args=(kind,), daemon=True)
            self.session_thread.start()

    def run_session(self, kind):
        remote = sender = None
        ready = threading.Event()
        receiver_done = threading.Event()
        messages = []
        error = None
        started = time.time()
        cancelled_before_output = False
        ending = None
        try:
            if kind == 'arming' and not self.arm_setup():
                cancelled_before_output = True
                return
            host = self.settings['host']
            duration = 4 if kind == 'synthetic' else 60 if kind == 'arming' else self.settings['seconds']
            self.session.update(started=time.time(), seconds=duration, state='starting', message='Connecting the receiver…')
            with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as route:
                route.connect((host, 14601))
                source = route.getsockname()[0]
            remote_command = (f'cd /opt/ascent-relay && sudo timeout --kill-after=2 {duration + 10} '
                              f'python3 -m relay.sbus_bench --key /run/ascent-sbus-bench.key '
                              f'--bind {host} --peer {source} --seconds {duration + 5} --transmit --sbus-wired')
            if kind == 'arming':
                remote_command = (f'cd /opt/ascent-relay && sudo timeout --kill-after=2 70 '
                                  f'python3 -m relay.arm_test receiver --key /run/ascent-sbus-bench.key '
                                  f'--bind {host} --peer {source} --seconds 65 --props-off')
            remote = subprocess.Popen(SSH + ['-o', f'HostName={host}', '-o',
                                            'HostKeyAlias=ascent-relay.local', 'ascent-pi', remote_command],
                                      stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
            def receiver_log():
                for line in remote.stdout:
                    try:
                        entry = json.loads(line)
                    except ValueError:
                        self.log(line.strip(), 'error')
                        continue
                    messages.append(entry)
                    state = entry.get('state')
                    if state == 'waiting':
                        ready.set()
                    elif state == 'accepted':
                        with self.lock:
                            if kind != 'arming' or entry.get('arm_requested'):
                                self.session.update(state='live', message='ARM requested · automatic cutoff in two seconds' if kind == 'arming' else 'Live stick transport · ARM blocked')
                            self.session['frames'] = entry['frames']
                    elif state in ('loss_latched', 'stopped'):
                        with self.lock:
                            self.session.update(state='stopping', frames=entry.get('frames', 0),
                                                message='Receiver stopped; restart is explicit')
                        receiver_done.set()
                    elif state == 'interlock':
                        self.log(entry.get('message', 'Arming interlock'), 'error')
                receiver_done.set()
            reader = threading.Thread(target=receiver_log, daemon=True)
            reader.start()
            if not ready.wait(8) or receiver_done.is_set():
                raise RuntimeError('Receiver did not become ready. Check the Pi connection and prepare it again.')
            if self.stop_event.is_set():
                return
            command = [sys.executable, '-m', 'relay.bench', 'sender', '--key', str(WORK / 'control.key'),
                       '--host', host, '--port', '14601', '--seconds', str(duration)]
            if kind == 'joystick':
                command += ['--joystick', '/dev/input/by-id/' + self.hid['device'],
                            '--mapping', str(WORK / 'joystick.json')]
            else:
                command += ['--synthetic']
            if kind == 'arming':
                command = [sys.executable, '-m', 'relay.arm_test', 'sender', '--key', str(WORK / 'control.key'),
                           '--host', host, '--seconds', '60', '--props-off',
                           '--joystick', '/dev/input/by-id/' + self.hid['device'], '--mapping', str(WORK / 'joystick.json')]
            sender = subprocess.Popen(command, cwd=ROOT, stdout=subprocess.PIPE,
                                      stderr=subprocess.STDOUT, text=True)
            sender_lines = []
            def sender_log():
                for line in sender.stdout:
                    sender_lines.append(line)
                    try:
                        event = json.loads(line)
                        if kind == 'arming' and event.get('state') == 'guidance':
                            with self.lock:
                                self.session.update(state=event['phase'], message=event['message'])
                        elif event.get('state') == 'interlock':
                            self.log(event.get('message', 'Control interlock'), 'error')
                    except ValueError:
                        self.log(line.strip(), 'error')
            sender_reader = threading.Thread(target=sender_log, daemon=True)
            sender_reader.start()
            samples = []
            while sender.poll() is None and not receiver_done.is_set() and not self.stop_event.wait(.1):
                with self.lock:
                    samples.append({'t': round(time.time() - started, 3), 'fc': copy.deepcopy(self.fc)})
            if sender.poll() is None:
                sender.terminate()
            sender.wait(timeout=3)
            sender_reader.join(timeout=1)
            output = ''.join(sender_lines)
            for line in output.splitlines():
                try:
                    event = json.loads(line)
                    if event.get('state') == 'enable_released':
                        self.log('SA returned to the off position. Control stopped.')
                except ValueError:
                    self.log(line, 'error')
            # No sender means no new frames. Allow receiver watchdog to close normally.
            try:
                remote.wait(timeout=2)
            except subprocess.TimeoutExpired:
                remote.terminate()
                remote.wait(timeout=3)
            reader.join(timeout=1)
            private_json(WORK / ('trial-' + time.strftime('%Y%m%dT%H%M%S') + '.json'),
                         {'kind': kind, 'started': started, 'receiver': messages, 'samples': samples,
                          'sender_log': output, 'sender_returncode': sender.returncode,
                          'receiver_returncode': remote.returncode})
            if remote.returncode and not self.stop_event.is_set():
                raise RuntimeError('The Pi receiver exited unexpectedly; output has stopped')
            if sender.returncode not in (0, -signal.SIGTERM) and not self.stop_event.is_set():
                raise RuntimeError('The control sender exited unexpectedly; output has stopped')
            if kind == 'arming':
                ending = next((item.get('reason') for item in reversed(messages) if item.get('state') == 'stopped'), None)
                if ending == 'source_loss' and not self.stop_event.is_set():
                    raise RuntimeError('Control link timed out. ARM-low frames sent; lower SA and retry.')
                if ending == 'interlock':
                    raise RuntimeError('Switch-test interlock stopped output. Begin with SA low for one second.')
        except Exception as exc:
            error = str(exc)
            self.log(error, 'error')
        finally:
            for process in (sender, remote):
                if process and process.poll() is None:
                    process.terminate()
                    try:
                        process.wait(timeout=2)
                    except subprocess.TimeoutExpired:
                        process.kill()
            with self.lock:
                final_message = 'Cancelled · no ARM command sent' if cancelled_before_output else (
                    'Two-second test complete. Lower SA and click Test again.' if ending == 'arm_limit' else
                    'SA lowered · disarm frames sent. Click Test again when ready.' if ending == 'sa_low' else
                    'Stopped · disarm frames sent. Click Test again when ready.')
                self.session.update(active=False, state='error' if error else 'stopped',
                                    message=error or (final_message if kind == 'arming' else 'Session ended · output stopped'), ended=time.time())
            if kind == 'arming':
                self.log(error or final_message, 'error' if error else 'info')
            else:
                self.log(error or 'Bench session ended. ARM remained blocked.', 'error' if error else 'info')

    def watchdog(self):
        while not self.closing.wait(.25):
            if time.monotonic() - self.last_ui > 3:
                self.stop('Setup screen disconnected')

    def action(self, action, data):
        if action == 'stop':
            self.stop()
            return
        if action == 'start':
            self.start(data.get('kind'))
            return
        with self.lock:
            if self.session['active'] or self.job['busy']:
                raise ValueError('Stop the active operation before changing setup')
            if action == 'settings':
                settings = validate_settings(data)
                if settings['host'] != self.settings['host']:
                    self.pi = {'connected': False, 'error': 'Check the new relay address'}
                    self.video = {'available': False, 'updated': None}
                self.settings = settings
                self.save()
                self.log('Connection and video preferences saved')
            elif action == 'mapping':
                validate_mapping(data)
                self.mapping = copy.deepcopy(data)
                self.save()
                self.log('TX15 control calibration saved')
            elif action == 'fc':
                self.fc_enabled = data.get('enabled') is True
            elif action == 'check':
                self.run_job('Check relay', self.check_pi)
            elif action == 'prepare':
                self.run_job('Prepare relay', self.prepare_pi)
            elif action == 'arm_prepare':
                self.run_job('Prepare indoor arming', self.prepare_arm_profile)
            elif action == 'arm_restore':
                self.run_job('Restore flight failsafe', self.restore_arm_profile)
            elif action in ('video_restart', 'video_bitrate'):
                self.run_job('Apply video settings', lambda: self.video_action('bitrate' if action == 'video_bitrate' else 'restart'))
            else:
                raise ValueError('Unknown action')

    def close(self):
        self.stop('Console closing')
        if self.session_thread:
            self.session_thread.join(timeout=5)
        self.closing.set()


def handler_for(console, port):
    origin = f'http://127.0.0.1:{port}'
    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *args):
            pass

        def send(self, code, data, kind='application/json'):
            body = json.dumps(data).encode() if kind == 'application/json' else data
            self.send_response(code)
            self.send_header('Content-Type', kind)
            self.send_header('Content-Length', str(len(body)))
            self.send_header('Cache-Control', 'no-store')
            self.send_header('X-Content-Type-Options', 'nosniff')
            self.send_header('Referrer-Policy', 'no-referrer')
            # The selected, validated Pi is the only extra signaling destination.
            video_host = getattr(console, 'settings', {}).get('host', '192.168.8.175')
            self.send_header('Content-Security-Policy', f"default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; img-src 'self' data:; media-src 'self' blob:; frame-src http:; connect-src 'self' http://{video_host}:8889; frame-ancestors 'none'")
            self.end_headers()
            try:
                self.wfile.write(body)
            except (BrokenPipeError, ConnectionResetError):
                pass

        def allowed_host(self):
            return self.headers.get('Host') == f'127.0.0.1:{port}'

        def do_GET(self):
            if not self.allowed_host():
                self.send(403, {'error': 'Open the console through 127.0.0.1'})
                return
            path = urlsplit(self.path).path
            if path == '/api/state':
                self.send(200, console.snapshot())
            elif path in ('/', '/app.js', '/style.css', '/video-player.js',
                          '/vendor/mediamtx-reader.js', '/latency-target.html', '/latency-target.js'):
                name = 'index.html' if path == '/' else path[1:]
                self.send(200, (WEB / name).read_bytes(), mimetypes.guess_type(name)[0] or 'text/plain')
            else:
                self.send(404, {'error': 'Not found'})

        def do_POST(self):
            if (not self.allowed_host() or self.headers.get('Origin') != origin
                    or not secrets.compare_digest(self.headers.get('X-Console-Token', ''), console.token)):
                self.send(403, {'error': 'Local console session required'})
                return
            try:
                length = int(self.headers.get('Content-Length', '0'))
                if not 0 < length <= 8192:
                    raise ValueError('Invalid request length')
                data = json.loads(self.rfile.read(length))
                if type(data) is not dict or not self.path.startswith('/api/'):
                    raise ValueError('Invalid request')
                console.action(self.path[5:], data)
                self.send(200, {'ok': True})
            except (ValueError, TypeError, KeyError) as exc:
                self.send(400, {'error': str(exc)})
    return Handler


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--port', type=int, default=8767)
    args = parser.parse_args()
    console = Console()
    server = ThreadingHTTPServer(('127.0.0.1', args.port), handler_for(console, args.port))
    def shutdown(*unused):
        console.stop('Console closing')
        threading.Thread(target=server.shutdown, daemon=True).start()
    signal.signal(signal.SIGTERM, shutdown)
    try:
        print(f'Ascent setup console: http://127.0.0.1:{args.port}', flush=True)
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        console.close()
        server.server_close()


if __name__ == '__main__':
    main()
