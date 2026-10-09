# Validation and evidence boundaries

Evidence collected on Linux through 2026-10-09. Backend 0.2.6, native module/UI 0.2.5, Packet Tracer 9.0.0.0810 and experimental Codex CLI integration tested with 0.159.3. The automated checks below can be repeated from this checkout; historical native results need a separately installed simulator and disposable lab.

| Layer | Evidence | Limit |
| --- | --- | --- |
| Python | 38 offline tests: authentication, mode/argument validation, provider payloads, partial context, Codex process/protocol and cancellation | Uses doubles; no real provider quota consumed |
| Native controller | Node API-double tests for device/cable calls, CLI output/errors, pagers and ping summaries | Does not replace the native simulator |
| Browser UI | Headless Chrome mocked-service interaction and performance workloads, 4× CPU throttle, lazy details/cards, row bounds, scroll preservation and responsive composer | Synthetic workload; timing depends on runner |
| Real Packet Tracer | Creation/cabling, router CLI recovery, VLANs, trunks, subinterfaces, interface states, routes and full ping results | Version/platform specific |
| Real providers | Gemini discovery/chat/tool inspection; OpenRouter free tool round trip and native inspection | Access and quotas can change; ordinary OpenAI API inference unverified |
| Local Codex | Leading-prefix trigger; native R2 inspection and CLI commands; Stop interrupted a 15-second wait in approximately 0.25 seconds and cleaned owned workers | Experimental protocol; not the existing interactive Codex chat |
| Native window | Expand undocked/maximized, Resize redocked; input and tab switching remained usable | Native Linux check; no Windows evidence |
| User service | Persistent login startup, restart-on-failure, unit validation and active state | Requires desktop user systemd |

## Completed multi-router lab

The existing R1/S1/PC0/PC1 lab was preserved and expanded with R2 and R3, each connected to four additional PCs. PC2–PC5 belong to VLAN 10. PC6–PC7 belong to VLAN 20. **Only PC8 and PC9 belong to VLAN 30**. PC0/PC1 remain in VLANs 10/20.

R2 and R3 use separate /30 transit links through R1. Gateways, VLAN 30's forward route and the required return/default routes were configured. Router interfaces were checked up/up, and switch trunks were checked forwarding. Eighteen directed gateway/cross-VLAN checks ended with four replies out of four each. Initial ARP-related packet loss was retained as a failed initial attempt and retried; it was not counted as a passing result.

The saved lab was reopened and inspected: 15 native devices (14 logical devices plus the simulator's automatic power device) and 15 links. Raw labs, local paths, bridge tokens and full execution traces remain private. This document publishes a factual summary, not a downloadable lab or independent reproduction of those historical runs.

This lab was completed with the real structured tools through a direct harness. An earlier model-created lab stopped at provider quota. A complete autonomous multi-router build by every supported model has **not** been established.

## Release verification

GitHub Actions runs the offline Python suite on Python 3.12/3.13, native API doubles, syntax checks, local packaging, documentation/link checks, tracked-file release checks and a separate browser job. Consult the repository's actual Actions result for the current commit; a workflow definition is not evidence of a passing run.

The release checker excludes known private/generated file classes and checks common token signatures plus locally known bridge/provider secrets when present. It is a useful guard, not a complete secret-detection or security audit.

Windows installation, native Windows IPC/resize/process cleanup, cold clean-desktop onboarding and broader Packet Tracer/Codex version compatibility remain open acceptance work. See [known issues](docs/KNOWN_ISSUES.md), [Windows](docs/WINDOWS.md) and [contribution checks](CONTRIBUTING.md).
