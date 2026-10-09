# SPDX-License-Identifier: Apache-2.0
"""Install the extension and an additional app launcher for this user."""
from pathlib import Path
from build_extension import build
from agent import ROOT

build(install=True)
apps = Path.home() / '.local' / 'share' / 'applications'
apps.mkdir(parents=True, exist_ok=True)
for name, title, extra, terminal in [
    ('packettracer-agent.desktop', 'Packet Tracer with AI Agent', '', 'false'),
    ('packettracer-agent-setup.desktop', 'Packet Tracer AI — Set API Key', ' --setup', 'true'),
]:
    (apps / name).write_text(f'''[Desktop Entry]
Type=Application
Name={title}
Comment=OpenAI assistant for Cisco Packet Tracer
Exec="{ROOT / 'launch.sh'}"{extra}
Icon=applications-internet
Terminal={terminal}
Categories=Education;Development;
''')
print('Installed app launchers: Packet Tracer with AI Agent / Packet Tracer AI — Set API Key')
