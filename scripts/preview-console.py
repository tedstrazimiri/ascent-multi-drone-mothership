#!/usr/bin/env python3
"""Offline UI fixture: synthetic telemetry only, no device/SSH/control imports.

Run with python3 scripts/preview-console.py, open http://127.0.0.1:8768/.
The banner and video test pattern deliberately identify simulation.
"""
import argparse
import copy
import json
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
import threading
import time

ROOT = Path(__file__).resolve().parent.parent
FIXTURE = {
    'preview': True, 'token': 'offline-preview', 'fc_enabled': True,
    'settings': {'host':'192.168.8.175','transport':'hls','seconds':60,'video_bitrate':1},
    'mapping': json.loads((ROOT / 'config/joystick-tx15-bench.json').read_text()),
    'hid': {'connected':True,'axes':{'0':0,'1':0,'2':-32767,'3':0,'5':-32767},
            'buttons':{},'channels':[992,992,172,992]+[172]*12,'enabled':False},
    'fc': {'connected':True,'armed':False,'sbus':True,'channels':[1500,1500,1500,987]+[987]*14,
           'cells':6,'voltage':23.72,'arming_blockers':[]},
    'pi': {'connected':True,'checking':False,'host':'192.168.8.175','hostname':'ascent-relay',
           'ping_ms':4.7,'video':'active','media':'active','driver':True,'receiver':True,'key':True},
    'video': {'available':True},
    'arm_profile':{'ready':True,'message':'SIMULATION · indoor profile ready'},
    'session':{'active':False,'state':'idle','message':'Preview only','frames':0},
    'job':{'busy':False,'message':''},
    'logs':[{'time':'00:00:00','level':'info','text':'SIMULATION · no hardware access or control output'}],
}
PATTERN = '''<!doctype html><html><head><style>
*{box-sizing:border-box}body{margin:0;background:#0c2029;color:#c9e4df;display:grid;place-items:center;height:100vh;font:14px monospace;overflow:hidden}svg{position:absolute;width:100%;height:100%}.label{position:relative;padding:12px 18px;background:#0b1723c9;border:1px solid #587782;text-align:center;letter-spacing:3px;font-size:12px}.label small{display:block;font-size:9px;letter-spacing:2px;margin-top:8px;color:#9bafb5}
</style></head><body><svg viewBox="0 0 1280 720" preserveAspectRatio="xMidYMid slice"><defs><linearGradient id="sky" x2="0" y2="1"><stop stop-color="#345763"/><stop offset="1" stop-color="#9eb4ad"/></linearGradient><pattern id="grid" width="80" height="80" patternUnits="userSpaceOnUse"><path d="M80 0H0V80" fill="none" stroke="#71918d" opacity=".12"/></pattern></defs><path fill="url(#sky)" d="M0 0h1280v720H0z"/><path fill="#53746f" d="m0 460 170-210 70 120 180-240 185 250 165-210 185 270 200-220 125 150v400H0z"/><path fill="#2e5552" d="m0 550 280-180 150 180 180-220 145 250 120-90 120-130 285 280v160H0z"/><path fill="#1c3839" d="m0 650 230-100 100 100 190-70 240 100 190-190 330 210v80H0z"/><path fill="url(#grid)" d="M0 0h1280v720H0z"/><g stroke="#bed4c3" opacity=".5" fill="none"><path d="M570 360h35m70 0h35M640 290v35m0 70v35"/><circle cx="640" cy="360" r="65"/></g></svg><div class="label">SIMULATED VIDEO<small>LAYOUT TEST / NO LIVE CAMERA</small></div></body></html>'''

class FixtureHandler(BaseHTTPRequestHandler):
    fixture = copy.deepcopy(FIXTURE)
    lock = threading.Lock()
    def log_message(self, *args): pass
    def send(self, status, value, kind='application/json'):
        body=json.dumps(value).encode() if kind=='application/json' else value.encode()
        self.send_response(status); self.send_header('Content-Type',kind)
        self.send_header('Content-Length',str(len(body)));self.send_header('Cache-Control','no-store');self.end_headers()
        try:self.wfile.write(body)
        except (BrokenPipeError,ConnectionResetError):pass
    def do_GET(self):
        path=self.path.split('?')[0]
        if path=='/api/state':
            with self.lock:
                s=copy.deepcopy(self.fixture)
            now=time.time()
            for key in ('video','pi','fc','hid'):s[key]['updated']=now
            q=s['session']
            if q['active']:
                elapsed=now-q['started']
                if elapsed<2:q.update(state='preparing',message='Checking and preparing the relay…')
                elif elapsed<5:q.update(state='recovering',message='Hold SA low for a moment…',frames=25)
                elif elapsed<9:q.update(state='ready',message='Ready — move SA high.',frames=100)
                elif elapsed<11:
                    q.update(state='live',message='ARM requested · automatic cutoff in two seconds',frames=150)
                    s['hid']['axes']['5']=32767;s['hid']['enabled']=True;s['fc']['armed']=True;s['fc']['channels'][4]=2011
                else:
                    q.update(active=False,state='stopped',message='Two-second test complete. Lower SA and click Test again.',frames=200)
                    with self.lock:self.fixture['session']=copy.deepcopy(q)
            self.send(200,s)
        elif path=='/preview-feed':self.send(200,PATTERN,'text/html')
        elif path in ('/','/style.css','/app.js','/video-player.js',
                      '/vendor/mediamtx-reader.js','/latency-target.html','/latency-target.js'):
            self.send(200,(ROOT/'web'/('index.html' if path=='/' else path[1:])).read_text(),
                      'text/html' if path=='/' or path.endswith('.html') else 'text/css' if path.endswith('css') else 'text/javascript')
        else:self.send(404,{'error':'Not found'})
    def do_POST(self):
        if self.headers.get('Origin')!=f'http://127.0.0.1:{self.server.server_port}' or self.headers.get('X-Console-Token')!='offline-preview':
            self.send(403,{'error':'Local fixture only'});return
        data=json.loads(self.rfile.read(min(8192,int(self.headers.get('Content-Length','0')))))
        action=self.path.removeprefix('/api/')
        with self.lock:
            s=self.fixture
            if action=='start':s['session']={'active':True,'state':'preparing','kind':data['kind'],'frames':0,'message':'Simulation','started':time.time(),'seconds':60}
            elif action=='stop':s['session'].update(active=False,state='stopped',message='Simulation stopped')
            elif action=='settings':s['settings']=data
            elif action=='mapping':s['mapping']=data
            elif action=='fc':s['fc_enabled']=data['enabled'];s['fc']['connected']=data['enabled']
            elif action=='arm_restore':s['arm_profile']={'ready':False,'message':'SIMULATION · original settings restored'}
            elif action=='arm_prepare':s['arm_profile']={'ready':True,'message':'SIMULATION · indoor profile ready'}
            elif action in ('check','prepare','video_restart','video_bitrate'):pass
            else:self.send(400,{'error':'Unknown fixture action'});return
        self.send(200,{'ok':True})

if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--port',type=int,default=8768)
    args=parser.parse_args()
    print(f'OFFLINE UI SIMULATION: http://127.0.0.1:{args.port}/',flush=True)
    ThreadingHTTPServer(('127.0.0.1',args.port),FixtureHandler).serve_forever()
