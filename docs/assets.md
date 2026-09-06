# Exact asset map

All paths in this page are relative to the repository root. The authoritative
sequence input is `references/episode-v1/manifest-v2.json`, paired with
`plans/episode-reference-v2.json`. Do not pick assets just by finding a similar
filename; earlier versions are retained as evidence of corrections.

## Character references actually used

Source: [Seinfeld: The Contest (Clip) | TBS](https://www.youtube.com/watch?v=wGhg-htVnJ0).
The supplied MP4s are already cut and cropped; the source start times below are
provenance, not offsets to apply again to these short files.

| Character | Included file | Source start | Source duration | Crop width:height:x:y |
| --- | --- | --- | --- | --- |
| Jerry | `references/opening-v2/jerry.mp4` | 144.8 s | 3.25 s | `416:384:390:38` |
| George | `references/opening-v2/george.mp4` | 99.2 s | 3.25 s | `352:400:412:20` |
| Kramer | `references/opening-v2/kramer.mp4` | 127.4 s | 2.65 s | `352:416:164:24` |
| Elaine | `references/episode-v1/elaine.mp4` | 154.5 s | 2.65 s | `352:416:16:20` |

The full source video is not needed or included. Exact source URL, checksum and
crop metadata are in the two `sources.json` files. Face stills and contact sheets
are included for inspection. `director.references` prepares these excerpts on
the H3 frame grid, at 24 fps and 32 kHz stereo, immediately before upload.
Prepared duplicates are generated locally under run state and are not required
in the release.

## Starting images actually used

| Shot | Starting image | Intent |
| --- | --- | --- |
| 01a | `image.png` | Original user image; wardrobe authority |
| 01b | `references/episode-v1/window-three-v2.png` | Corrected interior angle with Jerry, George and Kramer |
| 01c | Previous last frame | Continue that angle |
| 02a | `references/episode-v1/window-two-v2.png` | Corrected Jerry/George window angle |
| 02b | Previous last frame | Same angle |
| 03a | `references/episode-v1/window-elaine.png` | Elaine entrance/coverage |
| 03b | Previous last frame | Same angle |
| 04 | `references/episode-v1/doorway-kramer.png` | Kramer doorway |
| 05a | `references/episode-v1/counter-four.png` | Four-character counter master |
| 05b, 05c, 06a, 06b, 06c | Previous last frame | Continue the counter angle |

`window-three.png` and `window-two.png` are superseded. They exposed unwanted
wardrobe changes, including George's shirt pattern and Kramer's missing shirt
panels. `image-prompts.json`, `window-three-prompts.json` and
`window-two-correction-prompt.txt` preserve generation/correction instructions.
`references/opening-v2/start.png` and the earlier manifests/plans are historical
single-shot or earlier sequence inputs. The v2 sequence above is the completed
production baseline.

The image is both `ref_images.ref_image_0` (Picture 1) and an actual frame-zero
`MiniMaxH3AddGuide`. For four-character shots, the fourth face is Picture 2
and its standalone soundtrack is Audio 4; do not displace the starting image.
Character order comes from `shot.characters`, not alphabetical order.

## Audience and editing evidence

`references/episode-v1/audio/` contains three excerpts from the same TBS source:

| File | Source start | Duration | Baseline per-cue gain |
| --- | --- | --- | --- |
| `laugh-soft.wav` | 13.2 s | 2.5 s | −3 dB |
| `laugh-medium.wav` | 93.0 s | 2.7 s | 0 dB |
| `laugh-big.wav` | 133.4 s | 2.4 s | +2 dB |

`plans/episode-mix.json` holds the ten actual audience placements and 48-frame
ending hold. `examples/bitcoin-contest/run/` holds all fourteen raw source takes,
their last frames, contact sheets, API graphs, histories and review state.
The example's `cuts.json` is required to reproduce the final edit. Its
`transcripts/` directory contains the selected per-source transcripts that drove
cue timing; `evidence/` preserves additional passes, the final transcript and
the rejected original 01b continuation.

API graphs contain uploaded filenames from the historical run. They are records,
not ready-to-submit workflows for a new server. The director prepares/uploads
fresh assets and builds a graph each time from the pinned builder.

`PACKAGE_MANIFEST.json` records the size and SHA-256 of each shipped file. Use
`scripts/verify_package.py` to check that assets arrived intact. See
`THIRD_PARTY_NOTICES.md` for source and rights scope.
