# Third-party notices

| Component | Included? | License / source |
| --- | --- | --- |
| `.pts` codec and builder | Yes, source only | MIT; Copyright (c) 2026 Mateo - Packet Tracer MCP Server; [upstream offline-tools](https://github.com/A-Town-corp/MCP-Packet-Tracer/tree/main/offline-tools) |
| Cisco Packet Tracer and extracted bundled help | No | External Cisco product; users obtain their own installation |
| Jcorderop02/packet-tracer-mcp | No | Consulted for interoperability; reference checkout is excluded |
| Codex CLI / app-server | No | Installed separately; [official CLI](https://learn.chatgpt.com/docs/cli), account/service terms apply |
| Playwright / Chromium | No | Optional development dependencies installed separately; no browser binary bundled |

The included MIT source is `cast256.py`, `eax.py`, `pts_builder.py`, `pts_decrypt.py` and `pts_encrypt.py`. Preserve `vendor/pts-codec/LICENSE` when redistributing these files. Fixed format constants in the licensed packer are packaging parameters, not user credentials.

All five included Python files were compared byte-for-byte with upstream revision `4a501ef96187cc1dcf5a722e6c16765acba552aa` on 2026-10-09. [SOURCE](vendor/pts-codec/SOURCE) records the immutable upstream reference. No Cisco files or reference checkout are included.
