# Start here

Open a Codex session in the cloned folder and ask it to read `AGENTS.md` and use
the included `$h3-video` skill. Begin with `python3 scripts/first_session.py` and
the [first-session guide](docs/first-session.md). If it
clones the repository during an existing session, explicitly ask it to enter
the new folder and read the instructions; automatic instruction discovery
happens at session startup. See the [official AGENTS.md guide](https://learn.chatgpt.com/docs/agent-configuration/agents-md).

There are three useful starting points:

1. **See the result:** open `examples/bitcoin-contest/final.mp4` and its contact
   sheet. No setup, account or GPU is needed.
2. **Check the machinery:** run the README's offline checks and replay. This
   exercises real media operations plus mocked API transport, and rebuilds the
   complete edit from the supplied source takes. It costs no GPU money.
3. **Make a new video:** create a project, adapt its script and plan, validate
   its assets, then follow the RunPod runbook for a small paid preview.

For a new render you supply a RunPod API key privately, a funded account, an
initial spending limit and the idea/script. The agent can create a local SSH
key for this project. Do not paste private keys into a public issue or commit.
If you already provide a suitable GPU server, skip pod creation and use its SSH
connection for remote setup.

The four character clips, approved starting images and audience samples are
already included. No source-video download is needed for the example. New
characters or sets need their own reference assets. An agent with image tools
can derive new angles from approved images; otherwise provide those images.

The simplest initial request is:

> Read AGENTS.md and use the included h3-video skill. Check this environment
> with scripts/first_session.py and guide me through missing setup.
> Verify and replay this repository offline. Create project
> `my-scene` about [idea], keeping the included cast. Prepare everything for a
> first-clip preview. Use no paid compute until we have a current estimate and
> my session budget. Once authorized, operate the server and stop it while I
> review the clip.

Once a budget and scope are authorized, routine setup, validation, generation
and cleanup within that scope do not need repeated approval. A preview-only
request still ends at the preview. The historical budget in the example is not
authorization for a new account.

Keep `projects/NAME/PROGRESS.md` current. On a later day, tell Codex:

> Read AGENTS.md and projects/NAME/PROGRESS.md. Inspect session.json and the
> saved run before resuming. Tell me what is complete, what remains and whether
> there is currently a running resource before taking a paid action.
