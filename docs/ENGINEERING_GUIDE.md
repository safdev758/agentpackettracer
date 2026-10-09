# What to understand as the software engineer

You are maintaining an agent execution system, a native-app integration and an open-source product. The model is one component. Reliability comes from state handling, bounded execution, independently checked evidence and clear distribution boundaries.

## Know the system before changing it

Trace one request through the panel, authenticated HTTP, mode filtering, provider message adapter, tool validation, bridge queue, Packet Tracer IPC, result events and final model answer. Read [architecture](ARCHITECTURE.md), then `Agent.work`, `validate_tool`, `Bridge.execute`, `startCli` and `CodexClient.create`.

Be able to answer: where can a mutation happen; who owns a queued job; what changes after Stop; which state disappears on restart; which result proves success; which bytes are private; and which failure is safe to retry?

## Skills this project exercises

| Skill | Concrete responsibility |
| --- | --- |
| Networking | Access vs trunk ports, dot1Q subinterfaces, unique gateways/subnets, transit links, forward and return routes, ARP/STP convergence, bidirectional checks |
| State machines | Router boot/setup/user/enable/config/pager states; CLI recovery based on actual prompts |
| Distributed systems | Jobs can execute while a response is lost; cancellation is not rollback; retries need idempotency or live reconciliation |
| API integration | Catalog discovery vs real endpoint capability, native tool/reasoning formats, temporary outage vs quota/auth failure |
| Process management | Stdio RPC, wrappers and children, bounded shutdown, avoiding orphan workers and unrelated-process termination |
| Frontend performance | Cursor polling, lazy JSON rendering, DOM retention, read/scroll preservation, native vs browser latency measurement |
| Security | Authenticated loopback, local-user threat boundary, private artifacts, untrusted CLI/model output, least privilege and credential lifecycle |
| Testing | Protocol doubles, negative permission tests, meaningful browser workloads, native acceptance and reproducible evidence |
| Open-source maintenance | Dependency provenance, license notices, clean releases, issue triage, version compatibility and honest support matrices |

## Rules to use in reviews

1. A router icon or a cable is not proof of a working route. Verify the correct interfaces, switch membership, gateway and return path.
2. A model answer, native status `0` or a completed task is not enough. Check the actual configuration and a complete connectivity summary.
3. After a dispatched mutation times out, reconcile current state before retrying. Duplicate router creation or duplicate links are avoidable data-integrity bugs.
4. Put required behavior in code where possible. A prompt can tell a model to obey Inspect mode; the host must still reject configuration tools.
5. Treat provider failure as a lifecycle event. Preserve factual partial work, stop honestly, and continue from a fresh snapshot.
6. Keep source releases and local artifacts distinct. A generated module can contain a secret even when the source templates are clean.
7. Label the evidence level. A passing fake-IPC test does not prove native Packet Tracer behavior; a passing Linux run does not prove Windows support.

## Next work in priority order

**First: finish product installation and release hygiene.** Make Packet Tracer paths configurable, add an installation preflight, simplify the first-run experience, provide a supported CLI version range, and reproduce installation from a clean checkout. Explain Codex login before the user sends a request. Keep generated credentials/artifacts out of releases.

**Second: strengthen task correctness.** Add machine-checked topology requirements: exact device counts, named PC-to-router/VLAN assignments, unique addressing, required interface states and expected ping pairs. Track tool intent, dispatch, acknowledged result and unknown execution separately. A durable journal and resumable plans need careful design because recorded configuration can be sensitive.

**Third: improve policy and observability.** Consider an IOS-aware configuration policy rather than extending a string denylist indefinitely. Bound backend event/history bytes as well as UI rows. Add redacted timings for inference, bridge wait, CLI execution and rendering so slow models and slow simulator/UI work are distinguishable.

**Fourth: automate compatibility.** Capture protocol contracts for each provider, Codex dynamic-tool versions and Packet Tracer versions. Run CI without live keys; keep opt-in native acceptance separate. Verify process cleanup and credentials under the actual target OS.

**Fifth: deliver Windows and broader onboarding.** Implement the platform adapter and native checks in [the Windows roadmap](WINDOWS.md). Evaluate explicit Sign in with ChatGPT if turning the current personal Codex trigger into a broadly distributed product. Do not assume local CLI login can be repackaged as hosted SaaS authentication.

## A practical learning sequence

Spend the first session drawing the request and failure states and running the offline tests. Next, reproduce a router startup/pager/ping failure in a throwaway lab and explain why the original false-success condition occurred. Then implement one observable improvement, such as per-stage timings or exact VLAN membership assertions, with a regression that would fail before the change. Finally, perform a clean installation and write down every undocumented assumption you encounter.

## Portfolio / CV wording

> Built a local AI assistant embedded in Cisco Packet Tracer using JavaScript IPC and an authenticated Python service. Integrated multiple model providers and an optional headless Codex worker, enforced execution modes and cancellation, and added evidence-based network verification, failure recovery and UI performance controls.

Back that statement with the repository, the automated tests and a native demo. State that the multi-router lab was completed through the real structured tools; do not claim that every supported model autonomously completes arbitrary labs. List Windows as planned until its native acceptance checks pass.
