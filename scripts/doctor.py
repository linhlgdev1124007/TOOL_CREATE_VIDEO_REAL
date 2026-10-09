"""Read-only installation checks; no login, generation, download or rendering."""
import importlib
import json
from pathlib import Path
import shutil
import subprocess
import sys

root = Path(__file__).resolve().parents[1]
checks = {}
for tool in ("git", "ffmpeg", "ffprobe", "bun"):
    checks[f"command:{tool}"] = bool(shutil.which(tool) or shutil.which(tool + ".exe"))
checks["python:3.13"] = sys.version_info[:2] == (3, 13)
for module in ("kokoro_onnx", "soundfile", "PIL", "numpy", "onnxruntime", "espeakng_loader"):
    try:
        importlib.import_module(module)
        checks[f"python:{module}"] = True
    except ImportError:
        checks[f"python:{module}"] = False
pins = json.loads((root / "dependencies.lock.json").read_text())
for name, config in pins.items():
    result = subprocess.run(["git", "-C", str(root / name), "rev-parse", "HEAD"], capture_output=True, text=True) if checks["command:git"] else None
    checks[f"pin:{name}"] = bool(result and result.returncode == 0 and result.stdout.strip() == config["commit"])
    checks[f"dependencies:{name}"] = (root / name / "node_modules").is_dir()
for name in ("kokoro-v1.0.onnx", "voices-v1.0.bin"):
    checks[f"model:{name}"] = (root / ".cache/kokoro" / name).is_file()
catalog = root / "reels/assets/catalog.json"
checks["audio:catalog"] = catalog.is_file()
if catalog.is_file():
    assets = json.loads(catalog.read_text(encoding="utf-8"))["assets"]
    checks["audio:files"] = bool(assets) and all((catalog.parent / a["file"]).is_file() for a in assets)
browsers = root / ".cache/ms-playwright"
checks["chromium:headless_shell"] = any(browsers.glob("chromium_headless_shell-*/*/chrome-headless-shell.exe")) or any(browsers.glob("chromium_headless_shell-*/*/headless_shell.exe"))
for name, ok in checks.items():
    print(f"{'OK' if ok else 'FAIL'} {name}")
media = root / "source/Wrydeco_real"
print("INFO Media and branded outro must be supplied locally under", media)
print("INFO Flow sign-in and extension connection are checked separately; no generation was requested.")
sys.exit(0 if all(checks.values()) else 1)
