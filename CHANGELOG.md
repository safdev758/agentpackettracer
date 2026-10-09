# Changelog

## 0.2.6 — initial public experimental release

Backend 0.2.6, native module/UI 0.2.5. Linux native evidence uses Packet Tracer 9.0.0.0810. Generated modules must be built privately on each workstation.

- Multi-provider service: OpenAI Responses, Gemini and OpenRouter tool adapters; bounded transient-outage retries and actionable routing/quota errors.
- Validated simulator tools, enforced Ask/Plan/Inspect/Agent modes, router startup recovery and complete CLI/ping evidence.
- Leading `@codex` local headless worker with owned-process cleanup and cancellation, tested with experimental CLI 0.159.3.
- Bounded provider-neutral session memory; retain requirements and observations across provider/Codex changes, compact oversized history and avoid repeated automatic full-network scans on follow-ups.
- Paired/lazy tool activity, cursor polling, bounded closed rows and native Expand/Resize restoration.
- Persistent Linux user service and separate convenience launchers.
- Apache-2.0 original code, preserved MIT packer attribution and byte-verified upstream provenance.
- Public setup, architecture, failure/evidence, security, Codex, Windows and engineering guides; automated CI and [tracked roadmap](docs/ROADMAP.md).

Verification includes 38 offline Python regressions, native API doubles, mocked browser interaction/performance and the historical native checks described in [VALIDATION.md](VALIDATION.md). Windows, durable task memory and complete autonomous builds by every provider remain unverified/open work.
