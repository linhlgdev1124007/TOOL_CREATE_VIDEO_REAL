"""Measured audio evidence. This cannot certify pronunciation or musical taste."""
import argparse
from pathlib import Path
import subprocess
import numpy as np
import pipeline as p


def samples(path):
    result = subprocess.run(["ffmpeg", "-v", "error", "-i", str(path), "-vn", "-ar", "24000",
                             "-ac", "2", "-f", "f32le", "-"], capture_output=True, check=True)
    return np.frombuffer(result.stdout, dtype="<f4").reshape(-1,2)


def db(value):
    return round(float(20*np.log10(max(1e-9, value))), 2)


def audit(job):
    plan = p.read(job/"edit-plan.json")
    p.validate(plan, job)
    final = samples(job/"reel.mp4")
    report = {"listening": "unavailable", "limitation": "Signal/timing measurements only, not a listening or pronunciation review.",
              "file_fingerprint": p.fingerprint(job/"reel.mp4"), "voice": [], "mix_windows": []}
    for index, t in enumerate(p.read(job/"voice-timing.json")):
        voice = samples(t["file"])
        energy = np.max(np.abs(voice), axis=1)
        active = np.flatnonzero(energy > .003)
        report["voice"].append({"index": index, "start": t["start"], "end": t["end"],
            "rms_dbfs": db(np.sqrt(np.mean(voice**2))), "sample_peak_dbfs": db(np.max(np.abs(voice))),
            "leading_silence_s": round(float(active[0]/24000),3) if len(active) else None,
            "trailing_silence_s": round(float((len(voice)-1-active[-1])/24000),3) if len(active) else None,
            "gap_before_outro_s": round(plan["content_duration"]-t["end"],3)})
    for start in np.arange(0,len(final)/24000,.5):
        chunk = final[int(start*24000):int((start+.5)*24000)]
        report["mix_windows"].append({"start": round(float(start),3), "rms_dbfs": db(np.sqrt(np.mean(chunk**2))),
                                       "sample_peak_dbfs": db(np.max(np.abs(chunk)))})
    report["sfx_schedule"] = [{"id":c["id"], "start":c["start"], "gain":c.get("gain",.3), "reason":c["reason"]} for c in plan["sfx"]]
    report["nonzero_stereo"] = bool(np.all(np.max(np.abs(final),axis=0) > .01))
    report["no_digital_clipping"] = bool(np.max(np.abs(final)) < 1)
    report["minimum_voice_gap_before_outro_s"] = min(t["gap_before_outro_s"] for t in report["voice"])
    p.write(job/"audio-signal-review.json", report)
    return report


if __name__ == "__main__":
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--job",required=True)
    job=Path(parser.parse_args().job).resolve()
    if not job.is_relative_to(p.ROOT/"output"):
        parser.error("Job must be inside output")
    with p.job_lock():
        result=audit(job)
    print({k:result[k] for k in ("nonzero_stereo","no_digital_clipping","minimum_voice_gap_before_outro_s","listening")})
