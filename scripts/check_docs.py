# SPDX-License-Identifier: Apache-2.0
"""Validate repository-relative Markdown links against public tracked files."""
import re
import subprocess
from pathlib import Path
from urllib.parse import unquote

root = Path(__file__).resolve().parents[1]
tracked = set(filter(None, subprocess.check_output(['git', 'ls-files', '-z'], cwd=root).decode().split('\0')))
errors = []
for name in sorted(tracked):
    if not name.endswith('.md'):
        continue
    for raw in re.findall(r'\]\(([^)]+)\)', (root / name).read_text()):
        target = raw.split(' "', 1)[0].strip('<>')
        if re.match(r'^[a-zA-Z]+:', target) or target.startswith('#'):
            continue
        target = unquote(target.split('#', 1)[0])
        resolved = (root / name).parent.joinpath(target).resolve()
        try:
            relative = resolved.relative_to(root).as_posix()
        except ValueError:
            errors.append(name + ': link leaves repository')
            continue
        if relative not in tracked and not any(path.startswith(relative + '/') for path in tracked):
            errors.append(name + ': missing public link ' + target)
if errors:
    raise SystemExit('\n'.join(errors))
print('Public Markdown links passed.')
