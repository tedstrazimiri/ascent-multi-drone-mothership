#!/usr/bin/env python3
"""Fetch pinned artifacts, verify SHA-256, never write a block device."""
import argparse
import hashlib
import json
from pathlib import Path
import urllib.request

ROOT = Path(__file__).resolve().parents[1]

def digest(path):
    with path.open('rb') as f:
        return hashlib.file_digest(f, 'sha256').hexdigest()

def main():
    lock = json.loads((ROOT / 'config/downloads.json').read_text())
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('artifacts', nargs='+', choices=list(lock))
    args = p.parse_args()
    cache = ROOT / '.cache'
    cache.mkdir(exist_ok=True)
    for name in args.artifacts:
        item = lock[name]
        target = cache / item['url'].rsplit('/', 1)[-1]
        if not target.exists() or digest(target) != item['sha256']:
            part = target.with_suffix(target.suffix + '.part')
            print(f'Downloading {name}', flush=True)
            with urllib.request.urlopen(item['url'], timeout=60) as src, part.open('wb') as dst:
                while chunk := src.read(1024 * 1024):
                    dst.write(chunk)
            if digest(part) != item['sha256']:
                raise SystemExit(f'Checksum mismatch: {part}; not using download')
            part.replace(target)
        print(f'VERIFIED {name}: {target}', flush=True)

if __name__ == '__main__':
    main()
