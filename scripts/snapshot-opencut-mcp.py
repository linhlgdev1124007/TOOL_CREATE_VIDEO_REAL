"""Save local MCP modifications for reproducible setup on another machine."""
import json
from pathlib import Path
import shutil
import subprocess

root = Path(__file__).resolve().parents[1]
repo = root / "opencut-mcp"
config = json.loads((root / "dependencies.lock.json").read_text())["opencut-mcp"]
head = subprocess.check_output(["git", "-C", str(repo), "rev-parse", "HEAD"]).decode().strip()
if head != config["commit"]:
    raise SystemExit("Upstream commit changed; review and update dependencies.lock.json first")
patch = root / config["patch"]
patch.parent.mkdir(exist_ok=True)
patch.write_bytes(subprocess.check_output(["git", "-C", str(repo), "diff", "--binary", "HEAD", "--", "bun.lock", "package.json", "tsconfig.json", "src", "scripts", "tests"]))
extra = subprocess.check_output(["git", "-C", str(repo), "ls-files", "--others", "--exclude-standard", "-z", "--", "src", "scripts", "tests"]).decode().split("\0")
for name in filter(None, extra):
    if Path(name).suffix not in {".ts", ".json"}:
        raise SystemExit(f"Review unexpected untracked file: {name}")
    target = root / config["overlay"] / name
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(repo / name, target)
print("Saved MCP patch and source overlays. Review git diff before committing.")
