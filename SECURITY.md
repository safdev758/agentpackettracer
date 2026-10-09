# Security and data boundaries

This experimental local integration can modify the open lab in Agent mode. Save a copy first. Stop is cancellation of future work, not rollback of an already dispatched action. Inspect actual state after an unknown execution result.

The HTTP bridge binds only to loopback, validates Host and requires a random bearer token. Packet Tracer's custom origins receive compatible CORS responses; authentication still applies. Provider keys are stored in private local files and do not enter model prompts. The generated `.pts` contains a bridge credential and must be kept private. Source templates contain placeholders, not user credentials.

Prompts, selected topology facts and CLI output may be sent to the selected provider, including Codex's configured inference route. Provider policies and account limits apply. Conversation history and run events live in service memory. Private development evidence and labs are excluded from the repository.

The module requests native network read/write, GUI and application-workspace privileges. It exposes named handlers rather than arbitrary model JavaScript. Mode restrictions and schema checks are enforced server-side. Its IOS CLI denylist is not a complete semantic security policy. Do not use this project as a boundary against malicious same-user software or treat it as a real-network administration security product.

Supported evidence currently covers Linux/Packet Tracer 9 and the versions in [VALIDATION.md](VALIDATION.md). Windows protection/cleanup are roadmap requirements, not promised behavior.

Report vulnerabilities privately through GitHub's **Report a vulnerability** feature if enabled for the repository, or contact the maintainer through their GitHub profile to arrange a private channel. Do not publish credentials, generated modules, private topology dumps or exploit details in a public issue. No response-time SLA is currently promised.

If a local credential leaks, stop the backend, rotate the affected provider credential, or regenerate the bridge credential and rebuild/re-import the module as applicable. Git history rewriting alone does not revoke a credential.
