#!/usr/bin/env python3
"""Configure this one Pi image privately for unattended SSH and provisioning."""
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import uuid

ROOT = Path(__file__).resolve().parents[1]

def run(args):
    return subprocess.check_output(args, text=True, stderr=subprocess.PIPE).rstrip('\n')

def sha(path):
    with path.open('rb') as f:
        return hashlib.file_digest(f, 'sha256').hexdigest()

def main():
    os.umask(0o077)
    work = ROOT/'work/private'
    work.mkdir(parents=True, exist_ok=True)
    work.chmod(0o700)
    dist = ROOT/'dist'
    manifest = json.loads((dist/'image-manifest.json').read_text())
    image = dist/manifest['image']
    if sha(image) != manifest['image_sha256']:
        raise SystemExit('Base staged image hash mismatch or already personalized; rebuild first')
    image.chmod(0o600)
    ssh = Path.home()/'.ssh'
    ssh.mkdir(mode=0o700, exist_ok=True)
    key = ssh/'ascent_ed25519'
    if not key.exists():
        subprocess.run(['ssh-keygen', '-q', '-t', 'ed25519', '-N', '', '-C', 'ascent-relay-laptop', '-f', str(key)], check=True)
    public = run(['ssh-keygen', '-y', '-f', str(key)])
    hostkey = work/'ssh_host_ed25519_key'
    if not hostkey.exists():
        subprocess.run(['ssh-keygen', '-q', '-t', 'ed25519', '-N', '', '-C', 'ascent-relay-host', '-f', str(hostkey)], check=True)
    hostpub = run(['ssh-keygen', '-y', '-f', str(hostkey)])
    user = {
        'hostname': 'ascent-relay', 'manage_etc_hosts': True, 'manage_resolv_conf': False,
        'timezone': 'America/Toronto', 'enable_ssh': True, 'ssh_pwauth': False,
        'disable_root': True, 'ssh_deletekeys': True,
        'ssh_keys': {'ed25519_private': hostkey.read_text(), 'ed25519_public': hostpub},
        'users': [{'name': 'ted', 'groups': ['adm','dialout','audio','video','plugdev','input','gpio','i2c','spi','netdev','sudo'],
                   'shell': '/bin/bash', 'lock_passwd': True, 'sudo': ['ALL=(ALL) NOPASSWD:ALL'],
                   'ssh_authorized_keys': [public]}],
        'rpi': {'interfaces': {'serial': {'console': False, 'hardware': True}}},
        'write_files': [
            {'path': '/usr/local/sbin/ascent-firstboot', 'permissions': '0755', 'content': (ROOT/'scripts/firstboot.sh').read_text()},
            {'path': '/etc/systemd/system/ascent-firstboot.service', 'permissions': '0644', 'content': (ROOT/'systemd/ascent-firstboot.service').read_text()},
            {'path': '/etc/ssh/sshd_config.d/10-ascent.conf', 'permissions': '0644',
             'content': 'PasswordAuthentication no\nKbdInteractiveAuthentication no\nPermitRootLogin no\nPubkeyAuthentication yes\n'},
        ],
        'runcmd': [['systemctl','daemon-reload'], ['systemctl','enable','--now','--no-block','ascent-firstboot.service']],
        'final_message': 'Ascent SSH setup complete; inspect ascent-firstboot.service for package/video readiness.'
    }
    # JSON is valid YAML; cloud-init dispatch uses the explicit cloud-config header.
    (work/'user-data').write_text('#cloud-config\n' + json.dumps(user, indent=2) + '\n')
    instance = 'ascent-relay-' + uuid.uuid4().hex
    (work/'meta-data').write_text(json.dumps({'instance-id': instance, 'local-hostname': 'ascent-relay'})+'\n')
    network = {'network': {'version': 2, 'renderer': 'NetworkManager', 'ethernets': {'eth0': {'dhcp4': True, 'dhcp6': True, 'optional': True}}}}
    wifi = False
    # Capture credentials directly into a private image file; never print them.
    active = run(['nmcli','-t','-f','UUID,TYPE,DEVICE','connection','show','--active'])
    for line in active.splitlines():
        ident, kind, device = line.split(':', 2)
        if kind != '802-11-wireless':
            continue
        ssid = run(['nmcli','--escape','no','-g','802-11-wireless.ssid','connection','show',ident])
        security = run(['nmcli','-g','802-11-wireless-security.key-mgmt','connection','show',ident])
        if security != 'wpa-psk':
            continue
        secret = run(['nmcli','--escape','no','--show-secrets','-g','802-11-wireless-security.psk','connection','show',ident])
        if not secret:
            continue
        network['network']['wifis'] = {'wlan0': {'dhcp4': True, 'optional': True, 'regulatory-domain': 'CA',
                                               'access-points': {ssid: {'password': secret}}}}
        wifi = True
        break
    (work/'network-config').write_text(json.dumps(network, indent=2)+'\n')
    mcopy = shutil.which('mcopy') or str(ROOT/'.cache/mtools/usr/bin/mcopy')
    fat = f'{image}@@{manifest["partitions"][0]["start"]}'
    # Disable GPIO UART console even during very early boot. Preserve all other boot arguments.
    subprocess.run([mcopy, '-i', fat, '::/cmdline.txt', str(work/'cmdline.txt')], check=True)
    cmdline = (work/'cmdline.txt').read_text().strip().split()
    cmdline = [x for x in cmdline if not (x.startswith('console=serial') or x.startswith('console=ttyAMA')
                                        or x.startswith('console=ttyS') or x.startswith('earlycon')
                                        or x.startswith('ds=nocloud') or x.startswith('cfg80211.ieee80211_regdom='))]
    cmdline += ['ds=nocloud;i='+instance, 'cfg80211.ieee80211_regdom=CA']
    (work/'cmdline.txt').write_text(' '.join(cmdline)+'\n')
    subprocess.run([mcopy, '-i', fat, '::/config.txt', str(work/'config.txt')], check=True)
    with (work/'config.txt').open('a') as f:
        f.write('\n# Ascent PL011 UART begin\n[all]\nenable_uart=1\n'
                'dtoverlay=disable-bt\n# Ascent PL011 UART end\n')
    for name in ('user-data','meta-data','network-config','cmdline.txt','config.txt'):
        subprocess.run([mcopy, '-o', '-i', fat, str(work/name), '::/'+name], check=True)
        readback = work/('readback-'+name)
        subprocess.run([mcopy,'-o','-i',fat,'::/'+name,str(readback)],check=True)
        if sha(readback) != sha(work/name):
            raise SystemExit('FAT customization readback failed: '+name)
    (ssh/'known_hosts_ascent').write_text('ascent-relay.local ' + hostpub + '\n')
    (ssh/'known_hosts_ascent').chmod(0o600)
    confdir = ssh/'config.d'
    confdir.mkdir(mode=0o700, exist_ok=True)
    conf = confdir/'ascent.conf'
    if conf.exists() and '# Managed Ascent relay access' not in conf.read_text():
        raise SystemExit('Existing unmanaged ascent SSH config; inspect before replacing')
    conf.write_text('# Managed Ascent relay access\nHost ascent-pi\n  HostName ascent-relay.local\n  User ted\n'
                    '  IdentityFile ~/.ssh/ascent_ed25519\n  IdentitiesOnly yes\n  UserKnownHostsFile ~/.ssh/known_hosts_ascent\n'
                    '  StrictHostKeyChecking yes\n  ServerAliveInterval 15\n  ServerAliveCountMax 3\n')
    config = ssh/'config'
    existing = config.read_text() if config.exists() else ''
    include = 'Include ~/.ssh/config.d/ascent.conf'
    if include not in existing:
        if config.exists():
            backup = ssh/'config.before-ascent'
            if not backup.exists():
                shutil.copy2(config, backup)
        config.write_text(include+'\n'+existing)
        config.chmod(0o600)
    final = {**manifest, 'image_sha256': sha(image), 'personalized': True,
             'hostname': 'ascent-relay', 'ssh_user': 'ted', 'ssh_alias': 'ascent-pi',
             'wifi_configured': wifi, 'ethernet': 'DHCP', 'ssh_host_fingerprint': run(['ssh-keygen','-lf',str(hostkey)+'.pub']),
             'provisioning': 'Automatic firstboot service with retry; offline package bundle when present; one synthetic stream enabled.',
             'verification': 'Customized FAT files read back byte-for-byte. Not boot-tested.'}
    (dist/'personalized-manifest.json').write_text(json.dumps(final, indent=2)+'\n')
    (dist/(image.name+'.sha256')).write_text(final['image_sha256']+'  '+image.name+'\n')
    print(json.dumps({k: final[k] for k in ('image','image_sha256','hostname','ssh_user','ssh_alias','wifi_configured','verification')}, indent=2))

if __name__ == '__main__':
    main()
