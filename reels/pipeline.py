"""Deterministic Wrydeco media pipeline. Creative decisions are supplied by the skill.

No paid API, shell interpolation, or automatic claims of editorial approval.
"""
from __future__ import annotations

import argparse
import contextlib
import hashlib
import json
import math
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import time
import urllib.request
import effects
import timing

ROOT = Path(__file__).resolve().parents[1]
LIBRARY = ROOT / "reels/assets"
IMAGES = {".jpg", ".jpeg", ".png", ".webp"}
VIDEOS = {".mp4", ".mov", ".mkv", ".webm", ".m4v", ".avi"}
FPS = 30


def render_config(plan):
    config = plan.get("render", {"width": 720, "height": 1280, "fps": 30})
    if config not in ({"width": 720, "height": 1280, "fps": 30},
                      {"width": 1080, "height": 1920, "fps": 30}):
        raise ValueError("Supported render profiles: 720x1280 or 1080x1920, 30fps")
    return config


def read(path):
    return json.loads(Path(path).read_text(encoding="utf-8-sig"))


def write(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding="utf-8")
    tmp.replace(path)


def run(args, timeout=900, cwd=None):
    result = subprocess.run([str(x) for x in args], cwd=cwd, capture_output=True,
                            text=True, encoding="utf-8", errors="replace", timeout=timeout)
    if result.returncode:
        raise RuntimeError(f"{args[0]} failed ({result.returncode}): {result.stderr[-4500:]}")
    return result


def ff(args, cwd=None):
    return run(["ffmpeg", "-hide_banner", "-nostdin", "-y", "-threads", "2",
                "-filter_threads", "1", "-filter_complex_threads", "1", *args], cwd=cwd)


def probe(path):
    return json.loads(run(["ffprobe", "-v", "error", "-show_format", "-show_streams",
                           "-of", "json", path], timeout=60).stdout)


def duration(path):
    return float(probe(path)["format"]["duration"])


def fingerprint(path):
    p = Path(path)
    stat = p.stat()
    return [str(p.resolve()), stat.st_size, stat.st_mtime_ns]


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True).encode()).hexdigest()


@contextlib.contextmanager
def job_lock():
    path = ROOT / "work/reels.lock"
    path.parent.mkdir(exist_ok=True)
    try:
        fd = os.open(path, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
    except FileExistsError:
        raise RuntimeError(f"Another reel job owns {path}. Inspect its PID before removing a stale lock.")
    try:
        os.write(fd, str(os.getpid()).encode())
        os.close(fd)
        yield
    finally:
        path.unlink(missing_ok=True)


def checkpoint(target, key, build):
    target = Path(target)
    marker = target.with_suffix(target.suffix + ".checkpoint.json")
    if target.exists() and marker.exists() and read(marker).get("key") == digest(key):
        return
    build()
    if not target.exists() or not target.stat().st_size:
        raise RuntimeError(f"Stage produced no output: {target}")
    write(marker, {"key": digest(key), "completed": time.time()})


def sheet(paths, output, labels=None, columns=4):
    from PIL import Image, ImageDraw, ImageOps
    if not paths:
        return
    canvas = Image.new("RGB", (columns * 200, math.ceil(len(paths) / columns) * 230), "#171b20")
    draw = ImageDraw.Draw(canvas)
    for i, p in enumerate(paths):
        with Image.open(p) as im:
            thumb = ImageOps.contain(im.convert("RGB"), (192, 202))
            x, y = (i % columns) * 200, (i // columns) * 230
            canvas.paste(thumb, (x + (200-thumb.width)//2, y))
            draw.text((x+4, y+205), (labels[i] if labels else Path(p).stem)[:30], fill="white")
    canvas.save(output, quality=88)


def analyze(source, job):
    source, job = Path(source).resolve(), Path(job).resolve()
    if not source.is_dir():
        raise ValueError("Input must be an existing media directory")
    job.mkdir(parents=True, exist_ok=True)
    frames = job / "analysis"
    frames.mkdir(exist_ok=True)
    try:
        files = [Path(x) for x in run(["rg", "--files", str(source)]).stdout.splitlines()]
    except (FileNotFoundError, RuntimeError):
        files = list(source.rglob("*"))
    previous_path = job/"media-manifest.json"
    previous = {a["path"]:a for a in read(previous_path)["assets"]} if previous_path.exists() else {}
    assets = []
    for path in sorted(files):
        if path.suffix.lower() not in IMAGES | VIDEOS or job in path.parents:
            continue
        ident = digest(fingerprint(path))[:12]
        cached = previous.get(str(path))
        if cached and cached.get("status") == "ok" and cached.get("fingerprint") == fingerprint(path) and Path(cached["storyboard"]).exists():
            assets.append(cached)
            continue
        entry = {"id": ident, "path": str(path), "fingerprint": fingerprint(path)}
        try:
            info = probe(path)
            video = next(s for s in info["streams"] if s["codec_type"] == "video")
            still = path.suffix.lower() in IMAGES
            length = 0 if still else float(info["format"]["duration"])
            entry.update(kind="image" if still else "video", duration=length,
                         width=video["width"], height=video["height"],
                         fps=video.get("avg_frame_rate"), rotation=video.get("side_data_list", []),
                         has_audio=any(s["codec_type"] == "audio" for s in info["streams"]),
                         metadata=info)
            # Uniform coverage plus actual scene-change timestamps, bounded for long recordings.
            times = [0] if still else [round(length*i/9, 3) for i in range(9)]
            if not still:
                scenes = ff(["-i", path, "-vf", "fps=2,scale=240:-2,select='gt(scene,0.32)',showinfo",
                             "-an", "-f", "null", "-"]).stderr
                times += [float(t) for t in re.findall(r"pts_time:([0-9.]+)", scenes)][:20]
            times = sorted(set(t for t in times if still or t < length-0.03))
            previews = []
            for n, t in enumerate(times):
                out = frames / f"{ident}-{n:02d}.jpg"
                checkpoint(out, [entry["fingerprint"], t], lambda out=out, t=t: ff([
                    *([] if still else ["-ss", str(t)]), "-i", path, "-frames:v", "1", "-vf", "scale=384:-2", out]))
                previews.append(str(out))
            storyboard = frames / f"{ident}-sheet.jpg"
            sheet(previews, storyboard, [f"{t:.2f}s" for t in times])
            entry.update(samples=[{"time": t, "path": p} for t, p in zip(times, previews)],
                         storyboard=str(storyboard), status="ok")
        except Exception as exc:
            entry.update(status="error", error=str(exc))
        assets.append(entry)
        print(f"Analyzed {path.name}: {entry['status']}", flush=True)
        write(job / "media-manifest.json", {"source": str(source), "assets": assets})
    if not assets:
        raise ValueError("No supported media found")
    write(job / "media-manifest.json", {"source": str(source), "assets": assets})
    return job / "media-manifest.json"


def library():
    catalog = read(LIBRARY / "catalog.json")
    return {x["id"]: x for x in catalog["assets"]}


def asset_path(asset):
    p = (LIBRARY / asset["file"]).resolve()
    if not p.is_relative_to(LIBRARY.resolve()):
        raise ValueError("Library path escapes assets directory")
    if not p.is_file() or not asset.get("license") or not asset.get("source_url"):
        raise ValueError(f"Unlicensed or missing audio asset: {asset['id']}")
    if asset.get("sha256") and hashlib.sha256(p.read_bytes()).hexdigest() != asset["sha256"]:
        raise ValueError(f"Audio library asset was modified: {asset['id']}")
    return p


def finite(value, low, high, label):
    if not isinstance(value, (float, int)) or isinstance(value, bool) or not math.isfinite(value) or not low <= value <= high:
        raise ValueError(f"Invalid {label}: {value}")


def validate(plan, job):
    # Part of the plan digest: old prepared mixes cannot be exported unchanged.
    plan["audio_policy"] = "voice-chill-sfx-only-v1"
    if plan.get("version") not in (1, 2):
        raise ValueError("edit-plan version must be 1 or 2")
    render_config(plan)
    if plan["version"] == 1 and ("render" in plan or any(
            any(k in c.get("effects", {}) for k in ("speed_segments", "motion", "title_style"))
            for c in plan.get("clips", []))):
        raise ValueError("New rendering controls require edit-plan version 2")
    manifest = {a["id"]: a for a in read(Path(job)/"media-manifest.json")["assets"] if a["status"] == "ok"}
    if len(plan.get("hooks", [])) != 3 or not plan.get("story"):
        raise ValueError("Three considered hooks and an evidence-based story are required")
    clips = plan.get("clips", [])
    if not 3 <= len(clips) <= 12:
        raise ValueError("Use 3–12 selected shots")
    total = 0.0
    for index, clip in enumerate(clips):
        a = manifest[clip["asset_id"]]
        if fingerprint(a["path"]) != a["fingerprint"]:
            raise ValueError("Source changed; analyze it again")
        finite(clip["in"], 0, 1e6, "source in")
        if a["kind"] == "image" and clip["in"] != 0:
            raise ValueError("Images must start at zero")
        finite(clip["duration"], 0.5, 8, "shot duration")
        effects.validate(clip, a)
        if a["kind"] == "video" and clip["in"] + effects.source_duration(clip) > a["duration"] + .02:
            raise ValueError("Shot extends beyond source")
        finite(clip.get("crop_x", .5), 0, 1, "crop_x")
        if clip.get("fit", "cover") not in ("cover", "contain"):
            raise ValueError("fit must be cover or contain")
        finite(clip.get("crop_y", .5), 0, 1, "crop_y")
        if "source_crop" in clip:
            box = clip["source_crop"]
            if plan["version"] != 2 or not isinstance(box, dict) or set(box) != {"x", "y", "width", "height"}:
                raise ValueError("source_crop requires v2 normalized rectangle")
            for key in ("x", "y"):
                finite(box[key], 0, 1, key)
            for key in ("width", "height"):
                finite(box[key], .25, 1, key)
            if box["x"]+box["width"] > 1 or box["y"]+box["height"] > 1:
                raise ValueError("Crop extends beyond source")
        finite(clip.get("sound_gain", 0), 0, 1, "sound_gain")
        transition = clip.get("transition", "cut")
        if transition not in ("cut", "fade"):
            raise ValueError("Supported transitions: cut, fade")
        if not clip.get("reason") or not clip.get("evidence"):
            raise ValueError("Shot needs reason and visual evidence")
        finite(clip.get("transition_duration", .4), .1, .5, "transition duration")
        overlap = timing.overlap(clip, index)
        if overlap >= clip["duration"] or (index and overlap >= clips[index-1]["duration"]):
            raise ValueError("Transition must be shorter than both adjacent shots")
        clip["timeline_start"] = round(total-overlap, 6)
        total += clip["duration"]-overlap
        text = clip.get("text", "")
        if len(text.splitlines()) > 2 or any(len(line) > 28 for line in text.splitlines()):
            raise ValueError("Text must fit two lines, max 28 characters per line")
        finite(clip.get("contrast", 1), .9, 1.15, "contrast")
        finite(clip.get("saturation", 1), .85, 1.2, "saturation")
        color = clip.get("color", {})
        if not isinstance(color, dict) or set(color)-{"brightness", "gamma", "red", "blue"}:
            raise ValueError("Unknown color adjustment")
        finite(color.get("brightness", 0), -.08, .08, "brightness")
        finite(color.get("gamma", 1), .9, 1.1, "gamma")
        for channel in ("red", "blue"):
            finite(color.get(channel, 0), -.08, .08, channel)
        if plan["version"] == 2:
            if clip.get("role") not in ("hook", "context", "action", "detail", "payoff", "atmosphere"):
                raise ValueError("v2 shots need an editorial role")
            for mark in clip.get("actions", []):
                if not mark.get("label"):
                    raise ValueError("Action marker needs a label")
                timing.output_at(clip, mark["source_time"]-clip["in"])
    total = timing.schedule(clips)
    generated = [c for c in clips if manifest[c["asset_id"]].get("origin") == "google_flow"]
    if len(generated) > 2 or sum(c["duration"] for c in generated) > 2:
        raise ValueError("AI cutaways are limited to two shots and two seconds total")
    for c in generated:
        asset = manifest[c["asset_id"]]
        review = asset.get("ai_review", {})
        if c.get("role") != "atmosphere" or review.get("visual") != "pass" or not review.get("no_product_or_people"):
            raise ValueError("Flow cutaways require a no-product/no-people visual review")
    outro = Path(plan["outro"]).resolve()
    outro_info = probe(outro)
    outro_duration = float(outro_info["format"]["duration"])
    if not 15 <= total + outro_duration <= 30:
        raise ValueError("Reel including outro must be 15–30 seconds")
    narration = plan.get("narration", [])
    if not narration:
        raise ValueError("Voice-over is required")
    for item in narration:
        finite(item["start"], 0, total-.4, "voice start")
        if not item.get("text", "").strip() or not item.get("evidence"):
            raise ValueError("Narration needs text and supporting evidence")
    lib = library()
    music = lib[plan["music"]["id"]]
    if music["kind"] != "music":
        raise ValueError("Music ID must reference music")
    music_duration = duration(asset_path(music))
    if music_duration < total+outro_duration:
        raise ValueError("Music must cover the complete Reel including silent outro")
    finite(plan["music"].get("in", 0), 0, music_duration-total-outro_duration, "music in")
    finite(plan["music"].get("gain", .24), 0, 1, "music gain")
    duck = plan.get("mix", {})
    if set(duck)-{"duck_threshold", "duck_ratio", "duck_attack", "duck_release"}:
        raise ValueError("Unknown mix control")
    for key, default, low, high in (("duck_threshold", .025, .005, .2), ("duck_ratio", 5, 1, 12),
                                   ("duck_attack", 15, 1, 100), ("duck_release", 300, 50, 1500)):
        finite(duck.get(key, default), low, high, key)
    if not 2 <= len(plan.get("sfx", [])) <= 4:
        raise ValueError("Choose 2–4 purposeful SFX cues")
    for cue in plan["sfx"]:
        if "shot" in cue:
            if type(cue["shot"]) is not int or not 0 <= cue["shot"] < len(clips):
                raise ValueError("Invalid SFX shot index")
            finite(cue["source_time"], 0, 1e6, "cue source time")
            cue["start"] = round(timing.cue_time(cue, clips), 6)
        if lib[cue["id"]]["kind"] != "sfx" or not cue.get("reason"):
            raise ValueError("Each SFX must reference a licensed SFX and explain its purpose")
        length = duration(asset_path(lib[cue["id"]]))
        finite(cue["start"], 0, total-length, "SFX start")
        finite(cue.get("gain", .3), 0, 1, "SFX gain")
    plan["content_duration"] = round(total, 6)
    plan["outro_duration"] = outro_duration
    plan["total_duration"] = round(total+outro_duration, 6)
    return manifest


def voice(plan, job):
    import numpy as np
    import soundfile as sf
    from kokoro_onnx import Kokoro
    import onnxruntime as ort
    models = ROOT / ".cache/kokoro"
    options = ort.SessionOptions()
    options.intra_op_num_threads = 2
    options.inter_op_num_threads = 1
    session = ort.InferenceSession(str(models/"kokoro-v1.0.onnx"), sess_options=options,
                                 providers=["CPUExecutionProvider"])
    # kokoro-onnx 0.4.9 assumes int32 speed for input_ids exports; v1.1 expects float.
    # Adapt from the actual model signature rather than patching installed dependencies.
    class TypedSession:
        def __getattr__(self, name):
            return getattr(session, name)

        def run(self, outputs, inputs):
            dtypes = {"tensor(float)": np.float32, "tensor(int64)": np.int64, "tensor(int32)": np.int32}
            normalized = {i.name: np.asarray(inputs[i.name], dtype=dtypes[i.type]) for i in session.get_inputs()}
            return session.run(outputs, normalized)
    engine = Kokoro.from_session(TypedSession(), str(models/"voices-v1.0.bin"))
    intervals = []
    for i, line in enumerate(plan["narration"]):
        out = job / f"voice-{i}.wav"
        spoken = line["text"].replace("Wrydeco", plan.get("brand_pronunciation", "Rye deco"))
        def build():
            samples, rate = engine.create(spoken, voice="af_heart", speed=1.0, lang="en-us")
            sf.write(str(out), samples, rate)
        checkpoint(out, [spoken, "af_heart", "kokoro-onnx-0.4.9"], build)
        end = line["start"]+duration(out)
        if end > plan["content_duration"]-.4:
            raise ValueError(f"Voice {i} ends at {end:.2f}s; shorten copy (outro {plan['content_duration']:.2f}s)")
        intervals.append({"start": line["start"], "end": end, "file": str(out)})
    ordered = sorted(intervals, key=lambda x: x["start"])
    if any(a["end"] > b["start"] for a,b in zip(ordered, ordered[1:])):
        raise ValueError("Narration phrases overlap; adjust starts or shorten text")
    write(job/"voice-timing.json", intervals)
    write(job/"voice-plan.json", {"key": digest([plan["narration"], plan["content_duration"], plan.get("brand_pronunciation", "Rye deco")])})


def normalize(source, target):
    result = ff(["-i", source, "-vn", "-af", "loudnorm=I=-16:LRA=9:TP=-2:print_format=json",
                 "-f", "null", "-"])
    stats = json.loads(result.stderr[result.stderr.rfind("{"):])
    if not math.isfinite(float(stats["input_i"])):
        raise ValueError("Audio contains no measurable signal")
    filt = ("loudnorm=I=-16:LRA=9:TP=-2:linear=true:"
            f"measured_I={stats['input_i']}:measured_LRA={stats['input_lra']}:"
            f"measured_TP={stats['input_tp']}:measured_thresh={stats['input_thresh']}:"
            f"offset={stats['target_offset']}")
    ff(["-i", source, "-vn", "-af", filt, "-ar", "48000", "-ac", "2", "-c:a", "aac", "-b:a", "192k", target])
    return stats


def prepare(plan, job, manifest):
    if read(job/"voice-plan.json")["key"] != digest([plan["narration"], plan["content_duration"], plan.get("brand_pronunciation", "Rye deco")]):
        raise ValueError("Voice schedule changed; rerun voice")
    total = plan["content_duration"]
    config = render_config(plan)
    width, height = config["width"], config["height"]
    parts = []
    for i, clip in enumerate(plan["clips"]):
        a = manifest[clip["asset_id"]]
        out = job / f"scene-{i:02d}.mp4"
        textfile = job / f"text-{i:02d}.txt"
        textfile.write_text(clip.get("text", ""), encoding="utf-8")
        vf = (f"scale={width}:{height}:force_original_aspect_ratio=increase,"
              f"crop={width}:{height}:(iw-{width})*{clip.get('crop_x', .5)}:(ih-{height})*{clip.get('crop_y', .5)}")
        if clip.get("fit") == "contain":
            vf = (f"scale={width}:{height}:force_original_aspect_ratio=decrease,"
                  f"pad={width}:{height}:(ow-iw)/2:(oh-ih)/2:color=0x101614")
        color = clip.get("color", {})
        box = clip.get("source_crop")
        crop = (f"crop=trunc(iw*{box['width']}/2)*2:trunc(ih*{box['height']}/2)*2:"
                f"trunc(iw*{box['x']}/2)*2:trunc(ih*{box['y']}/2)*2,") if box else ""
        vf = timing.setpts(clip)+",fps=30,"+crop+vf+",setsar=1"
        vf += (f",eq=contrast={clip.get('contrast',1)}:saturation={clip.get('saturation',1)}:"
               f"brightness={color.get('brightness',0)}:gamma={color.get('gamma',1)},"
               f"colorbalance=rm={color.get('red',0)}:bm={color.get('blue',0)}")
        if clip.get("effects", {}).get("push_in", 1) != 1 or clip.get("effects", {}).get("motion"):
            vf += effects.motion_filter(clip, width, height)
        elif a["kind"] == "image":
            vf += f",scale={width*2}:{height*2},zoompan=z='min(1+on*0.0003,1.04)':x='iw/2-iw/zoom/2':y='ih/2-ih/zoom/2':d=1:s={width}x{height}:fps=30"
        if clip.get("text"):
            vf += effects.title_filter(clip, textfile.name, width, height)
        vf += ",format=yuv420p,setpts=PTS-STARTPTS"
        inputs = ["-loop", "1", "-framerate", "30"] if a["kind"] == "image" else ["-ss", clip["in"]]
        checkpoint(out, [a["fingerprint"], clip, config, "scene-v4"], lambda: ff([
            *inputs, "-i", a["path"], "-t", clip["duration"], "-vf", vf, "-an",
            "-c:v", "libx264", "-preset", "fast", "-crf", "19", out], cwd=job))
        parts.append(out)
    # Compose pairwise so memory stays bounded on an 8 GB machine.
    composed = parts[0]
    accumulated = plan["clips"][0]["duration"]
    for i, part in enumerate(parts[1:], 1):
        clip = plan["clips"][i]
        out = job/f"join-{i:02d}.mp4"
        fade = clip.get("transition") == "fade"
        overlap = timing.overlap(clip, i)
        filt = (f"[0:v]settb=AVTB[a];[1:v]settb=AVTB[b];[a][b]xfade=transition=fade:duration={overlap}:offset={accumulated-overlap}[v]"
                if fade else "[0:v][1:v]concat=n=2:v=1:a=0[v]")
        checkpoint(out, [fingerprint(composed), fingerprint(part), filt], lambda: ff([
            "-i", composed, "-i", part, "-filter_complex", filt, "-map", "[v]", "-an",
            "-c:v", "libx264", "-preset", "fast", "-crf", "19", "-pix_fmt", "yuv420p", out]))
        composed = out
        accumulated += clip["duration"]-overlap
    shutil.copy2(composed, job/"content.mp4")
    outro = Path(plan["outro"])
    checkpoint(job/"outro-silent.mp4", [fingerprint(outro), config, "outro-v2"], lambda: ff([
        "-i", outro, "-vf", f"scale={width}:{height}:force_original_aspect_ratio=decrease,pad={width}:{height}:(ow-iw)/2:(oh-ih)/2,setsar=1,fps=30",
        "-an", "-c:v", "libx264", "-preset", "fast", "-crf", "18", "-pix_fmt", "yuv420p", job/"outro-silent.mp4"]))
    mix(plan, job, manifest)
    write(job/"prepared.json", {"plan_hash": digest(plan), "render": config, "content": str(job/"content.mp4"),
                               "outro": str(job/"outro-silent.mp4"), "audio": str(job/"master.m4a"),
                               "content_duration": total, "total_duration": plan["total_duration"],
                               "outro_duration": plan["outro_duration"]})


def mix(plan, job, manifest):
    lib = library()
    timings = read(job/"voice-timing.json")
    inputs, filters, labels = [], [], []
    total, full = plan["content_duration"], plan["total_duration"]
    def add(path, start, length, delay, gain, tag, speed=1):
        n = len(inputs)//2
        inputs.extend(["-i", str(path)])
        label = f"a{n}"
        fade_in, fade_out = (.25, .8) if tag == "music" else (.015, .07)
        filters.append(f"[{n}:a]atrim=start={start}:duration={length*speed},asetpts=PTS-STARTPTS,atempo={speed},"
                       f"aresample=48000,aformat=channel_layouts=stereo,volume={gain},"
                       f"afade=t=in:d={fade_in},afade=t=out:st={max(0,length-fade_out)}:d={fade_out},"
                       f"adelay={round(delay*1000)}:all=1,apad,atrim=duration={full}[{label}]")
        labels.append((label, tag))
    for t in timings:
        add(t["file"], 0, t["end"]-t["start"], t["start"], 1, "voice")
    # Never open source footage or the original outro as audio inputs, even if
    # legacy plans contain nonzero sound_gain. Only these three layers are allowed.
    add(asset_path(lib[plan["music"]["id"]]), plan["music"].get("in",0), full, 0, plan["music"].get("gain", .24), "music")
    for cue in plan["sfx"]:
        p = asset_path(lib[cue["id"]])
        add(p, 0, duration(p), cue["start"], cue.get("gain",.3), "bed")
    def group(tag, out):
        items = [f"[{label}]" for label,t in labels if t == tag]
        filters.append("".join(items)+f"amix=inputs={len(items)}:normalize=0[{out}]")
    group("voice", "vo")
    group("music", "music")
    group("bed", "bed")
    duck = plan.get("mix", {})
    filters += ["[vo]asplit=2[side][speech]",
                f"[music][side]sidechaincompress=threshold={duck.get('duck_threshold',.025)}:ratio={duck.get('duck_ratio',5)}:attack={duck.get('duck_attack',15)}:release={duck.get('duck_release',300)}[ducked]",
                "[speech][ducked][bed]amix=inputs=3:normalize=0,alimiter=limit=0.9:level=false[out]"]
    ff([*inputs, "-filter_complex", ";".join(filters), "-map", "[out]", "-t", full,
        "-c:a", "pcm_s16le", job/"mix.wav"])
    write(job/"mix-loudness.json", normalize(job/"mix.wav", job/"master.m4a"))
    used = [lib[plan["music"]["id"]], *[lib[s["id"]] for s in plan["sfx"]]]
    credits = list(dict.fromkeys(a.get("attribution", "") for a in used if a.get("attribution")))
    (job/"caption.txt").write_text(plan.get("caption", "Discover Wrydeco.")+"\n\n"+"\n".join(credits), encoding="utf-8")
    write(job/"audio-credits.json", used)


def export(job):
    p = read(job/"edit-plan.json")
    validate(p, job)
    ready = read(job/"prepared.json")
    if ready["plan_hash"] != digest(p):
        raise ValueError("Plan changed since prepare; rerun voice and prepare")
    # Bun executable, not the PowerShell shim, for shell-free subprocess invocation.
    bun = shutil.which("bun.exe") or shutil.which("bun")
    if not bun:
        raise RuntimeError("Bun is required")
    run([bun, "run", "scripts/reels-client.ts", str(job)], cwd=ROOT/"opencut-mcp", timeout=1900)
    # OpenCut remains the timeline renderer. Conform only stream metadata and audio
    # after its browser AAC encoder; preserve the exported video frames bit-for-bit.
    raw = job/"opencut-export.mp4"
    normalize(raw, job/"export-audio.m4a")
    conform_video(raw, job/"export-audio.m4a", job/"reel.mp4")
    write(job/"export-record.json", {"plan_hash": digest(p), "fingerprint": fingerprint(job/"reel.mp4")})
    history_path = ROOT/"work/reels-history.json"
    history = read(history_path) if history_path.exists() else []
    history = [x for x in history if x["job"] != str(job)]
    history.append({"job": str(job), "status": "exported", "hook": p["clips"][0]["asset_id"],
                    "music": p["music"]["id"], "shots": [c["asset_id"] for c in p["clips"]]})
    write(history_path, history)


def conform_video(raw, audio, target):
    video = next(s for s in probe(raw)["streams"] if s["codec_type"] == "video")
    video_duration = float(video["duration"])
    # Browser AAC may have a padded tail. Bound audio to actual video, preserving
    # every rendered video frame; AAC packet rounding is checked again by QA.
    ff(["-i", raw, "-i", audio, "-map", "0:v:0", "-map", "1:a:0",
        "-t", video_duration, "-c", "copy", "-bsf:v", "h264_metadata=sample_aspect_ratio=1/1",
        "-movflags", "+faststart", target])


def qa(job):
    plan_check = read(job/"edit-plan.json")
    validate(plan_check, job)
    if read(job/"prepared.json")["plan_hash"] != digest(plan_check):
        raise ValueError("Export does not match current plan; prepare and export again")
    final = job/"reel.mp4"
    record = read(job/"export-record.json")
    if record["plan_hash"] != digest(plan_check) or record["fingerprint"] != fingerprint(final):
        raise ValueError("Final export is stale or modified; rerun export")
    info = probe(final)
    streams = info["streams"]
    v = next(s for s in streams if s["codec_type"] == "video")
    a = next((s for s in streams if s["codec_type"] == "audio"), {})
    length = float(info["format"]["duration"])
    video_length = float(v.get("duration", length))
    decode = ff(["-v", "error", "-i", final, "-f", "null", "-"])
    loud = ff(["-i", final, "-af", "loudnorm=I=-16:TP=-1.5:print_format=json", "-vn", "-f", "null", "-"]).stderr
    stats = json.loads(loud[loud.rfind("{"):])
    scan = ff(["-i", final, "-vf", "blackdetect=d=0.15:pix_th=0.1", "-af", "silencedetect=n=-48dB:d=0.5", "-f", "null", "-"]).stderr
    p = read(job/"edit-plan.json")
    validate(p, job)
    config = render_config(p)
    checks = {
        "video_format": v["codec_name"] == "h264" and v["width"] == config["width"] and v["height"] == config["height"] and v["pix_fmt"] == "yuv420p",
        "frame_rate": v.get("avg_frame_rate") == "30/1",
        "square_pixels": v.get("sample_aspect_ratio") == "1:1",
        "audio_format": a.get("codec_name") == "aac" and a.get("channels") == 2,
        "duration": abs(length-p["total_duration"]) < .12,
        "av_end_sync": abs(float(a.get("duration", length))-video_length) <= .05,
        "decode": not decode.stderr.strip(),
        "loudness": -17 <= float(stats["input_i"]) <= -15,
        "true_peak": float(stats["input_tp"]) <= -1.5,
        "voice_before_outro": all(t["end"] <= p["content_duration"]-.4 for t in read(job/"voice-timing.json")),
    }
    times = sorted(set(min(t, max(0, video_length-1/FPS)) for t in ([round(i*length/12,3) for i in range(12)] +
                       [max(0,c["timeline_start"]-.08) for c in p["clips"]] +
                       [min(length-.08,c["timeline_start"]+.15) for c in p["clips"]] +
                       [c["timeline_start"]+(c.get("effects", {}).get("title_start", 0)+
                         c.get("effects", {}).get("title_end", c["duration"]))/2
                        for c in p["clips"] if c.get("text")] +
                       [p["content_duration"]+.15,length-.1])))
    images = []
    for i,t in enumerate(times):
        out = job/f"qa-frame-{i:02d}.jpg"
        ff(["-ss", t, "-i", final, "-frames:v", "1", "-vf", "scale=360:640", out])
        images.append(out)
    sheet(images, job/"storyboard.jpg", [f"{t:.2f}s" for t in times])
    shutil.copy2(images[0], job/"cover.jpg")
    for name,t in [("start",0),("middle",length/2-2),("end",length-4)]:
        ff(["-ss", t, "-i", final, "-t", "4", "-vn", "-c:a", "pcm_s16le", job/f"listen-{name}.wav"])
    warnings = [line.strip() for line in scan.splitlines() if "black_start:" in line or "silence_start:" in line]
    report = {"status": "needs_editorial_review" if all(checks.values()) else "failed", "plan_hash": digest(p),
              "checks": checks, "warnings": warnings, "loudness": stats, "metadata": info,
              "export_fingerprint": fingerprint(final), "visual_review": None, "listening_review": None}
    write(job/"qa-report.json", report)
    return report


def review(job, review_file):
    report = read(job/"qa-report.json")
    decision = read(review_file)
    if fingerprint(job/"reel.mp4") != report["export_fingerprint"]:
        raise ValueError("Export changed; rerun QA")
    if report.get("plan_hash"):
        current = read(job/"edit-plan.json")
        validate(current, job)
        if digest(current) != report["plan_hash"]:
            raise ValueError("Plan changed after QA; render and review the current version")
    for field in ("visual", "listening"):
        if decision.get(field) not in ("pass", "fail", "unavailable"):
            raise ValueError("Review must explicitly mark visual/listening pass, fail, or unavailable")
    if not decision.get("notes"):
        raise ValueError("Record specific review evidence and limitations")
    report["visual_review"], report["listening_review"] = decision["visual"], decision["listening"]
    report["review"] = decision
    report["status"] = "complete" if (all(report["checks"].values()) and decision["visual"] == "pass"
                            and decision["listening"] == "pass" and decision.get("warnings_resolved", False)) else "needs_review"
    write(job/"qa-report.json", report)
    if report["status"] == "complete":
        history_path = ROOT/"work/reels-history.json"
        history = read(history_path) if history_path.exists() else []
        p = read(job/"edit-plan.json")
        history = [x for x in history if x["job"] != str(job)]
        history.append({"job": str(job), "hook": p["clips"][0]["asset_id"], "music": p["music"]["id"],
                        "shots": [c["asset_id"] for c in p["clips"]]})
        write(history_path, history)
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=["analyze", "validate", "voice", "prepare", "export", "qa", "review"])
    parser.add_argument("--job", required=True)
    parser.add_argument("--source")
    parser.add_argument("--review-file")
    args = parser.parse_args()
    if args.command == "analyze" and not args.source:
        parser.error("analyze requires --source")
    if args.command == "review" and not args.review_file:
        parser.error("review requires --review-file")
    job = Path(args.job).resolve()
    if not job.is_relative_to((ROOT/"output").resolve()):
        raise ValueError("Jobs must be under workspace output/")
    job.mkdir(parents=True, exist_ok=True)
    with job_lock():
        if args.command == "analyze":
            print(analyze(args.source, job))
            return
        p = read(job/"edit-plan.json")
        manifest = validate(p, job)
        if args.command == "validate":
            print(json.dumps({"valid": True, "duration": p["total_duration"]}))
        elif args.command == "voice":
            voice(p, job)
        elif args.command == "prepare":
            # Revalidate that the generated voice belongs to the current narration.
            for i,line in enumerate(p["narration"]):
                spoken = line["text"].replace("Wrydeco", p.get("brand_pronunciation", "Rye deco"))
                if read(job/f"voice-{i}.wav.checkpoint.json")["key"] != digest([spoken,"af_heart","kokoro-onnx-0.4.9"]):
                    raise ValueError("Narration changed; rerun voice")
            prepare(p, job, manifest)
        elif args.command == "export":
            export(job)
        elif args.command == "qa":
            print(json.dumps(qa(job), ensure_ascii=False))
        elif args.command == "review":
            print(json.dumps(review(job, args.review_file), ensure_ascii=False))


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        sys.exit(1)
