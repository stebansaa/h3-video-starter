# Start here

Follow the [README walkthrough](README.md#2-clone-the-repository-and-enter-it)
for the exact `git clone`, `cd`, project creation, text-editor and `codex`
commands, followed by RunPod account setup and preview approval.
The original root `script.txt` is the default example. The walkthrough copies
it to `projects/my-video/script.txt` so you can modify or replace the script
without changing the release baseline. Point Codex to that exact project file.

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

> Read AGENTS.md and use the included h3-video skill. My existing project is
> projects/my-video. Read projects/my-video/script.txt in full, preserve my
> edits, summarize the intended video and discuss the script with me first.
> Check this environment with scripts/first_session.py, guide me through
> missing setup, and verify and replay this repository offline. Once we agree
> on the script, adapt my project's plan and references to it. Guide me through
> RunPod setup and give me a current first-preview estimate. Use no paid
> compute until I authorize a budget and scope.

If the project does not exist yet, ask Codex to create it with
`python3 scripts/new_project.py my-video`, then edit its `script.txt` and ask
Codex to reread it. The renderer uses the JSON shot plan, so Codex must update
that plan from your approved text; saving new dialogue in the text file alone
does not change a render.

Once a budget and scope are authorized, routine setup, validation, generation
and cleanup within that scope do not need repeated approval. A preview-only
request still ends at the preview. The historical budget in the example is not
authorization for a new account.

Keep `projects/NAME/PROGRESS.md` current. On a later day, tell Codex:

> Read AGENTS.md and projects/NAME/PROGRESS.md. Inspect session.json and the
> saved run before resuming. Tell me what is complete, what remains and whether
> there is currently a running resource before taking a paid action.
