"""Evidence for human editorial review; never a prediction of audience retention."""
import argparse
from pathlib import Path
from PIL import Image, ImageDraw
import pipeline as p
import timing


def audit(plan, manifest):
    shots = plan["clips"]
    still = sum(c["duration"] for c in shots if manifest[c["asset_id"]]["kind"] == "image")
    run = longest = 0
    hashes, repeated = {}, []
    for i, c in enumerate(shots):
        a = manifest[c["asset_id"]]
        if a["kind"] != "image":
            run = 0
            continue
        run += c["duration"] - timing.overlap(c, i)
        longest = max(longest, run)
        with Image.open(a["path"]) as im:
            pixels = list(im.convert("L").resize((9, 8)).getdata())
        bits = [pixels[y*9+x] > pixels[y*9+x+1] for y in range(8) for x in range(8)]
        matches = [j for j, prev in hashes.items() if sum(x != y for x, y in zip(bits, prev)) <= 4]
        if matches:
            repeated.append({"shot": i, "similar_to": matches, "note": "Perceptual similarity candidate; verify visually"})
        hashes[i] = bits
    warnings = []
    if manifest[shots[0]["asset_id"]]["kind"] == "image":
        warnings.append("Static opening: check whether product and hook earn attention immediately")
    if longest > 4:
        warnings.append("More than 4 seconds of consecutive stills: inspect for a stalled ending")
    if repeated:
        warnings.append("Similar photographs recur; inspect whether repetition adds information")
    return {"opening_kind": manifest[shots[0]["asset_id"]]["kind"],
            "still_seconds_before_overlap": round(still, 2), "longest_still_run": round(longest, 2),
            "similar_photos": repeated, "warnings": warnings,
            "limitation": "Editorial heuristics, not measured engagement or guaranteed retention"}


def inspect(plan, manifest, job):
    """Sample each chosen range every half second, including its final frame."""
    frames = job/"selected-frames"
    frames.mkdir(exist_ok=True)
    for i, c in enumerate(plan["clips"]):
        a = manifest[c["asset_id"]]
        times = [0] if a["kind"] == "image" else sorted(set(
            [min(n*.5, c["duration"]-1/30) for n in range(int(c["duration"]*2)+1)] + [c["duration"]-1/30]))
        sheet = Image.new("RGB", (240*4, 270*((len(times)+3)//4)), "#101614")
        draw = ImageDraw.Draw(sheet)
        for j, t in enumerate(times):
            out = frames/f"{i:02d}-{j:02d}.jpg"
            source_t = c["in"]+timing.source_at(c, t)
            seek = [] if a["kind"] == "image" else ["-ss", source_t]
            p.ff([*seek, "-i", a["path"], "-frames:v", 1, "-vf", "scale=220:240:force_original_aspect_ratio=decrease", out])
            with Image.open(out) as im:
                sheet.paste(im, ((j%4)*240, (j//4)*270))
            draw.text(((j%4)*240, (j//4)*270+245), f"shot {i+1} source {source_t:.2f}s", fill="white")
        sheet.save(job/f"selected-shot-{i:02d}.jpg")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--job", required=True)
    parser.add_argument("--inspect", action="store_true")
    args = parser.parse_args()
    job = Path(args.job).resolve()
    if not job.is_relative_to((p.ROOT/"output").resolve()):
        parser.error("Job must be under output/")
    with p.job_lock():
        plan = p.read(job/"edit-plan.json")
        manifest = p.validate(plan, job)
        p.write(job/"editorial-audit.json", audit(plan, manifest))
        if args.inspect:
            inspect(plan, manifest, job)
