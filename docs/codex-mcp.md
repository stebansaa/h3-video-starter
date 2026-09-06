# Optional RunPod MCP and the repository skill

The default route is Codex running the shipped Python commands through its
terminal. These commands call RunPod REST v2 and ComfyUI directly. MCP is an
optional additional way for the agent to inspect/manage infrastructure; it
does not run the episode renderer in place of these scripts.

| Component | How it is provided |
| --- | --- |
| Project rules and lessons | Root `AGENTS.md` and `docs/`, included in the clone |
| H3 production skill | `.agents/skills/h3-video/SKILL.md`, included and usable inside the clone |
| RunPod MCP | Optional connection configured/authenticated in that user's Codex host |
| RunPod's general skills/plugin | Optional external installation; our direct workflow does not require it |
| API credentials | Supplied privately by the new user; never shipped |

Do not automatically install a plugin just because the original production used
it. When one is already connected, use its actual current tool descriptions.
Keep the repository's pinned graph, hardware requirements and budget boundaries
when operating infrastructure through another tool.

## Connect MCP when the user wants it

For Codex with CLI access, inspect `codex mcp add --help` first and existing
connections before adding a duplicate. The CLI syntax below was checked against
the installed CLI on 2026-09-06; confirm it on the new host.
Some provider setup examples use `--transport http`; the checked Codex CLI
uses `--url` instead. Follow the actual client's help when those examples differ.

If `RUNPOD_API_KEY` is already securely available in the **Codex host process
environment**, the hosted MCP can reference the environment variable by name:

```sh
codex mcp add runpod --url https://mcp.getrunpod.io/ \
  --bearer-token-env-var RUNPOD_API_KEY
```

This registers a connection; it changes Codex configuration. Run it when the
user has chosen this setup, then reconnect/restart the client as needed. Do not
put the key itself in this command. Our `.env` loader only serves our Python
commands: a key in the repository's `.env` is **not automatically an environment
variable in a running Codex app**. If the host environment cannot be arranged
conveniently, keep the direct API route or use the separate OAuth route below.

For a user who wants browser-based MCP login, a separate option is:

```sh
codex mcp add runpod --url https://mcp.getrunpod.io/
codex mcp login runpod
```

Choose one setup route for the connection. Do not overwrite an existing server
configuration or copy someone else's tokens. In a desktop/IDE client without
CLI access, use its MCP server settings to add the HTTP URL and authenticate.
See [official Codex MCP setup](https://learn.chatgpt.com/docs/extend/mcp?surface=cli)
for current UI/CLI instructions and
[RunPod's MCP repository](https://github.com/runpod/runpod-mcp) for the provider.

After configuring, inspect the active session's tool list and make a read-only
RunPod call such as listing pods. A configured entry is not proof of a working
connection. Avoid posting raw connection/configuration dumps: they can contain
headers or credentials. A redacted “connected, read-only call passed” result
is enough for the project progress file.

## Separate credential paths

**MCP OAuth authenticates that MCP connection.** It does not populate
`RUNPOD_API_KEY` for our Python CLI or local stop watchdog. Continue to use the
user's API key in `.env` for this repository's direct infrastructure commands.
Verify those commands separately with:

```sh
python3 scripts/first_session.py --check-auth
```

An existing key can be used for both paths, but each tool must actually be able
to read it. Do not extract an OAuth access token and repurpose it as a RunPod
API key. RunPod documents the connection options in its
[agent setup guide](https://docs.runpod.io/agent-setup.md).

If MCP creation cannot express the GPU/RAM/CPU/CUDA/storage requirements in the
prepared request, use the repository's `pod-config` / `pod-create` path. Do not
silently omit filters. Preserve the resource ID, ownership, allocation start,
rate and deadline in the session regardless of which interface created it.
Never create a second pod because an MCP/API response was uncertain; reconcile
the first request against actual account resources.

## Skill discovery

The local H3 skill is ordinary repository content. Codex can discover it under
`.agents/skills`, and it can be explicitly invoked as `$h3-video`. If unavailable,
read its `SKILL.md` directly from the checkout. It links to the same maintained
runbooks as `AGENTS.md`; it does not duplicate RunPod's global skill collection
or declare MCP as a mandatory dependency.
[Official skill documentation](https://learn.chatgpt.com/docs/build-skills).

A skill is instructions and optional helpers. It does not grant account access,
install image tools or override the user's permissions. A new video with changed
characters or sets still needs suitable reference assets and creative review.
