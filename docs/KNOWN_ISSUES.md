# Problems encountered, fixes and remaining limits

These are observed failures from development, not hypothetical claims that prompts alone prevent every recurrence. Every fix has an evidence level. See [validation](../VALIDATION.md) for the distinction between test doubles, browser workloads and native runs.

| Observed problem | Cause / implemented response | Evidence and remaining limit |
| --- | --- | --- |
| OpenRouter 404 despite a discovered free model | Catalog availability was confused with routing capability. Requiring optional `parallel_tool_calls` excluded free endpoints; omit it for OpenRouter and classify routing/privacy errors | Reproduced failure and successful zero-cost tool round trip; endpoint availability still varies |
| Provider 503 / 429 halted work | Temporary server failures and quota are different. At most two short bounded retries for selected 5xx errors; do not automatically retry quota/auth failures | Provider regressions and live recovery; no quota bypass |
| Model described an empty network instead of building | Context followed and overshadowed the user's request. Put mode/fresh context before the actual request and require build actions in Agent mode | Regression and native creation attempt; a later quota failure still stopped the model |
| Device creation denied by native IPC privileges | Workspace access required `APPLICATION` in addition to network-write privileges | Native denial reproduced; updated module created real devices after re-import |
| Router accepted text as startup wizard answers | Router CLI not ready; a native status of zero did not imply configuration succeeded | Prompt/mode guard and error detection; startup recovery instructions; API-double coverage |
| Routers existed but interfaces were down | Boot, parent `no shutdown`, dot1Q/trunks, gateways and routing were unfinished | Multi-router recipe and real configuration/verification; instructions are not an independent verifier |
| Shared-switch PC groups left added routers unused | A PC must use the intended router's actual gateway and VLAN path, not merely sit near its icon | Finished lab groups use R2/R3 gateways; exact membership checks preserved original hosts |
| Link/gateway getters returned unsupported IPC errors | PT 9 does not expose the assumed remote-link or host gateway getters | Use cable presence separately from interface state; read PC gateways through CLI; remote endpoints remain unavailable for some loaded labs |
| Long `show` command timed out at `--More--` | Pager needed input; `terminal length 0` was not a reliable assumed feature | Bounded automatic pager advancement; full native router/switch configurations completed |
| Stale CLI history included older results/errors | Terminal buffers rotate/redraw instead of always appending | Prefer fresh output/delta evidence; API-double regression prevents old summaries being reused |
| PC ping stalled, then a following command had no output | Timed-out ping was still running in the terminal | Inspect/cancel unfinished ping; native recovery; partial summary was never counted as passed |
| Inspect could not wake a saved router CLI | Policy blocked an empty Return command | Permit empty input and Ctrl+C in Inspect/Plan while still rejecting configuration; native Codex read verified recovery |
| Bridge intermittently said disconnected | Four-second staleness window was too short for temporary UI delay | Fifteen-second tolerance and regression; closed panel or longer stalls still disconnect |
| Expanded panel stayed labeled Expand | Native window state was not mirrored in the UI; no restore action | Expand/Resize toggle with native undock/redock and browser callback checks |
| Long activity history made the panel heavy | Repeated JSON formatting, duplicate rows, full re-renders and hidden device cards | Cursor reads, lazy details, paired rows, bounded closed-row retention, deferred cards and limited CLI-history reads; native speed is not guaranteed |
| Restart left a stale active task in the panel | In-memory task ID no longer existed | Missing run returns 404 and UI clears the stale task without declaring the bridge broken |
| Provider/tool interruption lost continuation context | Partial provider messages could include unanswered calls | Retain bounded request/result facts; fresh live inspection before continuation; restart still clears in-memory history |
| Packet Tracer closed before additions were saved | Simulator lab persistence is independent of model/task state | Restored missing additions from actual evidence, saved checkpoints and reopened final lab; saving remains a user workflow |
| Codex worker could leave its native child running | npm CLI can wrap a child; stopping only a parent is insufficient | Terminate isolated process group; live Stop test completed within 0.25 seconds on Linux |
| Disabling Codex connectors with an empty map failed | Config maps merge; quoted dotted keys could create a new invalid transport entry | Explicit TOML inline-map per-entry overrides; actual initialization and live cancellation verified |
| Persistent service initially failed to start | Quoted `WorkingDirectory` was parsed as a non-absolute path | Corrected unit value and added active-state check; unit verification and enabled/running state checked |

## Still open

- Native Windows installation, ACL protection, Codex process-tree cleanup and UI acceptance are not implemented/tested.
- A complete autonomous multi-router build by each provider is not established. The verified final lab was completed through the real structured tools using a direct local harness.
- Raw OpenAI API inference has not been tested with a live API account. Local Codex inference is a separate verified path.
- The selected device/model/cable combinations and Packet Tracer version have limited coverage. An API-double test is not an IPC compatibility guarantee.
- One active task/panel is supported. Conversation state is in memory; no durable task journal or automatic rollback exists.
- Backend event/result bytes are not globally capped; opened UI details and conversation bubbles are retained. Long-term resource bounds need further work.
- Agent CLI policy is broad configuration permission plus a denylist, not an exhaustive IOS policy parser.
- Generated `.pts` files contain local credentials. Public release artifacts must remain source-only until packaging separates provisioning from reusable assets.
- Current Linux launch paths and optional Chrome test paths are fixed. Clean setup and cross-platform path discovery need improvement.
- Provider calls can send selected topology/CLI data off the computer. Keep sensitive labs out of public issue reports.

## Reporting a failure

Include OS, Packet Tracer/Python/Codex versions, selected provider/model and mode, the exact prompt, expected vs observed behavior, and a redacted minimal tool result. Say whether the panel was open, whether the task had already dispatched an action and whether the lab was saved. Avoid API keys, auth files, generated `.pts`, or full private lab captures. Use the repository's bug template.

## Repeated inspection and lost context

The backend previously scanned the entire topology at the start of each non-Ask request, discarded all native conversation history beyond 100 KB, and cleared it on provider/model changes. The fix replaces oversized/reset history with bounded provider-neutral session memory, keeps original requirements and actual observations, and acquires the full baseline once per session/panel instance. Five regressions cover follow-ups, oversized context, provider transfer, panel/New chat invalidation and bounded retention. Models can still request unnecessary reads; instructions now direct them to affected state rather than repeated full inventories. Historical context cannot establish current simulator state after manual changes.
