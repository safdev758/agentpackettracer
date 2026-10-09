# SPDX-License-Identifier: Apache-2.0
"""Install the local agent as a user service that starts at desktop login."""
import json
import subprocess
import urllib.request
from pathlib import Path
from agent import PORT, ROOT, load_settings


def install():
    request = urllib.request.Request(f'http://127.0.0.1:{PORT}/status',
        headers={'Authorization': 'Bearer ' + load_settings()['token']})
    try:
        with urllib.request.urlopen(request, timeout=2) as response:
            if json.load(response).get('active_run'):
                raise SystemExit('Finish or stop the active task before installing the service.')
    except (OSError, urllib.error.URLError):
        pass
    directory = Path.home() / '.config' / 'systemd' / 'user'
    directory.mkdir(parents=True, exist_ok=True)
    # systemd unit values need their own escaping, not shell interpolation.
    escaped_root = str(ROOT).replace('\\', '\\\\').replace('"', '\\"').replace('%', '%%')
    (directory / 'packettracer-agent.service').write_text(
        '[Unit]\nDescription=Packet Tracer Agent and on-demand Codex worker\n'
        '[Service]\nType=simple\n'
        f'WorkingDirectory={escaped_root}\n'
        f'ExecStart=/usr/bin/python3 "{escaped_root}/agent.py"\n'
        'Restart=on-failure\nRestartSec=2\nEnvironment=PYTHONUNBUFFERED=1\n'
        '[Install]\nWantedBy=default.target\n')
    for command in [('daemon-reload',), ('stop', 'packettracer-agent.service'), ('daemon-reload',),
                    ('enable', '--now', 'packettracer-agent.service')]:
        subprocess.run(['systemctl', '--user', *command], check=True)
    subprocess.run(['systemctl', '--user', 'is-active', '--quiet', 'packettracer-agent.service'], check=True)
    print('Agent service installed and enabled at desktop login. Codex workers start on @codex requests.')


if __name__ == '__main__':
    install()
