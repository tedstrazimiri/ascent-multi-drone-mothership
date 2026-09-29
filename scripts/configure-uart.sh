#!/usr/bin/env bash
# Pi 4 only: give GPIO14/15 the PL011 UART. Does not transmit or reboot.
set -euo pipefail
[[ $(id -u) == 0 ]] || { echo 'Run with sudo on the Raspberry Pi.' >&2; exit 1; }
model=$(tr -d '\0' </proc/device-tree/model)
[[ $model == *'Raspberry Pi 4 Model B'* ]] || { echo 'Requires a Raspberry Pi 4B.' >&2; exit 1; }
python3 - <<'PY'
from pathlib import Path
import datetime
import shutil

stamp = datetime.datetime.now(datetime.timezone.utc).strftime('%Y%m%dT%H%M%S%fZ')
def save(path, text):
    original = path.read_text()
    if original != text:
        backup = path.with_name(path.name + '.before-ascent-uart-' + stamp)
        shutil.copy2(path, backup)
        path.write_text(text)
        print(f'Updated {path}; backup {backup}')

config = Path('/boot/firmware/config.txt')
begin, end = '# Ascent PL011 UART begin', '# Ascent PL011 UART end'
text = config.read_text()
if text.count(begin) != text.count(end) or text.count(begin) > 1:
    raise SystemExit('Malformed Ascent UART block; inspect config.txt')
if begin in text:
    start, finish = text.index(begin), text.index(end) + len(end)
    if finish < start:
        raise SystemExit('Reversed Ascent UART markers; inspect config.txt')
    text = text[:start] + text[finish:]
block = f'{begin}\n[all]\nenable_uart=1\ndtoverlay=disable-bt\n{end}\n'
save(config, text.rstrip() + '\n\n' + block)

cmdline = Path('/boot/firmware/cmdline.txt')
args = cmdline.read_text().split()
args = [arg for arg in args if not arg.startswith(
    ('console=serial', 'console=ttyAMA', 'console=ttyS', 'earlycon'))]
save(cmdline, ' '.join(args) + '\n')
PY
if systemctl cat hciuart.service >/dev/null 2>&1; then
  systemctl disable --now hciuart.service
fi
systemctl disable --now serial-getty@serial0.service serial-getty@ttyS0.service serial-getty@ttyAMA0.service
echo 'PL011 configured; onboard Bluetooth disabled. Reboot to apply. No RC output enabled.'
