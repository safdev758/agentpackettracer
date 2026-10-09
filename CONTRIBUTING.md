# Contributing

Read [architecture](docs/ARCHITECTURE.md), [known issues](docs/KNOWN_ISSUES.md) and [validation](VALIDATION.md) before changing the tool loop. Contributions to original project files are intended under Apache-2.0; preserve the separate vendored MIT notices. Submit only work you have rights to contribute.

Use Python 3.12+ and Node. The offline suite makes no real provider calls or Packet Tracer changes:

```bash
python3 -m unittest discover -s tests -v
node tests/test_extension.js
python3 -m py_compile agent.py context_memory.py providers.py codex_worker.py build_extension.py install.py install_service.py
node --check extension/main.js
node --check extension/ui.js
bash -n launch.sh
```

Optional browser checks use a separate environment:

```bash
python3 -m venv .venv
.venv/bin/pip install -r requirements-dev.txt
CHROME_EXECUTABLE=/usr/bin/google-chrome .venv/bin/python tests/ui_browser.py
CHROME_EXECUTABLE=/usr/bin/google-chrome .venv/bin/python tests/ui_performance.py
```

If no `CHROME_EXECUTABLE` is set, install Playwright's managed Chromium with `python -m playwright install chromium`. The workload tests use mocked services. Native tests need a licensed local Packet Tracer installation and a saved disposable lab; live inference consumes the tester's account quota.

Keep patches focused. Add regressions for meaningful failure modes: policy bypass, unknown execution, stale evidence, cancellation and protocol drift. Do not relax permissions just to make a demonstration succeed. Preserve provider reasoning/tool-call identifiers and read CLI output before dependent commands.

PR descriptions should explain the trigger, changed behavior, actual checks and remaining evidence gaps. Label tests as doubles, browser, native IPC or live inference. Windows support requires the acceptance evidence in [WINDOWS.md](docs/WINDOWS.md).

Before a commit/release run `python3 scripts/check_release.py` and `python3 scripts/check_docs.py` after staging the intended files. Generated artifacts, raw lab evidence, Cisco files and credentials are deliberately ignored. Never attach a personally generated `.pts` to a release.
