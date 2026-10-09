# SPDX-License-Identifier: Apache-2.0
"""Build this user's authenticated, importable Packet Tracer script module."""
import json
import os
import shutil
import sys
from pathlib import Path

from agent import ROOT, load_settings

sys.path.insert(0, str(ROOT / 'vendor' / 'pts-codec'))
from pts_builder import build_pts


def build(install=False):
    settings = load_settings()
    dest = ROOT / 'dist'
    dest.mkdir(exist_ok=True)
    html = (ROOT / 'extension' / 'index.html').read_text().replace('__BRIDGE_TOKEN__', json.dumps(settings['token']))
    result = build_pts(str(dest / 'PacketTracerAgent.pts'), name='Packet Tracer Agent',
        module_id='com.safouane.packettracer.agent', author='Safouane', version='0.2.5',
        description='In-app network assistant with OpenAI, Gemini and OpenRouter: questions, plans, live inspection, configuration and tests. Requires the local Packet Tracer Agent service.',
        # PT 9 requires APPLICATION for Workspace.getLogicalWorkspace; CHANGE_GUI alone is insufficient.
        privileges=['GET_NETWORK_INFO', 'CHANGE_NETWORK_INFO', 'MISC_GUI', 'CHANGE_GUI', 'APPLICATION'],
        loading='ON_STARTUP', scripts={'main.js': (ROOT / 'extension' / 'main.js').read_text()},
        interfaces={'index.html': html, 'ui.js': (ROOT / 'extension' / 'ui.js').read_text().replace('__BRIDGE_TOKEN__', json.dumps(settings['token'])),
                    'styles.css': (ROOT / 'extension' / 'styles.css').read_text()})
    # The artifact contains a private local bridge credential, never a provider key.
    os.chmod(dest / 'PacketTracerAgent.pts', 0o600)
    if install:
        folder = Path.home() / 'pt' / 'extensions' / 'PacketTracerAgent'
        folder.mkdir(parents=True, exist_ok=True)
        shutil.copy2(dest / 'PacketTracerAgent.pts', folder / 'PacketTracerAgent.pts')
        print('Installed:', folder / 'PacketTracerAgent.pts')
    print('Built:', result['path'])
    return result


if __name__ == '__main__':
    build('--install' in sys.argv)
