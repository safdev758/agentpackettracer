# Windows feasibility and porting plan

Windows support is feasible, but this repository is currently tested on Linux only. Python HTTP/JSON logic and Packet Tracer's HTML/JavaScript panel are reusable. OS lifecycle, credential protection and process cleanup need deliberate adapters and native validation.

Codex itself supports native Windows workflows. That does not make this extension's Linux launcher and `os.killpg` cleanup Windows-compatible. [Official Windows sandbox documentation](https://learn.chatgpt.com/docs/windows/windows-sandbox).

## Concrete blockers

| Area | Current implementation | Windows work |
| --- | --- | --- |
| Packet Tracer launch | `/opt/pt/packettracer.AppImage` in Bash | Discover/configure `PacketTracer.exe`; PowerShell launcher; handle spaces and non-ASCII paths |
| Python | `/usr/bin/python3` and Linux launchers | Use a supported Python installation, typically `py -3`; verify interpreter version and environment |
| Startup | User systemd service; `.desktop` entries | Foreground launcher first, then a user-scoped scheduled task at sign-in with explicit restart/uninstall behavior |
| Config/credentials | `~/.config/packettracer-agent`, POSIX modes | App-specific directory under `%LOCALAPPDATA%`; verify NTFS ACLs or OS credential storage; `chmod(0600)` is not equivalent protection |
| Codex start | Executable on PATH, POSIX session | Resolve the native executable or vetted npm launcher; test `.cmd` argument forwarding without enabling arbitrary shell command execution |
| Codex Stop | `start_new_session` and `os.killpg` | Own the entire worker tree, preferably a Windows Job Object; verify graceful termination and bounded fallback |
| Extension install | `~/pt/extensions/...` convenience copy | Discover actual installation/user directories; allow a destination option; retain manual module import |
| Browser QA | `/usr/bin/google-chrome` | Configurable browser path or Playwright-managed Chromium |
| Native QA helper | Local X11 screenshot/input utility, excluded from distribution | Windows-specific manual/native UI verification; do not ship the Linux repair helper as a supported product API |

Microsoft documents `taskkill /T` for terminating a process and its children. It is one possible bounded fallback after owning a specific worker PID; never kill every process named Codex or Packet Tracer. [Microsoft taskkill documentation](https://learn.microsoft.com/en-us/windows-server/administration/windows-commands/taskkill).

## Recommended delivery stages

1. Extract paths, process launch/stop, service installation and private-file handling behind a small platform adapter. Preserve the tested Linux behavior.
2. Make a Windows foreground backend and local artifact build work before implementing autostart. Generate every user's `.pts` locally with their own bridge token.
3. Add Python/Node CI on Windows for the portable core. Introduce explicit platform assertions for credential ACLs and process cleanup; do not simply skip those requirements until the suite is green.
4. On an actual Windows 11 host, install licensed Packet Tracer, import the module, approve its named privileges, and verify custom-origin HTTP, polling, device inspection, configuration, long CLI pagination and native Expand/Resize.
5. Test API-provider and `@codex` runs, model failure, Stop while a worker waits, process-tree cleanup, service restart, save/reopen, token rotation and uninstall.
6. Publish Windows support only after the native evidence and installation steps are reproducible. Optional signed packaging comes later.

## Release acceptance

Test a non-admin user, a path containing spaces, a non-ASCII username, missing Python/Codex/Packet Tracer, occupied port, missing/expired login, sleeping/waking computer, a closed panel and a restarted service. Save a lab, reopen it, and re-check interface/VLAN/routes and bidirectional pings. Verify another user's credentials cannot be read and unrelated Codex processes survive Stop.

A WSL backend talking to Windows Packet Tracer is an experiment, not the first support target: loopback forwarding, filesystem boundaries and Linux/Windows process ownership add complexity. Start with a native Windows backend and record exact supported versions.
