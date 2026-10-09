# Codex integration for other users

Other users can run the same local integration using their own Codex installation and login. Your account, credentials and existing Codex chat are not distributed with the project.

## Setup on the currently tested Linux platform

1. Install this project and import the locally generated extension using the [setup guide](SETUP.md).
2. Install Codex CLI using the [official CLI instructions](https://learn.chatgpt.com/docs/cli).
3. Run `codex login`, then `codex login status` in your own terminal. Do not paste the Codex credential file into Packet Tracer.
4. Keep Packet Tracer and its Agent panel open.
5. In Inspect mode, send `@codex inspect R2 and show its interface status`. In Agent mode, a creation/configuration request can change the lab.

Only a leading, case-insensitive `@codex` followed by whitespace or the end of the message triggers the worker. `@codex` alone requires an actual request. Other messages continue using the saved API provider. The status chip displays the active Codex model while that task runs.

## What happens

Provider changes and subsequent `@codex` turns retain bounded, provider-neutral session memory. Native provider tool messages are not reused across incompatible protocols. Memory is historical context, not proof of current device state. New chat clears it; service restart clears it.

The backend launches a separate `codex app-server` process over stdio and initializes its JSON-RPC protocol. It checks account state, creates a temporary read-only ephemeral thread using the configured Codex model, supplies the shared Packet Tracer instructions and the tools permitted in the selected mode, and starts a turn.

Experimental dynamic tool requests are translated into the existing host validation/execution loop. Actual results return to Codex; completed assistant messages appear in the Packet Tracer activity log. Failed/interrupted turns are not reported as successful worker completion. Stop cancels host work and terminates the isolated CLI process group, including an npm wrapper's native child.

Shell, multi-agent, apps, web search, and configured plugin/MCP entries are disabled for the worker without editing the user's Codex configuration. The integration does not automatically approve unrelated interactions. Local managed requirements or future Codex versions can impose additional constraints; unsupported interactions fail visibly.

The local login is owned by Codex. Each user's account must have access to the selected model, and usage limits still apply. A model catalog or successful login is not proof that a later inference request will succeed. Codex desktop can be closed; the computer, local service and Packet Tracer panel must still be available.

## Distribution and hosted products

This release documents a personal/local integration tested with Codex CLI 0.159.3. The dynamic-tool API is experimental, so protocol changes need compatibility tests before updating a supported version. A raw stdio thread is not an integration with this project's existing interactive Codex conversation.

OpenAI currently documents app-server authentication for existing local/open-source integrations and recommends migrating to Sign in with ChatGPT; it states that app-server authentication is not permitted for commercial or hosted services. A source-code license does not grant model-service entitlement. Review that guidance before selling or hosting this authentication flow. [Official app-server authentication guidance](https://learn.chatgpt.com/docs/app-server#auth-endpoints).

For a polished public onboarding flow, evaluate explicit Sign in with ChatGPT, per-installation host IDs, consent for plan usage, profile selection, refresh handling, disconnect and usage controls. The official cookbook describes eligible open-source/local applications and account-dependent availability. This flow is a roadmap item, not implemented in this release. [Official Sign in with ChatGPT cookbook](https://developers.openai.com/cookbook/articles/sign-in-with-chatgpt).

## Verification

A live worker used `inspect_device`, Return, `enable` and `show ip interface brief` to read an existing router through Packet Tracer. A separate live cancellation check stopped a 15-second network wait within 0.25 seconds and returned the service to its saved provider, with no active worker. These checks establish the local trigger and tool flow, not a complete Codex-driven network build. See [validation](../VALIDATION.md).
