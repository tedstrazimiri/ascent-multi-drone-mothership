#!/usr/bin/env python3
"""Resolve ARM64 packages against the exact stock image, using isolated APT state."""
import hashlib
import json
from pathlib import Path
import shutil
import subprocess

ROOT = Path(__file__).resolve().parents[1]

def main():
    state = ROOT/'work/apt'
    state.mkdir(parents=True, exist_ok=True)
    manifest = json.loads((ROOT/'dist/image-manifest.json').read_text())
    image = ROOT/'dist'/manifest['image']
    rootpart = state/'root.ext4'
    partition = manifest['partitions'][1]
    if not rootpart.exists():
        with image.open('rb') as src, rootpart.open('xb') as dst:
            src.seek(partition['start'])
            remaining = partition['bytes']
            while remaining:
                chunk = src.read(min(1024*1024, remaining))
                if not chunk:
                    raise RuntimeError('short image')
                dst.write(chunk)
                remaining -= len(chunk)
    with rootpart.open('rb') as f:
        if hashlib.file_digest(f,'sha256').hexdigest() != manifest['root_partition_unchanged_sha256']:
            raise RuntimeError('root partition hash mismatch')
    for source, dest in [('/var/lib/dpkg/status','status'),
                         ('/usr/share/keyrings/debian-archive-keyring.pgp','debian.pgp'),
                         ('/usr/share/keyrings/raspberrypi-archive-keyring.pgp','raspberrypi.pgp')]:
        target = state/dest
        if target.exists():
            target.unlink()
        subprocess.run(['debugfs','-R',f'dump {source} "{target}"',str(rootpart)],check=True)
        if not target.is_file() or target.stat().st_size == 0:
            raise RuntimeError('could not extract '+source)
    for directory in ('lists/partial','archives/partial'):
        (state/directory).mkdir(parents=True,exist_ok=True)
    (state/'sources.list').write_text(
        f'deb [arch=arm64 signed-by={state}/debian.pgp] https://deb.debian.org/debian trixie main\n'
        f'deb [arch=arm64 signed-by={state}/debian.pgp] https://deb.debian.org/debian trixie-updates main\n'
        f'deb [arch=arm64 signed-by={state}/debian.pgp] https://deb.debian.org/debian-security trixie-security main\n'
        f'deb [arch=arm64 signed-by={state}/raspberrypi.pgp] https://archive.raspberrypi.com/debian trixie main\n')
    # deb822 avoids ambiguity from spaces in repository-local paths.
    sources = ''
    for uri, suites, key in [('https://deb.debian.org/debian','trixie trixie-updates','debian'),
                              ('https://deb.debian.org/debian-security','trixie-security','debian'),
                              ('https://archive.raspberrypi.com/debian','trixie','raspberrypi')]:
        sources += f'Types: deb\nURIs: {uri}\nSuites: {suites}\nComponents: main\nArchitectures: arm64\nSigned-By: {state}/{key}.pgp\n\n'
    # APT splits Signed-By on whitespace too: use a stable no-space cache path.
    alias = Path.home()/'.cache/ascent-apt'
    if alias.is_symlink():
        if alias.resolve() != state:
            raise RuntimeError('ascent-apt alias belongs to another workspace')
    elif alias.exists():
        raise RuntimeError('ascent-apt path exists and is not this workspace alias')
    else:
        alias.symlink_to(state,target_is_directory=True)
    sources = sources.replace(str(state),str(alias))
    (state/'sources.sources').write_text(sources)
    cfg = state/'apt.conf'
    cfg.write_text(f'''APT::Architecture "arm64";
#clear APT::Architectures;
APT::Architectures {{ "arm64"; }};
Dir::Etc::sourcelist "{state}/sources.sources";
Dir::Etc::sourceparts "-";
Dir::Etc::parts "-";
Dir::Etc::main "-";
Dir::State::status "{state}/status";
Dir::State::lists "{state}/lists";
Dir::Cache::archives "{state}/archives";
Dir::Cache::pkgcache "{state}/pkgcache.bin";
Dir::Cache::srcpkgcache "{state}/srcpkgcache.bin";
Dir::State::extended_states "{state}/extended_states";
Dir::Log "{state}";
Acquire::Languages "none";
APT::Install-Recommends "false";
APT::Install-Suggests "false";
''')
    subprocess.run(['apt-get','-c',str(cfg),'update'],check=True)
    packages = ['python3','ffmpeg','v4l-utils','usbutils','iperf3','wireguard-tools','ripgrep']
    subprocess.run(['apt-get','-c',str(cfg),'--download-only','--no-install-recommends','-y','install',*packages],check=True)
    dest = ROOT/'.cache/debs'
    dest.mkdir(exist_ok=True)
    records = []
    for source in sorted((state/'archives').glob('*.deb')):
        target = dest/source.name
        shutil.copy2(source,target)
        with target.open('rb') as f:
            records.append({'file':target.name,'sha256':hashlib.file_digest(f,'sha256').hexdigest()})
    if not records:
        raise RuntimeError('no packages downloaded')
    (dest/'manifest.json').write_text(json.dumps({'packages':packages,'base_root_sha256':manifest['root_partition_unchanged_sha256'],'files':records},indent=2)+'\n')
    (dest/'SHA256SUMS').write_text(''.join(f'{r["sha256"]}  {r["file"]}\n' for r in records))
    print(f'Prepared {len(records)} signed-repository ARM64 package files for offline first boot.')

if __name__ == '__main__':
    main()
