#!/usr/bin/env bash
# SPDX-License-Identifier: Apache-2.0
set -euo pipefail
task_dir="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
cd "$task_dir"
if [[ "${1:-}" == '--setup' ]]; then
    exec /usr/bin/python3 agent.py --setup
fi
if [[ "${1:-}" == '--install-service' ]]; then
    exec /usr/bin/python3 install_service.py
fi
/usr/bin/python3 build_extension.py --install
# Reuse a running authenticated service; never accidentally connect to an unrelated server.
if ! /usr/bin/python3 - <<'PY'
import json, urllib.request
from agent import load_settings, PORT
try:
    r = urllib.request.Request(f'http://127.0.0.1:{PORT}/status', headers={'Authorization':'Bearer '+load_settings()['token']})
    with urllib.request.urlopen(r,timeout=2) as response:
        data=json.load(response)
        assert 'key_configured' in data
except Exception:
    raise SystemExit(1)
PY
then
    # systemd owns the service so it survives closing the launching terminal.
    if [[ -f "$HOME/.config/systemd/user/packettracer-agent.service" ]]; then
        systemctl --user start packettracer-agent.service
    else
        systemd-run --user --unit=packettracer-agent --collect \
            --description='Packet Tracer agent service' /usr/bin/python3 "$task_dir/agent.py"
    fi
    task_service_ready=0
    for task_try in {1..20}; do
        if /usr/bin/python3 - <<'PY'
import urllib.request
from agent import load_settings, PORT
try:
    r=urllib.request.Request(f'http://127.0.0.1:{PORT}/status',headers={'Authorization':'Bearer '+load_settings()['token']})
    urllib.request.urlopen(r,timeout=1).close()
except Exception:
    raise SystemExit(1)
PY
        then task_service_ready=1; break; fi
        sleep 0.2
    done
    if [[ "$task_service_ready" != 1 ]]; then
        printf '%s\n' 'Agent service did not start. Run: journalctl --user -u packettracer-agent'
        exit 1
    fi
fi
if [[ "${1:-}" == '--service-only' ]]; then exit 0; fi
exec /opt/pt/packettracer.AppImage "$@"
