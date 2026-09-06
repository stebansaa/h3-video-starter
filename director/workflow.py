"""API graph derived from the pinned official T2V/I2V templates.

UI subgraphs, switches and expression nodes are resolved locally. Native H3,
sampler, decode and video-save nodes are kept intact. No custom nodes required.
"""
import math

from .common import DirectorError, ROOT, read_json, safe_id
from .plan import FPS, frame_count, prompt_for

PROFILES = {"preview": (512, 384, 20), "quality": (1024, 768, 25), "reference-preview": (640, 384, 20)}


def build(plan, shot, seed, prefix, profile="preview", first_frame=None, reference_videos=None):
    if profile not in PROFILES:
        raise DirectorError("Unknown profile: " + profile)
    if not isinstance(seed, int) or isinstance(seed, bool) or not 0 <= seed < 2**64:
        raise DirectorError("Seed must be an unsigned 64-bit integer.")
    safe_id(prefix)
    w, h, steps = PROFILES[profile]
    files = read_json(ROOT / "config/models.lock.json")["roles"]
    g = {}

    def node(key, kind, **inputs):
        g[key] = {"class_type": kind, "inputs": inputs}

    refs = reference_videos or []
    if refs:
        if not first_frame or len(refs) > 4 or [r["character"] for r in refs] != shot["characters"]:
            raise DirectorError("Reference mode requires a starting image and one ordered clip per character (maximum four).")
    diffusion = read_json(ROOT / "config/reference-model.lock.json")["file"]["path"].split("/")[-1] if refs else files["diffusion"]
    node("1", "UNETLoader", unet_name=diffusion, weight_dtype="default")
    node("2", "CLIPLoader", clip_name=files["text_encoder"], type="minimax", device="default")
    node("3", "VAELoader", vae_name=files["video_vae"])
    node("4", "VAELoader", vae_name=files["audio_vae"])
    node("5", "MiniMaxH3ImageToVideo", clip=["2", 0], vae=["3", 0],
         prompt=prompt_for(plan, shot), width=w, height=h, length=frame_count(shot["seconds"]))
    if refs:
        assignments = ["Reference assignments: <Picture 1> is the opening composition, wardrobe and set. Start at this image."]
        for i, ref in enumerate(refs, 1):
            visual = "<Video {}>".format(i) if i <= 3 else "<Picture 2>"
            assignments.append("{}: use {} for this character's face, mannerisms and identity, and <Audio {}> for their voice. "
                               "Ignore the reference's wardrobe, setting, laughter and spoken words; follow the new script.".format(ref["character"], visual, i))
        node("5", "MiniMaxH3ReferenceToVideo", clip=["2", 0], vae=["3", 0], audio_vae=["4", 0],
             prompt="\n".join(assignments) + "\n\n" + prompt_for(plan, shot), width=w, height=h,
             length=frame_count(shot["seconds"]), ref_image_size="match")
        # Preserve presentation order even when a fourth-character image follows.
        g["5"]["inputs"]["ref_images.ref_image_0"] = ["15", 0]
        for i, ref in enumerate(refs):
            loader, components = str(20 + i * 2), str(21 + i * 2)
            node(loader, "LoadVideo", file=ref["video"])
            node(components, "GetVideoComponents", video=[loader, 0])
            if i < 3:
                g["5"]["inputs"]["ref_videos.ref_video_" + str(i)] = [components, 0]
                g["5"]["inputs"]["ref_video_audios.ref_video_audio_" + str(i)] = [components, 1]
            else:
                # Native H3 accepts three video references. Its reference-image
                # encoder takes img[:1], so the fourth clip supplies one face
                # image plus a standalone soundtrack, labelled Audio 4 after
                # the three paired video soundtracks. No extra custom nodes.
                g["5"]["inputs"]["ref_images.ref_image_1"] = [components, 0]
                g["5"]["inputs"]["ref_audios.ref_audio_0"] = [components, 1]
    if first_frame:
        node("15", "LoadImage", image=first_frame)
        if refs:
            g["5"]["inputs"]["ref_images.ref_image_0"] = ["15", 0]
            node("16", "MiniMaxH3AddGuide", positive=["5", 0], latent=["5", 1],
                 vae=["3", 0], image=["15", 0], frame_idx=0)
        else:
            g["5"]["inputs"]["first_frame"] = ["15", 0]
    node("6", "RandomNoise", noise_seed=seed)
    node("7", "BasicGuider", model=["1", 0], conditioning=["16" if refs else "5", 0])
    node("8", "KSamplerSelect", sampler_name="res_multistep")
    node("9", "BasicScheduler", model=["1", 0], scheduler="simple", steps=steps, denoise=1.0)
    node("10", "SamplerCustomAdvanced", noise=["6", 0], guider=["7", 0], sampler=["8", 0],
         sigmas=["9", 0], latent_image=["5", 1])
    node("11", "VAEDecode", samples=["10", 0], vae=["3", 0])
    node("12", "VAEDecodeAudio", samples=["10", 0], vae=["4", 0])
    node("13", "CreateVideo", images=["11", 0], audio=["12", 0], fps=FPS, bit_depth=8)
    node("14", "SaveVideo", video=["13", 0], filename_prefix="director/" + prefix,
         format="mp4", codec="auto")
    return g


def preflight(graph, info, check_files=True):
    """Validate against the server's actual /object_info before loading weights."""
    errors = []
    for nid, node in graph.items():
        kind = node["class_type"]
        if kind not in info:
            errors.append("Missing node " + kind)
            continue
        schema = info[kind]
        inputs = schema.get("input", {})
        required = inputs.get("required", {})
        required = dict(required)
        allowed = dict(required, **inputs.get("optional", {}))
        # Native autogrow inputs use zero-based, dotted API names. Prompt labels
        # are separately one-based. Expand the upstream template's exact bounds.
        for name, definition in list(allowed.items()):
            if definition[0] != "COMFY_AUTOGROW_V3":
                continue
            template = definition[1]["template"]
            names = template.get("names") or [template["prefix"] + str(i) for i in range(template["max"])]
            child_groups = template["input"]
            children = child_groups.get("required", {}) or child_groups.get("optional", {})
            child_definition = next(iter(children.values()))
            allowed.pop(name)
            required.pop(name, None)
            for index, child in enumerate(names):
                key = name + "." + child
                allowed[key] = child_definition
                if index < template.get("min", 0) and child_groups.get("required"):
                    required[key] = child_definition
        # Native v3 SaveVideo uses a dynamic combo, not a simple list of codecs.
        # Expand the selected branch using the same flattened names as the API.
        pending = list(allowed)
        while pending:
            name = pending.pop()
            definition = allowed[name]
            if definition[0] != "COMFY_DYNAMICCOMBO_V3" or name not in node["inputs"]:
                continue
            options = definition[1].get("options", [])
            selected = next((o for o in options if o["key"] == node["inputs"][name]), None)
            if selected is None:
                errors.append("Unavailable dynamic option at " + kind + "." + name)
                continue
            for group, definitions in selected.get("inputs", {}).items():
                if group not in ("required", "optional"):
                    continue
                for child, child_definition in definitions.items():
                    full_name = name + "." + child
                    allowed[full_name] = child_definition
                    if group == "required":
                        required[full_name] = child_definition
                    pending.append(full_name)
        for name in required:
            if name not in node["inputs"]:
                errors.append(kind + "." + name + " is required")
        for name, val in node["inputs"].items():
            if name not in allowed:
                errors.append(kind + "." + name + " is not supported by this server")
                continue
            spec = allowed[name][0]
            opts = allowed[name][1] if len(allowed[name]) > 1 and isinstance(allowed[name][1], dict) else {}
            if isinstance(val, list):
                if len(val) != 2 or not isinstance(val[0], str) or val[0] not in graph or type(val[1]) is not int:
                    errors.append("Invalid link at " + kind + "." + name)
                    continue
                parent = info.get(graph[val[0]]["class_type"], {})
                outputs = parent.get("output", [])
                if not 0 <= val[1] < len(outputs) or (isinstance(spec, str) and outputs[val[1]] != spec):
                    errors.append("Incompatible output link at " + kind + "." + name)
            elif isinstance(spec, list):
                if (kind, name) in (("LoadImage", "image"), ("LoadVideo", "file")) and not check_files:
                    continue
                if val not in spec:
                    errors.append("Unavailable value for " + kind + "." + name + ": " + str(val))
            elif spec in ("INT", "FLOAT"):
                if type(val) not in ((int,) if spec == "INT" else (int, float)):
                    errors.append("Invalid number at " + kind + "." + name)
                elif not math.isfinite(val) or ("min" in opts and val < opts["min"]) or ("max" in opts and val > opts["max"]):
                    errors.append("Out-of-range value at " + kind + "." + name)
            elif spec == "STRING" and not isinstance(val, str):
                errors.append("Invalid string at " + kind + "." + name)
            elif spec == "BOOLEAN" and type(val) is not bool:
                errors.append("Invalid boolean at " + kind + "." + name)
    if errors:
        raise DirectorError("Preflight failed:\n" + "\n".join(errors))
    return {"nodes": len(graph), "status": "passed"}
