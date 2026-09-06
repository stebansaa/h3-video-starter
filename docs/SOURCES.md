# Primary sources checked for the handoff

Checked 2026-09-06; live services and package releases may change.

- [Codex AGENTS.md guide](https://learn.chatgpt.com/docs/agent-configuration/agents-md):
  instruction discovery, scope and session startup. The older developers.openai.com
  AGENTS.md URL redirected here during verification.
- [Codex skill authoring](https://learn.chatgpt.com/docs/build-skills):
  repository-local skill discovery and explicit invocation.
- [Codex MCP setup](https://learn.chatgpt.com/docs/extend/mcp?surface=cli):
  connection configuration, environment-based credentials and OAuth. Optional
  CLI examples were also checked against local `codex mcp add --help`.
- [RunPod agent setup](https://docs.runpod.io/agent-setup.md): provider MCP and
  API-key setup guidance; optional for the shipped direct API workflow.
- [RunPod storage types](https://docs.runpod.io/pods/storage/types): container,
  pod-volume and network-volume lifetime. The stop/resume instructions depend
  on selecting the correct storage type.
- [RunPod REST v2 OpenAPI](https://api.runpod.io/v2/openapi.json): creation,
  pod actions, catalog and billing paths. `runpod-openapi-checked.json` records
  the checked shape; `vendor/runpod-v2-contract.json` preserves the original
  production contract used by tests.
- [RunPod GraphQL specification](https://graphql-spec.runpod.io/#query-myself):
  minimal read-only `clientBalance`/`currentSpendPerHr` query. REST billing history
  is not account balance; live query examples are in `runpod-quote.md`.
- [ComfyUI repository](https://github.com/Comfy-Org/ComfyUI): pinned source
  revisions in `config/` and `vendor/`. The reference guide change is recorded
  in [PR 15439](https://github.com/Comfy-Org/ComfyUI/pull/15439).
- [MiniMax H3 model package](https://huggingface.co/Comfy-Org/MiniMax-H3):
  exact revisions, filenames, expected bytes and checksums in the lock files.
- [TBS reference clip](https://www.youtube.com/watch?v=wGhg-htVnJ0): supplied
  character and audience excerpts, with timing/crop provenance in `sources.json`.
- [actions/checkout](https://github.com/actions/checkout) and
  [actions/setup-python](https://github.com/actions/setup-python): official
  GitHub action tags resolved to full commit SHAs for CI; see `ci-pins.json`.

Provider documentation supports API/storage behavior, not creative quality.
Production quality claims come from the included media and review evidence.
