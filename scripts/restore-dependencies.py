"""Restore pinned upstream repositories without overwriting local edits."""
import argparse
import json
from pathlib import Path
import shutil
import subprocess

ROOT = Path(__file__).resolve().parents[1]


def git(*args, check=True):
    return subprocess.run(["git", *map(str, args)], check=check, capture_output=True)


def restore(root):
    pins = json.loads((root / "dependencies.lock.json").read_text(encoding="utf-8"))
    for name, config in pins.items():
        dest = root / name
        if not dest.exists():
            print(f"Cloning {name}", flush=True)
            git("clone", config["url"], dest)
            git("-C", dest, "checkout", "--detach", config["commit"])
        actual = git("-C", dest, "rev-parse", "HEAD").stdout.decode().strip()
        if actual != config["commit"]:
            raise RuntimeError(f"{name}: unexpected commit; preserve existing checkout and inspect")
        # Preflight overlays before any modifications.
        copies = []
        if config.get("overlay"):
            overlay = root / config["overlay"]
            for source in overlay.rglob("*"):
                if source.is_file():
                    target = dest / source.relative_to(overlay)
                    if target.exists() and target.read_bytes().replace(b"\r\n", b"\n") != source.read_bytes().replace(b"\r\n", b"\n"):
                        raise RuntimeError(f"Local changes in {target}; not overwriting")
                    copies.append((source, target))
        if config.get("patch"):
            patch = root / config["patch"]
            if git("-C", dest, "apply", "--reverse", "--check", patch, check=False).returncode == 0:
                print(f"{name}: patch already applied")
            else:
                git("-C", dest, "apply", "--check", patch)
                git("-C", dest, "apply", patch)
        for source, target in copies:
            if not target.exists():
                target.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(source, target)
        print(f"{name}: ready at {actual}", flush=True)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=ROOT)
    args = parser.parse_args()
    try:
        restore(args.root.resolve())
    except subprocess.CalledProcessError as exc:
        raise SystemExit(exc.stderr.decode(errors="replace"))
