#!/usr/bin/env python3
"""Test real localhost UDP and two synthetic RTSP streams, then stop everything."""
import json
import os
from pathlib import Path
import socket
import subprocess
import sys
import tarfile
import tempfile
import time

ROOT = Path(__file__).resolve().parents[1]
os.chdir(ROOT)
sys.path.insert(0, str(ROOT))
from relay.video import command

def free_port(kind):
    with socket.socket(socket.AF_INET, kind) as s:
        s.bind(('127.0.0.1', 0))
        return s.getsockname()[1]

def stop(process):
    if process.poll() is None:
        process.terminate()
        try:
            process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait()

def main():
    procs = []
    report = {'hardware_used': False}
    with tempfile.TemporaryDirectory(prefix='ascent-smoke-') as temp:
        temp = Path(temp)
        try:
            key = temp/'bench.key'
            key.write_bytes(os.urandom(32))
            key.chmod(0o600)
            port = free_port(socket.SOCK_DGRAM)
            with (temp/'control.log').open('w') as log:
                rx = subprocess.Popen([sys.executable, '-m', 'relay.bench', 'receiver', '--key', str(key),
                                       '--port', str(port), '--seconds', '3'], stdout=log, stderr=log)
                procs.append(rx)
                time.sleep(.2)
                subprocess.run([sys.executable, '-m', 'relay.bench', 'sender', '--key', str(key),
                                '--port', str(port), '--seconds', '1', '--synthetic'], check=True, timeout=5)
                rx.wait(timeout=5)
            records = [json.loads(line) for line in (temp/'control.log').read_text().splitlines()]
            accepted = sum(r.get('state') == 'accepted' for r in records)
            assert accepted >= 10, records
            assert any(r.get('state') == 'loss_latched' for r in records), records
            report['control'] = {'accepted_snapshots': accepted, 'sender_stop_watchdog': 'passed', 'sink': 'JSON only'}
            binary = temp/'mediamtx'
            archive = ROOT/'.cache/mediamtx_v1.21.1_linux_amd64.tar.gz'
            with tarfile.open(archive) as tar:
                with tar.extractfile('mediamtx') as src:
                    binary.write_bytes(src.read())
            binary.chmod(0o700)
            port = free_port(socket.SOCK_STREAM)
            cfg = temp/'mediamtx.yml'
            cfg.write_text((ROOT/'config/mediamtx.yml').read_text().replace('127.0.0.1:8554', f'127.0.0.1:{port}'))
            with (temp/'video.log').open('w') as log:
                server = subprocess.Popen([str(binary), str(cfg)], stdout=log, stderr=log)
                procs.append(server)
                for _ in range(30):
                    if server.poll() is not None:
                        raise RuntimeError((temp/'video.log').read_text())
                    try:
                        with socket.create_connection(('127.0.0.1', port), timeout=.1):
                            break
                    except OSError:
                        time.sleep(.1)
                streams = []
                for path in ('fpv1', 'fpv2'):
                    c = json.loads((ROOT/f'config/video-{path}.json').read_text())
                    c['size'] = '640x360'
                    c['url'] = f'rtsp://127.0.0.1:{port}/{path}'
                    publisher = subprocess.Popen(command(c), stdout=log, stderr=log)
                    procs.append(publisher)
                    streams.append(c['url'])
                time.sleep(1)
                report['video'] = []
                for url in streams:
                    result = subprocess.run(['ffprobe', '-v', 'error', '-rtsp_transport', 'tcp',
                                             '-show_entries', 'stream=codec_name,width,height', '-of', 'json', url],
                                            text=True, capture_output=True, timeout=12, check=True)
                    info = json.loads(result.stdout)['streams'][0]
                    assert info == {'codec_name': 'h264', 'width': 640, 'height': 360}, info
                    subprocess.run(['ffmpeg', '-v', 'error', '-rtsp_transport', 'tcp', '-i', url,
                                    '-frames:v', '10', '-f', 'null', '-'], stdout=log, stderr=log, timeout=12, check=True)
                    report['video'].append({'path': url.rsplit('/', 1)[-1], **info, 'decoded_frames': 10})
        except Exception:
            for name in ('video.log', 'control.log'):
                p = temp/name
                if p.exists():
                    print(p.read_text()[-6000:], file=sys.stderr)
            raise
        finally:
            for p in reversed(procs):
                stop(p)
    (ROOT/'work').mkdir(exist_ok=True)
    (ROOT/'work/smoke-result.json').write_text(json.dumps(report, indent=2)+'\n')
    print(json.dumps(report, indent=2))

if __name__ == '__main__':
    main()
