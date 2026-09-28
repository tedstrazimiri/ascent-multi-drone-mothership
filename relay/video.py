"""Generate or run a capture-to-RTSP command; default is a labelled test pattern."""
import argparse
import json
import os
import re
import shlex
from urllib.parse import urlsplit

def command(c):
    source, enc = c['source'], c['encoder']
    if source not in ('synthetic', 'v4l2'):
        raise ValueError('source must be synthetic or v4l2')
    if enc not in ('copy', 'h264_v4l2m2m', 'libx264'):
        raise ValueError('unsupported encoder')
    if not re.fullmatch(r'\d{2,4}x\d{2,4}', c['size']):
        raise ValueError('invalid resolution')
    fps = c['fps']
    if type(fps) is not int or not 1 <= fps <= 120:
        raise ValueError('invalid fps')
    if not re.fullmatch(r'\d+[kM]', c['bitrate']):
        raise ValueError('invalid bitrate')
    u = urlsplit(c['url'])
    if u.scheme != 'rtsp' or u.hostname not in ('127.0.0.1', 'localhost') or u.path not in ('/fpv1', '/fpv2'):
        raise ValueError('publish only to local RTSP fpv1/fpv2')
    cmd = ['ffmpeg', '-hide_banner', '-nostdin', '-loglevel', 'warning']
    if source == 'synthetic':
        if enc != 'libx264':
            raise ValueError('synthetic mode uses libx264')
        cmd += ['-re', '-f', 'lavfi', '-i', f"testsrc2=size={c['size']}:rate={fps}"]
        cmd += ['-vf', 'drawtext=text=SYNTHETIC BENCH VIDEO:x=20:y=20:fontsize=30:fontcolor=white:box=1:boxcolor=black']
    else:
        fmt = c['input_format']
        if fmt not in ('h264', 'mjpeg', 'yuyv422', 'nv12'):
            raise ValueError('unsupported input_format; inspect with v4l2-ctl')
        if not c['device'].startswith('/dev/') or 'REPLACE' in c['device']:
            raise ValueError('set the verified /dev/v4l/by-id or by-path capture device')
        if enc == 'copy' and fmt != 'h264':
            raise ValueError('copy mode requires H.264 input')
        cmd += ['-thread_queue_size', '4', '-f', 'v4l2', '-input_format', fmt,
                '-video_size', c['size'], '-framerate', str(fps), '-i', c['device']]
    cmd += ['-an', '-c:v', enc]
    if enc != 'copy':
        cmd += ['-pix_fmt', 'yuv420p', '-b:v', c['bitrate'], '-g', str(fps), '-bf', '0']
    if enc == 'libx264':
        cmd += ['-preset', 'ultrafast', '-tune', 'zerolatency']
    return cmd + ['-f', 'rtsp', '-rtsp_transport', 'tcp', c['url']]

def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('config')
    p.add_argument('--run', action='store_true')
    args = p.parse_args()
    with open(args.config) as f:
        cmd = command(json.load(f))
    print(shlex.join(cmd), flush=True)
    if args.run:
        os.execvp(cmd[0], cmd)

if __name__ == '__main__':
    main()
