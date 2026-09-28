#!/usr/bin/env python3
"""Write ONLY the explicitly identified SD in a private flash plan; verify readback."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import stat
import subprocess
import time

def digest(path, size=None):
    h = hashlib.sha256()
    with open(path, 'rb', buffering=0) as f:
        while size is None or size > 0:
            chunk = f.read(4*1024*1024 if size is None else min(size,4*1024*1024))
            if not chunk:
                if size:
                    raise RuntimeError('Short device readback')
                break
            h.update(chunk)
            if size is not None:
                size -= len(chunk)
    return h.hexdigest()

def output(args):
    return subprocess.check_output(args, text=True).strip()

def validate(plan):
    device = Path(plan['device'])
    if device.resolve() != device or not stat.S_ISBLK(device.stat().st_mode):
        raise RuntimeError('Target must be the exact block-device path')
    if not device.name.startswith('mmcblk') or 'p' in device.name:
        raise RuntimeError('This workflow only accepts whole MMC/SD cards')
    sysfs = Path('/sys/class/block')/device.name
    if (sysfs/'device/type').read_text().strip() != 'SD':
        raise RuntimeError('Target is not an SD card')
    if (sysfs/'device/cid').read_text().strip() != plan['cid']:
        raise RuntimeError('SD card identity changed')
    capacity = int((sysfs/'size').read_text())*512
    if capacity != plan['device_bytes']:
        raise RuntimeError('SD card capacity changed')
    root_source = output(['findmnt','-no','SOURCE','/'])
    parents = output(['lsblk','-sno','PATH',root_source]).splitlines()
    if str(device) in parents or root_source.startswith(str(device)):
        raise RuntimeError('Refusing the system disk')
    image = Path(plan['image'])
    if image.is_symlink() or not image.is_file() or image.stat().st_size > capacity:
        raise RuntimeError('Invalid image or insufficient card capacity')
    if digest(image) != plan['image_sha256']:
        raise RuntimeError('Image checksum mismatch')
    return device, image

def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--plan', required=True)
    p.add_argument('--check-only', action='store_true')
    args = p.parse_args()
    plan_path = Path(args.plan).resolve()
    plan = json.loads(plan_path.read_text())
    device, image = validate(plan)
    print(f'Identified SD: {device}, {plan["device_bytes"]} bytes; image SHA256 verified.', flush=True)
    if args.check_only:
        return
    if os.geteuid() != 0:
        raise SystemExit('Root is required to write the SD card; use local pkexec authentication.')
    tree = json.loads(output(['lsblk','--json','--paths','-o','NAME,TYPE',str(device)]))
    for part in tree['blockdevices'][0].get('children', []):
        if part['type'] != 'part':
            raise RuntimeError('Unexpected non-partition child')
        mounted = subprocess.run(['findmnt','-rn','-S',part['name'],'-o','TARGET'],capture_output=True,text=True)
        if mounted.returncode == 0:
            # Unmount by device so spaces/escapes in desktop mount names cannot redirect it.
            subprocess.run(['umount',part['name']],check=True)
    # Check card identity again immediately before mutation.
    if (Path('/sys/class/block')/device.name/'device/cid').read_text().strip() != plan['cid']:
        raise RuntimeError('Card changed immediately before write')
    status_path = plan_path.parent/'flash-status.json'
    status_path.write_text(json.dumps({'state':'writing','device':str(device),'started':time.time()})+'\n')
    subprocess.run(['dd',f'if={image}',f'of={device}','bs=4M','conv=fsync','status=progress'],check=True)
    subprocess.run(['blockdev','--flushbufs',str(device)],check=True)
    readback = digest(device, image.stat().st_size)
    if readback != plan['image_sha256']:
        status_path.write_text(json.dumps({'state':'readback_failed','expected':plan['image_sha256'],'actual':readback})+'\n')
        raise RuntimeError('SD readback differs from image')
    subprocess.run(['blockdev','--rereadpt',str(device)],check=True)
    os.sync()
    status = {'state':'verified','device':str(device),'bytes_verified':image.stat().st_size,
              'sha256':readback,'completed':time.time(),'boot_test':'pending'}
    status_path.write_text(json.dumps(status,indent=2)+'\n')
    os.chmod(status_path,0o644)
    print(json.dumps(status,indent=2),flush=True)

if __name__ == '__main__':
    main()
