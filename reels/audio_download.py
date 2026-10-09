"""Download verified free audio requests into the catalog; never scrape social audio."""
import argparse
from datetime import datetime, timezone
import hashlib
import ipaddress
import math
import os
from pathlib import Path
import re
import socket
import subprocess
import tempfile
import time
from urllib.parse import urlparse, urljoin
import urllib.request
import pipeline as p
from audio_rights import validate_rights

MAX_BYTES = 50 * 1024 * 1024


def public_url(url):
    u = urlparse(url)
    if u.scheme != "https" or not u.hostname or u.username or u.password or u.port not in (None, 443):
        raise ValueError("Only public HTTPS URLs without credentials are supported")
    addresses = socket.getaddrinfo(u.hostname, 443, type=socket.SOCK_STREAM)
    if not addresses or any(not ipaddress.ip_address(a[4][0]).is_global for a in addresses):
        raise ValueError("Private/local network downloads are forbidden")
    return url


class SafeRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        public_url(newurl)
        return super().redirect_request(req, fp, code, msg, headers, newurl)


def fetch(url, destination, limit=MAX_BYTES):
    if os.name == "nt":
        # Windows curl uses the OS certificate store. Never disable TLS checks.
        # Follow redirects ourselves so every new destination is checked.
        deadline = time.monotonic()+120
        for _ in range(6):
            public_url(url)
            remaining = max(1, int(deadline-time.monotonic()))
            result = subprocess.run(["curl.exe", "--silent", "--show-error", "--fail",
                                     "--proto", "=https", "--max-time", str(remaining),
                                     "--max-filesize", str(limit), "--output", str(destination),
                                     "--write-out", "%{http_code}\n%{redirect_url}", url],
                                    capture_output=True, text=True, timeout=remaining+2, check=True)
            status, _, redirect = result.stdout.partition("\n")
            if status.startswith("3") and redirect.strip():
                url = urljoin(url, redirect.strip())
                continue
            if not status.startswith("2") or not 0 < Path(destination).stat().st_size <= limit:
                raise ValueError("Invalid download response or size")
            return
        raise ValueError("Too many redirects")
    public_url(url)
    opener = urllib.request.build_opener(SafeRedirect())
    start, size = time.monotonic(), 0
    with opener.open(urllib.request.Request(url, headers={"User-Agent": "Wrydeco-Reels/1.0"}), timeout=30) as response:
        if int(response.headers.get("Content-Length", "0")) > limit:
            raise ValueError("Download exceeds size limit")
        with Path(destination).open("wb") as out:
            while chunk := response.read(64*1024):
                size += len(chunk)
                if size > limit or time.monotonic()-start > 120:
                    raise ValueError("Download exceeds size/time limit")
                out.write(chunk)
    if not size:
        raise ValueError("Empty download")


def validate_request(item):
    if not re.fullmatch(r"[a-z0-9][a-z0-9-]{0,79}", item.get("id", "")):
        raise ValueError("Invalid audio ID")
    if item.get("kind") not in ("music", "sfx"):
        raise ValueError("Only music/SFX are supported")
    validate_rights(item)
    for key in ("title", "author", "source_url", "download_url", "license_url", "license_evidence", "verified_on"):
        if not isinstance(item.get(key), str) or not item[key].strip():
            raise ValueError(f"Missing {key}")
    checked = datetime.strptime(item["verified_on"], "%Y-%m-%d").date()
    age = (datetime.now(timezone.utc).date()-checked).days
    if not 0 <= age <= 7:
        raise ValueError("Recheck the exact recording's license within 7 days")
    if item["license"] == "CC-BY-4.0" and not item.get("attribution"):
        raise ValueError("CC-BY requires attribution")
    tags = item.get("tags", [])
    if not isinstance(tags, list) or not all(isinstance(t, str) for t in tags):
        raise ValueError("tags must be strings")
    if item["kind"] == "music" and not set(tags).intersection({"chill", "calm", "ambient", "warm", "mellow", "relaxed", "gentle"}):
        raise ValueError("Music must fit the chill brief")


def acquire(item):
    validate_request(item)
    catalog_path = p.LIBRARY/"catalog.json"
    catalog = p.read(catalog_path) if catalog_path.exists() else {"version": 1, "assets": []}
    existing = next((a for a in catalog["assets"] if a["id"] == item["id"]), None)
    if existing:
        if existing.get("download_url") != item["download_url"] or existing.get("license") != item["license"]:
            raise ValueError("ID collision: existing asset preserved; choose another ID")
        p.asset_path(existing)
        return {"id": item["id"], "status": "cached"}
    # Validate source/provenance URLs too; they must never refer to local services.
    for key in ("source_url", "license_url", "download_url"):
        public_url(item[key])
    target = p.LIBRARY/"downloaded"/item["id"]
    target.parent.mkdir(parents=True, exist_ok=True)
    if target.exists():
        raise ValueError("Asset directory already exists; preserved for inspection")
    with tempfile.TemporaryDirectory(prefix="audio-", dir=target.parent) as tmp:
        work = Path(tmp)
        raw = work/"audio.bin"
        fetch(item["download_url"], raw)
        info = p.probe(raw)
        if not any(s["codec_type"] == "audio" for s in info["streams"]) or any(s["codec_type"] == "video" for s in info["streams"]):
            raise ValueError("Expected audio-only file, not HTML, archive or video")
        length = float(info["format"]["duration"])
        if not math.isfinite(length) or not .05 <= length <= 1800:
            raise ValueError("Audio duration outside supported range")
        p.ff(["-i", raw, "-map", "0:a:0", "-t", length, "-f", "null", "-"])
        fetch(item["license_url"], work/"license-snapshot.bin", limit=2*1024*1024)
        fetch(item["source_url"], work/"source-snapshot.bin", limit=2*1024*1024)
        asset = {**item, "file": f"downloaded/{item['id']}/audio.bin", "duration": length,
                 "sha256": hashlib.sha256(raw.read_bytes()).hexdigest(),
                 "downloaded_at": datetime.now(timezone.utc).isoformat(), "managed_download": True}
        p.write(work/"provenance.json", asset)
        work.rename(target)
    catalog["assets"].append(asset)
    p.write(catalog_path, catalog)
    return {"id": item["id"], "status": "downloaded", "duration": length}


def download_requests(job):
    requests = p.read(job/"audio-downloads.json")
    if not isinstance(requests, list) or len(requests) > 5:
        raise ValueError("Download request must be a list of at most 5 assets")
    results = []
    with p.job_lock():
        for item in requests:
            try:
                results.append(acquire(item))
            except Exception as exc:
                results.append({"id": item.get("id") if isinstance(item, dict) else None, "status": "failed", "error": str(exc)})
        p.write(job/"audio-download-report.json", results)
    return results


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--job", required=True)
    args = parser.parse_args()
    job = Path(args.job).resolve()
    if not job.is_relative_to((p.ROOT/"output").resolve()):
        parser.error("Job must be under output/")
    results = download_requests(job)
    print(results)
    raise SystemExit(1 if any(r["status"] == "failed" for r in results) else 0)
