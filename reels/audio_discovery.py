"""Rank licensed local audio against dated trend evidence gathered by the skill.

This is not a scraper and never treats a chart listing as a music license.
"""
import argparse
from datetime import date
from urllib.parse import urlparse
import pipeline as p
from audio_rights import validate_rights


def rank(catalog, evidence, history, region, today=None):
    today = today or date.today()
    signals, rejected = [], []
    for item in evidence:
        try:
            age = (today-date.fromisoformat(item["observed_on"])).days
            valid = (0 <= age <= 7 and item["region"] == region
                     and item["platform"] in ("facebook", "instagram", "tiktok")
                     and urlparse(item["url"]).scheme == "https"
                     and bool(item["evidence"].strip()) and bool(item["title"].strip())
                     and item.get("signal") in ("rising", "popular"))
        except (KeyError, ValueError, TypeError):
            valid = False
        if valid:
            signals.append(item)
        else:
            rejected.append(item.get("title", "invalid observation"))
    recent = [h.get("music") for h in history[-5:]]
    output = []
    for asset in catalog:
        if asset.get("kind") not in ("music", "sfx"):
            continue
        # Existing catalog provenance plus real-file hash checks, never trend URLs.
        try:
            validate_rights(asset)
            p.asset_path(asset)
        except (ValueError, FileNotFoundError, KeyError):
            continue
        tags = set(asset.get("tags", []))
        if asset["kind"] == "music" and not tags.intersection({"chill", "calm", "ambient", "warm", "relaxed", "gentle", "mellow"}):
            continue
        matches = [s for s in signals if s.get("catalog_id") == asset["id"]]
        related = [s for s in signals if tags.intersection(s.get("tags", []))]
        repeated = asset["id"] in recent
        score = 10 + (8 if matches else 3 if related else 0) - (6 if repeated else 0)
        output.append({"id": asset["id"], "kind": asset["kind"], "score": score,
                       "trend_status": "observed_track" if matches else "style_match_only" if related else "licensed_fallback",
                       "recently_used": repeated, "evidence": matches or related,
                       "listening_required": True})
    return {"region": region, "checked_on": today.isoformat(), "fresh_signals": len(signals),
            "rejected_observations": rejected,
            "status": "trend_informed" if signals else "no_verified_trend_fallback",
            "candidates": sorted(output, key=lambda x: (-x["score"], x["id"])),
            "unlicensed_trend_references": [s for s in signals if not any(c["id"] == s.get("catalog_id") for c in output)],
            "notice": "Scores are selection heuristics, not popularity measurements. TikTok evidence is not a Facebook trend or license."}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--job", required=True)
    parser.add_argument("--region", default="US")
    parser.add_argument("--download", action="store_true", help="Acquire verified audio-downloads.json before ranking")
    args = parser.parse_args()
    job = p.Path(args.job).resolve()
    if not job.is_relative_to((p.ROOT/"output").resolve()):
        parser.error("Job must be under output/")
    observed = job/"audio-trends.json"
    if args.download:
        from audio_download import download_requests
        results = download_requests(job)
        print({"downloads": results})
    history = p.ROOT/"work/reels-history.json"
    result = rank(p.read(p.LIBRARY/"catalog.json")["assets"],
                  p.read(observed) if observed.exists() else [],
                  p.read(history) if history.exists() else [], args.region)
    p.write(job/"audio-shortlist.json", result)
    print(result["status"])
