#!/usr/bin/env python3
"""Install a user-local launcher and service. Does not enable login autostart."""
from pathlib import Path
import subprocess

root = Path(__file__).resolve().parent.parent
units = Path.home() / '.config/systemd/user'
apps = Path.home() / '.local/share/applications'
units.mkdir(parents=True, exist_ok=True)
apps.mkdir(parents=True, exist_ok=True)
unit = units / 'ascent-console.service'
unit.write_text(f'''[Unit]
Description=Ascent graphical setup console
After=network-online.target

[Service]
Type=simple
WorkingDirectory={root}
ExecStart=/usr/bin/python3 -m relay.console
Environment=PYTHONUNBUFFERED=1
Restart=on-failure
RestartSec=3
TimeoutStopSec=10

[Install]
WantedBy=default.target
''')
(apps / 'ascent-control-room.desktop').write_text(f'''[Desktop Entry]
Type=Application
Name=Ascent Control Room
Comment=TX15 calibration, relay connections, video and disarmed bench tests
Exec=/usr/bin/python3 "{root / 'scripts/open-console.py'}"
Icon=input-gaming
Terminal=false
Categories=Utility;Engineering;
''')
subprocess.run(['systemctl', '--user', 'daemon-reload'], check=True)
subprocess.run(['systemctl', '--user', 'start', 'ascent-console.service'], check=True)
print('Installed Ascent Control Room launcher. Local console: http://127.0.0.1:8767')
