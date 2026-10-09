"""Download pinned Kokoro models and a provenance-tracked free audio starter library."""
import hashlib
import io
import json
from pathlib import Path
import re
import urllib.parse
import urllib.request
import zipfile
import subprocess

from pipeline import ROOT, LIBRARY, probe, write, ff


def fetch(url):
    if __import__("os").name == "nt":
        return subprocess.run(["curl.exe", "--fail", "--location", "--max-time", "180", url],
                              capture_output=True, check=True).stdout
    request = urllib.request.Request(url, headers={"User-Agent": "Wrydeco-Reels/1.0"})
    try:
        with urllib.request.urlopen(request, timeout=180) as response:
            return response.read()
    except urllib.error.URLError:
        # Windows curl uses the OS trust store. Never disable certificate validation.
        result = subprocess.run(["curl.exe", "--fail", "--location", "--max-time", "180", url],
                                capture_output=True, check=True)
        return result.stdout


def download(url, path):
    path.parent.mkdir(parents=True, exist_ok=True)
    if not path.exists():
        data = fetch(url)
        tmp = path.with_suffix(path.suffix+".download")
        tmp.write_bytes(data)
        tmp.replace(path)
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    models = ROOT/".cache/kokoro"
    provenance = []
    for name in ["kokoro-v1.0.onnx", "voices-v1.0.bin"]:
        url = f"https://github.com/thewh1teagle/kokoro-onnx/releases/download/model-files-v1.1/{name}"
        print(f"Downloading {name}", flush=True)
        sha = download(url, models/name)
        provenance.append({"file": name, "url": url, "sha256": sha,
                           "license": "Apache-2.0", "model_source": "https://huggingface.co/hexgrad/Kokoro-82M"})
    write(models/"provenance.json", provenance)
    # Preserve assets acquired after setup when refreshing the starter library.
    catalog_path = LIBRARY/"catalog.json"
    assets = [a for a in json.loads(catalog_path.read_text(encoding="utf-8"))["assets"]
              if a.get("managed_download")] if catalog_path.exists() else []
    # Original author distribution; archive paths are never extracted directly.
    packs = {
        "impact": "https://kenney.nl/media/pages/assets/impact-sounds/87b4ddecda-1677589768/kenney_impact-sounds.zip",
        "interface": "https://kenney.nl/media/pages/assets/interface-sounds/fa43c1dd4d-1677589452/kenney_interface-sounds.zip",
        "rpg": "https://kenney.nl/media/pages/assets/rpg-audio/8e99002d76-1677590336/kenney_rpg-audio.zip",
    }
    for pack, url in packs.items():
        archive = LIBRARY/f"sources/{pack}.zip"
        download(url, archive)
        with zipfile.ZipFile(archive) as z:
            for name in z.namelist():
                if name.lower().endswith("license.txt"):
                    (archive.parent/f"{pack}-license.txt").write_bytes(z.read(name))
            selected = [n for n in z.namelist() if n.lower().endswith((".ogg", ".wav")) and
                        (re.search(r"wood|plank|soft|swoosh|swish|swing|slide|transition|knifeSlice|cloth[1-4]", n, re.I))]
            for name in selected:
                dest = LIBRARY/f"sfx/{pack}-{Path(name).name}"
                dest.parent.mkdir(parents=True, exist_ok=True)
                dest.write_bytes(z.read(name))
                info = probe(dest)
                assets.append({"id": dest.stem, "kind": "sfx", "file": str(dest.relative_to(LIBRARY)).replace("\\", "/"),
                               "source_url": f"https://kenney.nl/assets/{'rpg-audio' if pack == 'rpg' else pack+'-sounds'}", "author": "Kenney",
                               "license": "CC0-1.0", "attribution": "", "tags": [pack, "wood" if "wood" in name.lower() else "transition"],
                               "duration": float(info["format"]["duration"]), "sha256": hashlib.sha256(dest.read_bytes()).hexdigest()})
    # Gentle transition accents derived from recorded CC0 sources, not beep/tone generators.
    for ident, source_name, filters, tags in [
        ("transition-air-soft", "rpg-knifeSlice.ogg", "highpass=f=180,lowpass=f=4500,volume=0.5", ["transition","soft","air"]),
        ("reveal-wood-rise", "impact-impactPlank_medium_000.ogg", "areverse,atempo=0.65,afade=t=in:d=0.6,afade=t=out:st=1.05:d=0.15,volume=0.5", ["reveal","riser","wood"]),
    ]:
        source = LIBRARY/f"sfx/{source_name}"
        dest = LIBRARY/f"sfx/{ident}.wav"
        ff(["-i", source, "-af", filters, "-ar", "48000", "-ac", "2", dest])
        origin = next(a for a in assets if Path(a["file"]).name == source_name)
        assets.append({"id":ident,"kind":"sfx","file":f"sfx/{ident}.wav", "author":"Kenney; Wrydeco pipeline edit",
                       "source_url":origin["source_url"],"license":"CC0-1.0","attribution":"", "tags":tags,
                       "derived_from":origin["id"],"processing":filters,"duration":float(probe(dest)["format"]["duration"]),
                       "sha256":hashlib.sha256(dest.read_bytes()).hexdigest()})
    # These author-hosted tracks are free with attribution, included in generated captions.
    titles = [("Dream Culture", ["warm", "ambient", "reveal"]),
              ("Fluidscape", ["ambient", "slow", "detail"]),
              ("Easy Lemon", ["acoustic", "bright", "craft"]),
              ("Tranquility", ["warm", "ambient", "detail"]),
              ("Porch Swing Days - slower", ["acoustic", "mellow", "wood"]),
              ("Wallpaper", ["rhythmic", "light", "craft"])]
    license_url = "https://incompetech.com/music/royalty-free/licenses/"
    license_html = fetch(license_url)
    (LIBRARY/"sources/incompetech-license.html").write_bytes(license_html)
    for title,tags in titles:
        url = "https://incompetech.com/music/royalty-free/mp3-royaltyfree/"+urllib.parse.quote(title)+".mp3"
        ident = re.sub(r"[^a-z0-9]+", "-", title.lower()).strip("-")
        dest = LIBRARY/f"music/{ident}.mp3"
        print(f"Downloading music: {title}", flush=True)
        sha = download(url, dest)
        info = probe(dest)
        assets.append({"id": ident, "kind": "music", "file": f"music/{ident}.mp3", "title": title,
                       "source_url": url, "license_url": license_url, "license": "CC-BY-4.0",
                       "author": "Kevin MacLeod", "tags": tags, "sha256": sha,
                       "bpm": {"Dream Culture":70,"Easy Lemon":82,"Wallpaper":92,"Porch Swing Days - slower":110}.get(title),
                       "duration": float(info["format"]["duration"]),
                       "attribution": f'"{title}" Kevin MacLeod (incompetech.com). Licensed under Creative Commons: By Attribution 4.0 License. https://creativecommons.org/licenses/by/4.0/ — edited excerpt.'})
        write(LIBRARY/"catalog.json", {"version": 1, "assets": assets})
    print(json.dumps({"music": sum(a["kind"] == "music" for a in assets), "sfx": sum(a["kind"] == "sfx" for a in assets)}))


if __name__ == "__main__":
    main()
