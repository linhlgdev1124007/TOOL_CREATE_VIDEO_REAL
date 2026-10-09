"""Bounded Flow cutaway acquisition; submissions are never automatically retried."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import time
import urllib.request
import urllib.error
from urllib.parse import urlparse
import uuid

import pipeline as p

PIN = "bc051f2308db050b0d987b696c843664d483b515"
BASE = "http://127.0.0.1:8100"


class Budget:
    def __init__(self, path):
        self.path = Path(path)

    def reserve(self, description):
        self.path.parent.mkdir(parents=True, exist_ok=True)
        lock = self.path.with_suffix(".lock")
        fd = os.open(lock, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
        try:
            data = p.read(self.path) if self.path.exists() else {"limit": 6, "attempts": []}
            if len(data["attempts"]) >= 6:
                raise ValueError("Flow generation limit reached (6); no request sent")
            ident = str(uuid.uuid4())
            data["attempts"].append({"id": ident, "reserved_at": time.time(), **description})
            p.write(self.path, data)
            return ident
        finally:
            os.close(fd)
            lock.unlink()


def api(path, payload=None, timeout=15):
    req = urllib.request.Request(BASE+path, data=None if payload is None else json.dumps(payload).encode(),
                                 headers={"Content-Type": "application/json", "X-Flowkit-Caller": "wrydeco-reels"})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as response:
            return json.load(response)
    except urllib.error.HTTPError as exc:
        body = exc.read(8192).decode("utf-8", errors="replace")
        if "UNUSUAL_ACTIVITY" in body or "unusual activity" in body.lower():
            raise RuntimeError("Google Flow unusual-activity block; resolve in the normal Flow UI before another submission") from exc
        raise RuntimeError(f"Flowkit HTTP {exc.code}; inspect the local server log (no automatic retry)") from exc


def health(project_id, job=None):
    uuid.UUID(project_id)
    result = {"ready": False, "project_id": project_id, "pin": PIN}
    try:
        result["health"] = api("/health")
        result["flow"] = api("/api/flow/status")
        result["guard"] = api("/wrydeco/guard")
        result["ready"] = bool(result["health"].get("extension_connected") and
                               result["flow"].get("connected") and
                               result["guard"].get("project_id") == project_id and
                               result["guard"].get("pin") == PIN)
        if job is not None:
            result["ready"] = result["ready"] and result["guard"].get("job") == str(Path(job).resolve())
    except Exception as exc:
        result["error"] = str(exc)
    return result


def submit(job, item, project_id):
    if not health(project_id, job)["ready"]:
        raise ValueError("Flow bridge/project/guard not ready; no generation submitted")
    if not re.fullmatch(r"[a-z0-9-]{1,60}", item["id"]):
        raise ValueError("Invalid cutaway ID")
    if item.get("purpose") != "atmosphere" or not item.get("no_product_or_people"):
        raise ValueError("Only atmosphere cutaways without products or people are supported")
    folder = Path(job)/"flow"
    folder.mkdir(exist_ok=True)
    record = folder/(item["id"]+".json")
    if record.exists():
        raise ValueError("Cutaway already submitted/reserved; poll or reconcile it, never resubmit the same ID")
    payload = {"project_id": project_id, "prompt": item["prompt"], "duration_s": 4,
               "resolution": "720p", "aspect_ratio": "VIDEO_ASPECT_RATIO_PORTRAIT"}
    entry = {"id": item["id"], "origin": "google_flow", "purpose": "atmosphere",
             "payload": payload, "status": "submission_unknown", "pin": PIN,
             "created_at": time.time()}
    p.write(record, entry)  # Durable before any request. Unknown submission is never retried.
    try:
        entry["receipt"] = api("/api/flow/generate-video-omni-text", payload, timeout=180)
        entry["status"] = "submitted"
    except Exception as exc:
        entry["error"] = str(exc)
    p.write(record, entry)
    return entry


def poll(job, ident):
    if not re.fullmatch(r"[a-z0-9-]{1,60}", ident):
        raise ValueError("Invalid cutaway ID")
    record = Path(job)/"flow"/(ident+".json")
    entry = p.read(record)
    if entry["status"] == "downloaded":
        return entry
    receipt = entry.get("receipt", {})
    descriptor = receipt.get("flowkitPolling", {})
    if not descriptor.get("workflows"):
        raise ValueError("No receipt; inspect the Flow project and server budget before any new generation")
    result = api("/api/flow/check-status", {"workflows": descriptor["workflows"],
                 "project_id": entry["payload"]["project_id"]}, timeout=90)
    entry["last_poll"] = time.time()
    # Signed download URLs remain transient; do not persist them in provenance.
    if result.get("done"):
        item = result["workflows"][0]
        url = item.get("media", {}).get("url", "")
        parsed = urlparse(url)
        if parsed.scheme != "https" or parsed.hostname != "flow-content.google":
            raise ValueError("Expected official Flow media URL")
        from audio_download import fetch
        target = record.with_suffix(".mp4")
        fetch(url, target, limit=150*1024*1024)
        info = p.probe(target)
        if not any(s["codec_type"] == "video" for s in info["streams"]):
            raise ValueError("Flow result has no video stream")
        if p.ff(["-v", "error", "-i", target, "-f", "null", "-"]).stderr.strip():
            raise ValueError("Flow result has decode errors")
        entry.update(status="downloaded", file=str(target), media_id=item["primary_media_id"],
                     sha256=hashlib.sha256(target.read_bytes()).hexdigest(), visual_review="pending")
    p.write(record, entry)
    return entry


def import_reviewed(job, ident):
    if not re.fullmatch(r"[a-z0-9-]{1,60}", ident):
        raise ValueError("Invalid cutaway ID")
    folder = Path(job)/"flow"
    entry = p.read(folder/(ident+".json"))
    decision = p.read(folder/(ident+"-review.json"))
    if (entry.get("status") != "downloaded" or decision.get("visual") != "pass"
            or decision.get("no_product_or_people") is not True or not decision.get("notes")):
        raise ValueError("Downloaded cutaway needs explicit visual and no-product/no-people evidence")
    target = Path(entry["file"]).resolve()
    if not target.is_relative_to(folder.resolve()) or hashlib.sha256(target.read_bytes()).hexdigest() != entry["sha256"]:
        raise ValueError("Flow download changed or is outside the job")
    scan = p.analyze(folder, Path(job)/"flow-analysis")
    asset = next(a for a in p.read(scan)["assets"] if Path(a["path"]).resolve() == target)
    if asset["status"] != "ok":
        raise ValueError("Flow media analysis failed")
    asset.update(origin="google_flow", ai_review=decision, provenance=str(folder/(ident+".json")))
    manifest = p.read(Path(job)/"media-manifest.json")
    manifest["assets"] = [a for a in manifest["assets"] if a["id"] != asset["id"]]+[asset]
    p.write(Path(job)/"media-manifest.json", manifest)
    return {"imported": asset["id"], "origin": "google_flow", "review": decision}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=["health", "submit", "poll", "import"])
    parser.add_argument("--job", required=True)
    parser.add_argument("--project-id", required=True)
    parser.add_argument("--id")
    args = parser.parse_args()
    job = Path(args.job).resolve()
    if not job.is_relative_to(p.ROOT/"output"):
        parser.error("Job must be inside output/")
    job.mkdir(parents=True, exist_ok=True)
    if args.command == "health":
        result = health(args.project_id, job)
        p.write(job/"flow-health.json", result)
    else:
        with p.job_lock():
            if args.command == "submit":
                item = next(x for x in p.read(job/"flow-requests.json") if x["id"] == args.id)
                result = submit(job, item, args.project_id)
            elif args.command == "poll":
                result = poll(job, args.id)
            else:
                result = import_reviewed(job, args.id)
    print(json.dumps(result, ensure_ascii=False))


if __name__ == "__main__":
    main()
