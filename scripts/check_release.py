# SPDX-License-Identifier: Apache-2.0
"""Check tracked/staged public bytes; print filenames, never secret values."""
import argparse
import json
import re
import subprocess
from pathlib import Path

parser = argparse.ArgumentParser()
parser.add_argument('--staged', action='store_true')
args = parser.parse_args()
root = Path(__file__).resolve().parents[1]
files = subprocess.check_output(['git', 'ls-files', '-z'], cwd=root).decode().split('\0')
allowed_vendor = {'vendor/pts-codec/' + name for name in
                  ['cast256.py', 'eax.py', 'pts_builder.py', 'pts_decrypt.py', 'pts_encrypt.py', 'LICENSE', 'SOURCE']}
pattern = re.compile(rb'(?:sk-(?:or-v1-)?[A-Za-z0-9_-]{24,}|gh[pousr]_[A-Za-z0-9]{30,})')
known = []
config = Path.home() / '.config' / 'packettracer-agent'
for name in ['settings.json', 'provider-keys.json']:
    path = config / name
    if path.exists():
        try:
            data = json.loads(path.read_text())
            values = [data.get('token')] if name == 'settings.json' else list(data.values())
            known.extend(value.encode() for value in values if isinstance(value, str) and len(value) >= 16)
        except (OSError, ValueError, AttributeError):
            raise SystemExit('Cannot read local secrets for comparison; resolve private configuration access.')
errors = []
for name in filter(None, files):
    path = Path(name)
    forbidden = (path.suffix.lower() in {'.pts', '.ptst', '.pkt', '.pka', '.pyc', '.log'}
                 or any(part in {'dist', 'validation', '__pycache__', '.venv', 'venv'} for part in path.parts)
                 or path.name in {'auth.json', 'provider-keys.json', 'providers.json', 'settings.json', 'openai-key'}
                 or path.name == '.env' or path.name.startswith('.env.')
                 or name.startswith('vendor/') and name not in allowed_vendor)
    if forbidden:
        errors.append(name + ': private/generated file class')
        continue
    data = subprocess.check_output(['git', 'show', ':' + name], cwd=root) if args.staged else (root / name).read_bytes()
    if pattern.search(data) or any(secret in data for secret in known):
        errors.append(name + ': possible credential detected')
if errors:
    raise SystemExit('\n'.join(errors))
print('Public file checks passed:', len(list(filter(None, files))), 'tracked files.')
