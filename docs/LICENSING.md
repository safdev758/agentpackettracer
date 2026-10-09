# Licensing and distribution

## Selected license

The project's original code and documentation use **Apache License 2.0**, as selected by the maintainer. It permits commercial and private reuse, modification and redistribution while requiring the applicable license/attribution notices and notices of changes. It includes a contributor patent grant and does not grant trademark rights. [Canonical Apache license](https://www.apache.org/licenses/LICENSE-2.0.txt).

Apache 2.0 was chosen because this project is intended to be reused and integrated, and an explicit patent grant is useful to downstream adopters. MIT is a shorter permissive alternative but does not contain Apache's explicit patent provisions. Neither license requires downstream users to publish every modification. If mandatory sharing of derivative improvements becomes a requirement, evaluate a copyleft license separately rather than assuming Apache does that. [MIT license](https://choosealicense.com/licenses/mit/).

Include [LICENSE](../LICENSE) and [NOTICE](../NOTICE) when redistributing the project, preserve relevant notices, and identify your changes. Contributions submitted for inclusion are intended to use the project's license; contributors must have rights to submit their work.

## Third-party code

The `.pts` packer in `vendor/pts-codec` comes from [A-Town-corp/MCP-Packet-Tracer](https://github.com/A-Town-corp/MCP-Packet-Tracer/tree/main/offline-tools). It retains its [MIT license](../vendor/pts-codec/LICENSE) and copyright notice. The root Apache license does not erase those terms. The [dependency notice](../THIRD_PARTY_NOTICES.md) identifies the included files and source.

Cisco's extracted help, SDK material, executable, bundled module samples, and a reference MCP checkout used during development are excluded from this distribution. Users obtain Packet Tracer independently. The repository is an independent integration and does not claim Cisco or OpenAI endorsement.

## What the code license does not provide

Apache 2.0 covers the rights granted by the project contributors. It does not license Cisco Packet Tracer, grant access to any model, waive provider quotas, make Codex inference free, or override provider authentication/service terms. Do not distribute personal provider credentials or Codex login files. Build a `.pts` separately on each user's computer because this release embeds that user's bridge credential.

The local Codex integration and a commercial/hosted Codex-backed product have different authentication requirements. Consult [the Codex integration guide](CODEX.md) and current official provider terms before changing the distribution model.
