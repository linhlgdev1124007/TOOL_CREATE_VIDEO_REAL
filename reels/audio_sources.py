"""Seven-source search routing plus live public Mixkit SFX search/resolution.

Other providers use the skill's web tools or an authorized account. No fabricated
search results, login bypass, undocumented API keys or preview-as-download URLs.
"""
import argparse
from datetime import datetime, timezone
from html import unescape
from html.parser import HTMLParser
from pathlib import Path
import re
import tempfile
from urllib.parse import quote, urljoin
import pipeline as p
from audio_download import fetch, acquire
from audio_rights import host_is

PROVIDERS = {
    "mixkit": {"domain": "mixkit.co", "kinds": ["music", "sfx"], "mode": "live_sfx_or_agent_web", "license": "https://mixkit.co/license/"},
    "pixabay": {"domain": "pixabay.com", "kinds": ["music", "sfx"], "mode": "agent_web", "license": "https://pixabay.com/service/license-summary/"},
    "chosic": {"domain": "chosic.com", "kinds": ["music"], "mode": "agent_web", "license": "https://www.chosic.com/free-music-policy/"},
    "freesound": {"domain": "freesound.org", "kinds": ["sfx"], "mode": "agent_web_or_authorized_account", "license": "https://freesound.org/help/faq/"},
    "uppbeat": {"domain": "uppbeat.io", "kinds": ["music", "sfx"], "mode": "account_and_plan_review", "license": "https://uppbeat.io/help-center"},
    "youtube": {"domain": "studio.youtube.com", "kinds": ["music", "sfx"], "mode": "account_required", "license": "https://support.google.com/youtube/answer/3376882"},
    "myinstants": {"domain": "myinstants.com", "kinds": ["sfx"], "mode": "reference_only", "license": "https://www.myinstants.com/en/terms_of_use.html"},
}


def search_plan(query, kind):
    query = " ".join(query.split())
    if not query or len(query) > 120 or kind not in ("music", "sfx"):
        raise ValueError("Use a short sound description and music/sfx kind")
    rows = []
    for provider, spec in PROVIDERS.items():
        eligible = kind in spec["kinds"]
        query_text = f"site:{spec['domain']} {query} {'instrumental chill music' if kind == 'music' else 'sound effect'}"
        rows.append({"provider": provider, **spec, "query": query_text,
                     "status": "not_searched" if eligible else "not_applicable",
                     "auto_download": provider == "mixkit" and kind == "sfx",
                     "next_action": ("Reference only: no automated requests or downloads" if spec["mode"] == "reference_only" else
                                     "Authorized account needed; do not bypass login" if spec["mode"] == "account_required" else
                                     "Search with agent web tools; record actual results and rights evidence") if eligible else "Skip this media type"})
    return {"query": query, "kind": kind, "sources": rows}


class MixkitCards(HTMLParser):
    def __init__(self):
        super().__init__()
        self.cards, self.current, self.in_title = [], None, False

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        ident = attrs.get("data-audio-player-item-id-value")
        if ident and attrs.get("data-audio-player-item-type-value") == "sfx":
            self.current = {"provider_id": ident, "title": ""}
            self.cards.append(self.current)
        if tag == "h2" and "item-grid-card__title" in attrs.get("class", "") and self.current is not None:
            self.in_title = True
        modal = attrs.get("data-download--button-modal-url-value")
        if modal and self.current is not None:
            self.current["download_page"] = urljoin("https://mixkit.co", modal)

    def handle_endtag(self, tag):
        if tag == "h2":
            self.in_title = False

    def handle_data(self, data):
        if self.in_title:
            self.current["title"] += data


def get_page(url):
    # Temporary pages are bounded; no cookies or account state is used.
    cache = p.ROOT/".cache/audio-search"
    cache.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="page-", dir=cache) as tmp:
        path = Path(tmp)/"page.html"
        fetch(url, path, limit=2*1024*1024)
        return path.read_text(encoding="utf-8", errors="replace")


def mixkit_search(query, limit=8):
    # Category URLs are visible public routes, not an undocumented search API.
    words = set(re.findall(r"[a-z]+", query.lower()))
    categories = [w for w in ("wood", "whoosh", "transition", "impact", "cloth", "swoosh", "nature") if w in words]
    category = categories[0] if categories else "transition"
    url = f"https://mixkit.co/free-sound-effects/{quote(category)}/"
    html = get_page(url)
    parser = MixkitCards()
    parser.feed(html)
    results = []
    seen = set()
    for card in parser.cards:
        if not card.get("title", "").strip() or not card.get("download_page") or card["provider_id"] in seen:
            continue
        if not card["provider_id"].isdigit() or not host_is(card["download_page"], "mixkit.co"):
            continue
        seen.add(card["provider_id"])
        title = " ".join(card["title"].split())
        title_words = set(re.findall(r"[a-z]+", title.lower()))
        overlap = len(words.intersection(title_words))
        if "impact" in words and title_words.intersection({"hit", "knock", "knocking", "tap", "tapping", "impact"}):
            overlap += 3
        if "wood" in words and "wooden" in title_words:
            overlap += 1
        if "wood" in words and not title_words.intersection({"wood", "wooden"}):
            overlap -= 4
        if "soft" in words and title_words.intersection({"hard", "loud", "explosion", "crash"}):
            overlap -= 3
        if not words.intersection({"door", "ambience", "ambient"}) and title_words.intersection({"door", "ambience", "ambient"}):
            overlap -= 3
        results.append({**card, "title": title, "source_url": url, "provider": "mixkit", "kind": "sfx",
                        "match_score": overlap, "category": category, "rights_status": "provider_license_reviewed",
                        "listening_review": "pending", "trend_status": "not_established"})
    return sorted(results, key=lambda c: (-c["match_score"], c["provider_id"]))[:limit]


def mixkit_request(candidate):
    if not host_is(candidate["download_page"], "mixkit.co"):
        raise ValueError("Not a Mixkit download page")
    html = get_page(candidate["download_page"])
    match = re.search(r'data-download--modal-url-value="([^"]+)"', html)
    if not match:
        raise ValueError("Download link unavailable; do not substitute preview audio")
    return {"id": "mixkit-sfx-"+candidate["provider_id"], "kind": "sfx", "title": candidate["title"],
            "author": "Mixkit", "provider": "mixkit", "source_url": candidate["source_url"],
            "download_url": unescape(match[1]), "license_url": "https://mixkit.co/license/modal/sfxFree/",
            "license": "Mixkit-SFX-Free", "usage": "facebook-commercial-video", "attribution": "",
            "license_evidence": "Official free SFX category and its own download modal; Mixkit SFX Free license permits incorporation in commercial social video, not standalone redistribution.",
            "verified_on": datetime.now(timezone.utc).date().isoformat(), "tags": [candidate["category"]]}


def search(job, query, kind, live=False, download_limit=0):
    if not 0 <= download_limit <= 3 or (download_limit and (not live or kind != "sfx")):
        raise ValueError("Automatic acquisition requires live SFX search and limit 1–3")
    report = search_plan(query, kind)
    report.update(candidates=[], downloads=[], checked_at=datetime.now(timezone.utc).isoformat())
    if live and kind == "sfx":
        row = next(s for s in report["sources"] if s["provider"] == "mixkit")
        try:
            report["candidates"] = mixkit_search(query)
            row["status"] = "results" if report["candidates"] else "no_results_or_markup_changed"
        except Exception as exc:
            row.update(status="unavailable", error=str(exc))
        with p.job_lock():
            for candidate in [c for c in report["candidates"] if c["match_score"] >= 2][:download_limit]:
                try:
                    report["downloads"].append(acquire(mixkit_request(candidate)))
                except Exception as exc:
                    report["downloads"].append({"id": candidate["provider_id"], "status": "failed", "error": str(exc)})
    p.write(job/"audio-source-search.json", report)
    return report


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--job", required=True)
    parser.add_argument("--query", required=True)
    parser.add_argument("--kind", choices=["music", "sfx"], required=True)
    parser.add_argument("--live", action="store_true")
    parser.add_argument("--download-limit", type=int, choices=range(0, 4), default=0)
    args = parser.parse_args()
    job = Path(args.job).resolve()
    if not job.is_relative_to((p.ROOT/"output").resolve()):
        parser.error("Job must be under output/")
    result = search(job, args.query, args.kind, args.live, args.download_limit)
    print({"candidates": len(result["candidates"]), "downloads": result["downloads"]})
