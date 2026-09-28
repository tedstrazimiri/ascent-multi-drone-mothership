#!/usr/bin/env python3
"""Stage the relay bundle into the stock image boot partition, without root."""
import hashlib
import json
import lzma
import os
from pathlib import Path
import shutil
import struct
import subprocess
import tarfile
import tempfile

ROOT = Path(__file__).resolve().parents[1]

def sha(path):
    with path.open('rb') as f:
        return hashlib.file_digest(f, 'sha256').hexdigest()

def region_sha(path, start, length):
    h = hashlib.sha256()
    with path.open('rb') as f:
        f.seek(start)
        while length:
            chunk = f.read(min(length, 1024*1024))
            if not chunk:
                raise ValueError('truncated image')
            h.update(chunk)
            length -= len(chunk)
    return h.hexdigest()

def main():
    lock = json.loads((ROOT / 'config/downloads.json').read_text())
    for artifact in ('raspios', 'mediamtx-arm64'):
        p = ROOT / '.cache' / lock[artifact]['url'].rsplit('/', 1)[-1]
        if not p.is_file() or sha(p) != lock[artifact]['sha256']:
            raise SystemExit(f'Run scripts/fetch.py {artifact} first')
    dist = ROOT / 'dist'
    dist.mkdir(exist_ok=True)
    mcopy = shutil.which('mcopy') or str(ROOT / '.cache/mtools/usr/bin/mcopy')
    mmd = shutil.which('mmd') or str(ROOT / '.cache/mtools/usr/bin/mmd')
    if not Path(mcopy).is_file() or not Path(mmd).is_file():
        raise SystemExit('mtools required; see docs/IMAGE.md for a user-local installation')
    bundle = dist / 'ascent-relay-bundle.tar.gz'
    with tarfile.open(bundle, 'w:gz') as tar:
        for name in ('README.md', 'relay', 'scripts', 'systemd', 'config', 'docs', 'tests'):
            p = ROOT / name
            tar.add(p, arcname='ascent-relay/' + name,
                    filter=lambda info: None if '__pycache__' in info.name or info.name.endswith('.pyc') else info)
        p = ROOT / '.cache' / lock['mediamtx-arm64']['url'].rsplit('/', 1)[-1]
        tar.add(p, arcname='ascent-relay/.cache/' + p.name)
        packages = ROOT/'.cache/debs'
        if (packages/'SHA256SUMS').exists():
            tar.add(packages, arcname='ascent-relay/.cache/debs')
    checksum = dist / 'ascent-relay-bundle.tar.gz.sha256'
    checksum.write_text(sha(bundle) + '  ' + bundle.name + '\n')
    output = dist / 'ascent-relay-pi4-2026-09-15-staged.img'
    if output.exists() or output.is_symlink():
        raise SystemExit(f'Image already exists; move it aside before rebuilding: {output}')
    source = ROOT / '.cache' / lock['raspios']['url'].rsplit('/', 1)[-1]
    partial = output.with_suffix('.img.part')
    # Exclusive creation prevents following a symlink or clobbering an existing file.
    with lzma.open(source, 'rb') as src, partial.open('xb') as dst:
        shutil.copyfileobj(src, dst, 1024*1024)
    with partial.open('rb') as f:
        mbr = f.read(512)
    if mbr[510:512] != b'\x55\xaa':
        raise SystemExit('unexpected image layout')
    partitions = []
    for i in range(4):
        entry = mbr[446 + i*16:462 + i*16]
        start, count = struct.unpack('<II', entry[8:16])
        if count:
            partitions.append({'type': entry[4], 'start': start*512, 'bytes': count*512})
    if len(partitions) != 2 or partitions[0]['type'] not in (0x0b, 0x0c) or partitions[1]['type'] != 0x83:
        raise SystemExit('unexpected partition types; inspect manually')
    rootpart = partitions[1]
    original_root = region_sha(partial, rootpart['start'], rootpart['bytes'])
    fat = f'{partial}@@{partitions[0]["start"]}'
    subprocess.run([mmd, '-i', fat, '::/ascent'], check=True)
    for p in (bundle, checksum, ROOT/'scripts/install-from-boot.sh', ROOT/'docs/IMAGE.md'):
        subprocess.run([mcopy, '-i', fat, str(p), '::/ascent/' + p.name], check=True)
    # Read back the exact archive from the FAT image, not merely the source file.
    with tempfile.TemporaryDirectory(dir=dist) as temp:
        readback = Path(temp)/bundle.name
        subprocess.run([mcopy, '-i', fat, '::/ascent/'+bundle.name, str(readback)], check=True)
        if sha(readback) != sha(bundle):
            raise SystemExit('boot payload readback mismatch')
    if region_sha(partial, rootpart['start'], rootpart['bytes']) != original_root:
        raise SystemExit('root partition unexpectedly changed')
    partial.replace(output)
    manifest = {'base': lock['raspios'], 'image': output.name, 'image_bytes': output.stat().st_size,
                'image_sha256': sha(output), 'bundle_sha256': sha(bundle),
                'root_partition_unchanged_sha256': original_root, 'partitions': partitions,
                'verification': 'SHA256 base; FAT payload readback; unchanged root partition. NOT boot-tested.',
                'provisioning': 'Manual first boot: sudo bash /boot/firmware/ascent/install-from-boot.sh; needs apt network access. Services initially disabled.'}
    (dist/'image-manifest.json').write_text(json.dumps(manifest, indent=2)+'\n')
    (dist/(output.name+'.sha256')).write_text(manifest['image_sha256']+'  '+output.name+'\n')
    print(json.dumps(manifest, indent=2))

if __name__ == '__main__':
    main()
