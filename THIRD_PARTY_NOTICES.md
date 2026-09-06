# Sources and license scope

`references/opening-v2/{jerry,george,kramer}.mp4`,
`references/episode-v1/elaine.mp4` and the three audience WAV excerpts come from
[Seinfeld: The Contest (Clip) | TBS](https://www.youtube.com/watch?v=wGhg-htVnJ0).
Exact excerpt timings and crops are recorded in each reference directory's
`sources.json` and summarized in `docs/assets.md`. These are third-party media;
this repository does not grant copyright, trademark, performer-likeness or
voice rights to them. Attribution is not a blanket redistribution license.

`image.png` is the original image supplied for this production. The other
starting images were generated from it and approved during production. Their
inclusion is not a representation that third-party character rights have been
licensed. The generated example and fan script are production demonstrations.
Use assets for which you have appropriate rights in your own published work.

`vendor/` contains reference snapshots from ComfyUI and provider API/model
metadata. `vendor/LICENSE` preserves ComfyUI's GNU GPL version 3 license;
`vendor/provenance.json` and `vendor/h3-guides/provenance.json` identify upstream
revisions and URLs. The snapshots are for contract tests and investigation;
remote setup fetches the pinned upstream revision.

Model weights are not included. Their upstream terms remain applicable when
downloaded on a GPU server; see the pinned model source in `config/` and
`vendor/model-info.json`.

No blanket open-source license is assigned to this entire mixed code/media
package. The repository owner can choose a license for their own code when
publishing; that choice does not relicense third-party media or vendor code.
