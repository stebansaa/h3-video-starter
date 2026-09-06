# Independent live handoff trial — September 6, 2026

A fresh agent produced a new reference-conditioned clip using only a clean
clone and its instructions. It resolved missing local media tools, completed
all 85 tests and the recorded replay, checked the account, provisioned a fresh
disposable GPU, installed the pinned stack, verified remote weights, passed
live preflight, rendered the first shot and detected extra opening speech.
No rendering or installation source-code fixes were needed.

After the supervisor requested an edited preview, the agent removed the
isolated extra phrase and transcribed the actual final MP4 independently.
The [7.54-second preview and evidence](../examples/standing-desk-preview) are
included. The approximately $0.43 estimated session cost includes cold setup;
it is not just inference cost. The temporary pod was stopped/deleted and both
the agent and supervisor verified its absence.

## Improvements made from the trial

1. **Balance lookup:** REST `/billing` is spending history. Added the minimal
   GraphQL balance query instead of leaving a new agent to discover it.
2. **Stock lookup:** documented explicit catalog availability filters,
   response fields and the distinction between OpenAPI `/v2/...` paths and
   client-relative paths. The new [quote guide](runpod-quote.md) was executed
   verbatim against the live APIs and passed.
3. **Schema access:** documented the working repository HTTP client/curl path
   after plain urllib received HTTP 403.
4. **Quiet downloads:** documented inspecting partial-file growth and process
   activity before assuming a quiet Xet download has stalled.
5. **Creative review:** retained both the bad prefix and the corrected preview,
   the exact hash-bound cut, measured gap, original/segment/final ASR and final
   technical verification. Prompting for exactly two utterances did not prevent
   extra speech. The review and editing steps are required parts of production.
6. **Provisional export:** added a tested [single-clip recipe](single-clip-preview.md)
   after a manual MKV-to-MP4 video-copy export inherited rounded timestamps.
   The final export explicitly encodes at 24 fps. This trim used the library
   helper and FFmpeg; the episode assembler was exercised only by offline replay.

## Scope and limits

The agent had no conversation-history fork and used no other checkout, global
RunPod skill or connected MCP tool. The parent provided the clone, private
credential and $2/90-minute scope, supervised spending and cleanup, and updated
the release folder separately. The trial checkout's shipped files remained
unchanged during generation. The parent supplied no production workaround
before the first raw clip and its review; it then requested the corrective edit.

The local host and available tools were shared. This does not prove every
Codex installation has terminal, SSH or media capabilities, nor that another
account has stock or funding. Future dependency changes and creative output
still require live preflight and a reviewed preview. Only shot 01a was generated;
the trial did not regenerate the entire episode or test a new picture/audio join.
Human listening and lip-sync review remain pending.
