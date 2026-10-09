# Packet Tracer Agent

An AI assistant inside Cisco Packet Tracer, backed by a local Python service. Inspect a lab, plan changes, configure devices and verify actual CLI results without modifying Cisco's executable.

**Status:** experimental Linux release, tested with Packet Tracer 9.0.0.0810. Windows is planned. Backend version 0.2.6; native module/UI version 0.2.5. This is an independent project, not an official Cisco or OpenAI product.

## Start here

Install your own Packet Tracer and Python 3.12+, then:

```bash
git clone https://github.com/safdev758/agentpackettracer.git
cd agentpackettracer
python3 build_extension.py --install
python3 agent.py
```

Open Packet Tracer separately. Add `dist/PacketTracerAgent.pts` through **Extensions → Scripting → Configure PT Script Modules**, review its privileges, start it and open **Extensions → Packet Tracer Agent**. Leave that panel and the backend open. Use Network → Refresh to check the connection without making a model request.

Follow [Linux setup](docs/SETUP.md) for persistent startup, the optional launchers, upgrades and removal. The supplied launcher currently assumes `/opt/pt/packettracer.AppImage`; manual startup works with your existing installation.

**Generate the module locally.** Its `.pts` contains your private local bridge token. Generated modules, provider keys, Cisco binaries and personal labs are excluded from this repository and releases.

## What it does

- **Ask:** explanations; no simulator tools.
- **Plan:** inspect the network and propose changes.
- **Inspect:** read device state, recover harmless CLI prompts and run diagnostics.
- **Agent:** create devices, connect cables, configure hosts and CLI, then verify results.

Choose OpenAI, Google Gemini or OpenRouter in Settings and use your own API key. Model discovery does not prove endpoint access or inference quota. OpenRouter's `openrouter/free` was tested successfully with tools after removing an incompatible optional request parameter; future availability and quotas remain provider-dependent.

Optional local Codex requests begin with `@codex`, for example:

```text
@codex inspect R2 and explain its routes
```

Others can set this up using their own installed Codex CLI and login. The backend launches a separate worker; the Codex desktop window can be closed. Packet Tracer, its Agent panel and the computer must remain running. See [Codex integration and account boundaries](docs/CODEX.md). It uses the user's account allowance, not an unlimited free model.

Bounded session memory retains requirements and actual tool observations across follow-ups and provider/Codex changes. Oversized conversations compact into factual context instead of disappearing. Follow-ups avoid an automatic whole-network rescan; affected state still needs fresh verification before changes. New chat and backend restart clear this memory.

Shared instructions cover router boot/setup recovery, interface activation, VLAN/trunk/subinterface configuration, gateways, forward/return routes and complete ping evidence. Tool validation also enforces execution modes. CLI errors, incomplete pings and interrupted work must not be reported as success.

The activity panel pairs tool starts/results, loads details lazily, bounds closed rows and retains reading position. **Expand** changes to **Resize**, restoring the native panel. Stop cancels subsequent work and the owned Codex worker; a simulator action already dispatched may still complete. Save a lab copy before substantial edits.

## Documentation

| Topic | Guide |
| --- | --- |
| Installation, configuration, autostart and removal | [Setup](docs/SETUP.md) |
| Components, lifecycle and trust boundaries | [Architecture](docs/ARCHITECTURE.md) |
| Local headless Codex and onboarding | [Codex](docs/CODEX.md) |
| Observed failures, fixes and remaining limitations | [Known issues](docs/KNOWN_ISSUES.md) |
| Actual checks and their limits | [Validation](VALIDATION.md) |
| Platform blockers and acceptance criteria | [Windows roadmap](docs/WINDOWS.md) |
| What to learn, engineering priorities and CV wording | [Engineering guide](docs/ENGINEERING_GUIDE.md) |
| License choice and dependency boundaries | [Licensing](docs/LICENSING.md), [third-party notices](THIRD_PARTY_NOTICES.md) |
| Development and reporting | [Contributing](CONTRIBUTING.md), [security](SECURITY.md) |

## Development

Runtime and packaging use Python's standard library. Node is needed for the native API-double tests; Playwright is optional for browser QA.

```bash
python3 -m unittest discover -s tests -v
node tests/test_extension.js
python3 scripts/check_docs.py
python3 scripts/check_release.py
```

See [Contributing](CONTRIBUTING.md) for syntax checks, browser tests and the separate native acceptance process. Automated doubles do not prove native simulator compatibility or autonomous completion by every model.

## License and distribution

Original project code is [Apache 2.0](LICENSE), with [NOTICE](NOTICE). The five vendored `.pts` packaging files retain their separate [MIT license](vendor/pts-codec/LICENSE) and verified [provenance](vendor/pts-codec/SOURCE). Cisco Packet Tracer, Codex, browsers, credentials and account entitlements are not redistributed.

Network context and CLI output are sent to the selected model provider. The authenticated bridge listens on loopback; local files and the generated module must remain private. Read [security and data boundaries](SECURITY.md) before sharing a demo or deploying outside a personal workstation.
