# Linux setup and operation

## Requirements

- A separately obtained Cisco Packet Tracer installation. Native integration was tested with Packet Tracer 9.0.0.0810 on Linux.
- Python 3.12 or newer. Backend and packaging use the standard library.
- A Linux desktop session with user systemd for the supplied launch/autostart scripts.
- Optional provider API key for ordinary model requests, or a locally installed/logged-in Codex CLI for `@codex` requests. Network Refresh needs neither.
- Node for API-double tests; Playwright and Chromium only for development browser tests.

This release's launcher expects Packet Tracer at `/opt/pt/packettracer.AppImage`. If your installation differs, start the backend directly and open your existing Packet Tracer launcher, or adapt the final executable path in `launch.sh`. Automatic installation/path discovery is a roadmap item.

## Clean checkout

```bash
git clone https://github.com/safdev758/agentpackettracer.git
cd agentpackettracer
python3 --version
python3 build_extension.py --install
python3 agent.py
```

Leave the backend terminal running for the first connection. It binds to `127.0.0.1:54123`. Open Packet Tracer separately, then import the module from this checkout's `dist/PacketTracerAgent.pts` through **Extensions → Scripting → Configure PT Script Modules → Add**. Review the named module's privileges, enable/start it, and open **Extensions → Packet Tracer Agent**.

The `--install` copy is a Linux convenience location under `~/pt/extensions/PacketTracerAgent`; manually importing the generated `dist` file works independently of auto-detection. Always generate it locally. It contains a private bridge token and is not a universal downloadable release artifact.

## Persistent backend and convenience launchers

Stop a foreground backend with Ctrl+C before installing the user service; do not interrupt an active task. Then:

```bash
./launch.sh --install-service
systemctl --user status packettracer-agent.service
./launch.sh
```

The service starts at desktop login, survives closing the launching terminal, and restarts after failure. It does not require the Codex desktop window. `launch.sh` builds the extension and reuses an authenticated service before opening Packet Tracer. `launch.sh --service-only` starts/reuses only the backend.

Optional Linux desktop launchers:

```bash
python3 install.py
```

These are separate launchers and do not replace Cisco's existing launcher. The legacy terminal `./launch.sh --setup` prompt configures OpenAI; the panel's Settings support all ordinary providers.

## Model setup

In Settings choose OpenAI, Google Gemini or OpenRouter, enter your own provider key, fetch models, select one with tool support, and save. A blank key field preserves the saved key. A discovered model can still fail because of account access, endpoint capabilities, privacy settings or quota.

`openrouter/free` routes through eligible free endpoints; quota and availability still apply. Requests omit optional `parallel_tool_calls` because requiring that feature caused free-endpoint routing failures. For the optional local Codex path, follow [CODEX.md](CODEX.md); its account usage is separate from OpenRouter.

## First checks

1. Confirm the panel says Connected to Packet Tracer.
2. Use Network → Refresh. This checks the native bridge without inference.
3. Try Inspect on an existing device and read its actual results.
4. In a saved throwaway lab, use Agent mode for a small authorized change and inspect interfaces, VLAN membership and full ping summaries.

Use Ask for explanations, Plan for a proposal, Inspect for diagnostics and Agent for configuration/build work. Save a copy before expanding a lab. Stop prevents subsequent work but does not roll back an already dispatched action.

## Upgrades, diagnostics and removal

Backend changes need an idle service restart. Native JavaScript/UI changes need a local rebuild and re-import/restart of the module. Remove an old module entry before importing the new artifact if Packet Tracer keeps its previously loaded copy. A new native build can request additional privileges; instructions cannot grant those privileges.

```bash
systemctl --user restart packettracer-agent.service
journalctl --user -u packettracer-agent.service --no-pager
```

To uninstall, disable and stop the user service, remove its unit and reload systemd, remove the module in Packet Tracer, and remove the convenience extension/desktop files. Delete credentials only if you intend to disconnect this installation:

```bash
systemctl --user disable --now packettracer-agent.service
rm ~/.config/systemd/user/packettracer-agent.service
systemctl --user daemon-reload
```

The remaining convenience files are `~/pt/extensions/PacketTracerAgent` and the two `packettracer-agent*.desktop` files under `~/.local/share/applications`. Credentials/settings live in `~/.config/packettracer-agent`. Your Codex login belongs to Codex and is not removed by this project's uninstall.
