"""Bounded, deterministic editorial effects. No arbitrary filter expressions."""
import math
import timing


def number(value, low, high, name):
    if isinstance(value, bool) or not isinstance(value, (float, int)) or not math.isfinite(value) or not low <= value <= high:
        raise ValueError(f"{name} must be between {low} and {high}")


def validate(clip, asset):
    fx = clip.get("effects", {})
    if not isinstance(fx, dict) or set(fx)-{"speed", "push_in", "title_start", "title_end", "title_position", "title_size", "reason", "speed_segments", "motion", "title_style"}:
        raise ValueError("Unknown effects; tracking and masking are not implemented")
    if fx and not fx.get("reason"):
        raise ValueError("Effects require an editorial reason")
    number(fx.get("speed", 1), .5, 2, "speed")
    number(fx.get("push_in", 1), 1, 1.12, "push_in")
    if "speed_segments" in fx:
        if "speed" in fx or asset["kind"] == "image":
            raise ValueError("Speed segments require video and cannot be combined with speed")
        segs = fx["speed_segments"]
        if not isinstance(segs, list) or not 1 <= len(segs) <= 8:
            raise ValueError("Use 1–8 speed segments")
        previous = None
        for seg in segs:
            number(seg["duration"], 1/30, clip["duration"], "segment duration")
            for key in ("from", "to"):
                number(seg[key], .5, 2, "segment speed")
            if previous is not None and abs(previous-seg["from"]) > 1e-6:
                raise ValueError("Speed ramp must be continuous")
            previous = seg["to"]
        if abs(sum(s["duration"] for s in segs)-clip["duration"]) > 1e-6:
            raise ValueError("Speed segment durations must equal shot duration")
    minimum_speed = min(min(s["from"], s["to"]) for s in timing.segments(clip))
    if minimum_speed < 1 and asset["kind"] == "video":
        n, _, d = asset.get("fps", "0/1").partition("/")
        if float(n)/float(d or 1)*minimum_speed < 29.9:
            raise ValueError("Slow motion requires enough source frames for 30fps")
    motion = fx.get("motion")
    if motion is not None:
        if not isinstance(motion, list) or not 2 <= len(motion) <= 6 or "push_in" in fx:
            raise ValueError("Motion requires 2–6 keyframes and cannot combine with push_in")
        last = -1
        for key in motion:
            number(key["time"], 0, clip["duration"], "motion time")
            if key["time"] <= last:
                raise ValueError("Motion keyframes must be ordered")
            last = key["time"]
            number(key["zoom"], 1, 1.12, "motion zoom")
            number(key["x"], 0, 1, "motion x")
            number(key["y"], 0, 1, "motion y")
        if motion[0]["time"] != 0 or motion[-1]["time"] != clip["duration"]:
            raise ValueError("Motion keyframes must cover whole shot")
    if fx.get("title_style", "classic") not in ("classic", "luxury"):
        raise ValueError("Unknown title style")
    if asset["kind"] == "image" and fx.get("speed", 1) != 1:
        raise ValueError("Cannot retime a still image")
    if fx.get("speed", 1) < 1:
        n, _, d = asset.get("fps", "0/1").partition("/")
        fps = float(n)/float(d or 1)
        if fps*fx["speed"] < 29.9:
            raise ValueError("Slow motion requires enough source frames for 30fps; no invented frames")
    if fx.get("title_position", "top") not in ("top", "bottom"):
        raise ValueError("title_position must be top or bottom")
    number(fx.get("title_size", 30), 28, 40, "title_size")
    start, end = fx.get("title_start", 0), fx.get("title_end", clip["duration"])
    number(start, 0, clip["duration"], "title_start")
    number(end, start, clip["duration"], "title_end")
    if clip.get("text") and end-start < .7:
        raise ValueError("Title exposure must be at least 0.7 seconds")


def source_duration(clip):
    return timing.source_at(clip, clip["duration"])


def motion_filter(clip, width=720, height=1280):
    keys = clip.get("effects", {}).get("motion")
    if keys:
        def interpolate(field):
            result = str(keys[-1][field])
            for a, b in reversed(list(zip(keys, keys[1:]))):
                u = f"clip((on/30-{a['time']})/{b['time']-a['time']},0,1)"
                val = f"({a[field]}+({b[field]-a[field]})*({u})*({u})*(3-2*({u})))"
                result = f"if(lt(on/30,{b['time']}),{val},{result})"
            return result
        return (f",scale={width*2}:{height*2},zoompan=z='{interpolate('zoom')}':"
                f"x='(iw-iw/zoom)*({interpolate('x')})':y='(ih-ih/zoom)*({interpolate('y')})':"
                f"d=1:s={width}x{height}:fps=30")
    zoom = clip.get("effects", {}).get("push_in", 1)
    if zoom == 1:
        return ""
    frames = max(1, round(clip["duration"]*30)-1)
    # Smoothstep starts and ends with zero velocity, unlike a linear digital zoom.
    u = f"min(on/{frames},1)"
    return (f",scale={width*2}:{height*2},zoompan=z='1+{zoom-1}*({u})*({u})*(3-2*({u}))':"
            f"x='iw/2-iw/zoom/2':y='ih/2-ih/zoom/2':d=1:s={width}x{height}:fps=30")


def title_filter(clip, textfile, width=720, height=1280):
    fx = clip.get("effects", {})
    scale = width/720
    size = round(fx.get("title_size", 30)*scale)
    lines = len(clip["text"].splitlines())
    box_height = lines*size+(lines-1)*round(12*scale)+round(32*scale)
    y = round(134*scale) if fx.get("title_position", "top") == "top" else round(1020*scale)-box_height
    start, end = fx.get("title_start", 0), fx.get("title_end", clip["duration"])
    enable = f"between(t,{start},{end})"
    alpha = f"min(1,min((t-{start})/0.15,({end}-t)/0.15))"
    if fx.get("title_style") == "luxury":
        return (f",drawtext=fontfile='C\\:/Windows/Fonts/arial.ttf':textfile={textfile}:"
                f"expansion=none:fontcolor=0xF5F0E6:fontsize={size}:line_spacing={round(12*scale)}:"
                f"shadowcolor=black@0.75:shadowx=0:shadowy={round(2*scale)}:"
                f"borderw={max(1,round(scale))}:bordercolor=black@0.25:"
                f"x=(w-text_w)/2:y={y+round(16*scale)}:alpha='{alpha}':enable='{enable}'")
    return (f",drawbox=x={round(42*scale)}:y={y}:w={round(636*scale)}:h={box_height}:color=black@0.42:t=fill:enable='{enable}',"
            f"drawtext=fontfile='C\\:/Windows/Fonts/arialbd.ttf':textfile={textfile}:"
            f"expansion=none:fontcolor=white:fontsize={size}:line_spacing={round(12*scale)}:"
            f"x=(w-text_w)/2:y={y+round(16*scale)}:alpha='{alpha}':enable='{enable}'")
