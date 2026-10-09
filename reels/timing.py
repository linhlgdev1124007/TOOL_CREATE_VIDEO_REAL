"""Shared output/source clock for rendering, range inspection and contact cues."""
import math


def segments(clip):
    fx = clip.get("effects", {})
    return fx.get("speed_segments") or [{"duration": clip["duration"],
                                         "from": fx.get("speed", 1), "to": fx.get("speed", 1)}]


def source_at(clip, output_time):
    remaining = max(0, min(output_time, clip["duration"]))
    value = 0.0
    for seg in segments(clip):
        dt = min(remaining, seg["duration"])
        slope = (seg["to"]-seg["from"])/seg["duration"]
        value += seg["from"]*dt + slope*dt*dt/2
        remaining -= dt
        if remaining <= 1e-9:
            break
    return value


def output_at(clip, source_time):
    if not 0 <= source_time <= source_at(clip, clip["duration"])+1e-6:
        raise ValueError("Action cue is outside selected source range")
    elapsed = 0.0
    for seg in segments(clip):
        span = seg["duration"]*(seg["from"]+seg["to"])/2
        if source_time <= span+1e-9:
            slope = (seg["to"]-seg["from"])/seg["duration"]
            # Stable quadratic inverse, including deceleration.
            dt = 2*source_time/(seg["from"]+math.sqrt(max(0, seg["from"]**2+2*slope*source_time)))
            return elapsed+dt
        source_time -= span
        elapsed += seg["duration"]
    return clip["duration"]


def setpts(clip):
    source_start = output_start = 0.0
    expr = "0"
    pieces = []
    for seg in segments(clip):
        a, b, dt = seg["from"], seg["to"], seg["duration"]
        span = dt*(a+b)/2
        x = f"max(0,(PTS-STARTPTS)*TB-{source_start:.9f})"
        local = f"({x})/{a}" if abs(a-b) < 1e-9 else f"2*({x})/({a}+sqrt(max(0,{a*a}+{2*(b-a)/dt}*({x}))))"
        pieces.append((source_start+span, f"({output_start:.9f}+{local})/TB"))
        source_start += span
        output_start += dt
    expr = pieces[-1][1]
    for end, value in reversed(pieces[:-1]):
        expr = f"if(lt((PTS-STARTPTS)*TB,{end:.9f}),{value},{expr})"
    return f"setpts='{expr}'"


def overlap(clip, index):
    return clip.get("transition_duration", .4) if index and clip.get("transition") == "fade" else 0


def schedule(clips):
    total = 0.0
    for index, clip in enumerate(clips):
        clip["timeline_start"] = round(total-overlap(clip, index), 6)
        total = clip["timeline_start"]+clip["duration"]
    return round(total, 6)


def cue_time(cue, clips):
    if "shot" not in cue:
        return cue["start"]
    clip = clips[cue["shot"]]
    return clip["timeline_start"]+output_at(clip, cue["source_time"]-clip["in"])
