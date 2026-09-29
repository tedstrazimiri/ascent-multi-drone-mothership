#!/usr/bin/env python3
"""Open the graphical console from the desktop launcher."""
import subprocess
import time
import urllib.request
import webbrowser

subprocess.run(['systemctl', '--user', 'start', 'ascent-console.service'], check=True)
for attempt in range(30):
    try:
        urllib.request.urlopen('http://127.0.0.1:8767/api/state', timeout=1).close()
        break
    except OSError:
        time.sleep(.2)
webbrowser.open('http://127.0.0.1:8767')
