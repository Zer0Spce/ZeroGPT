import os
import shutil
import subprocess
import sys
import time
from pathlib import Path

import py7zr
import requests

from .config import DEFAULT_CHAT_MODEL, DEFAULT_IMAGE_MODEL, DEFAULT_IMAGE_URL, RUNTIME_DIR


class SetupManager:
    def __init__(self, log):
        self.log = log

    def _run(self, args, cwd=None, check=True):
        self.log("> " + " ".join(map(str, args)))
        return subprocess.run(args, cwd=cwd, check=check, text=True, capture_output=False)

    def _download(self, url: str, target: Path):
        target.parent.mkdir(parents=True, exist_ok=True)
        with requests.get(url, stream=True, timeout=60) as r:
            r.raise_for_status()
            total = int(r.headers.get("content-length", 0))
            done = 0
            with open(target, "wb") as f:
                for chunk in r.iter_content(1024 * 1024):
                    if not chunk:
                        continue
                    f.write(chunk)
                    done += len(chunk)
                    if total:
                        self.log(f"Downloading {target.name}: {done * 100 // total}%")

    def ensure_ollama(self):
        exe = shutil.which("ollama")
        if not exe:
            self.log("Installing Ollama...")
            self._run(["winget", "install", "--id", "Ollama.Ollama", "-e", "--accept-package-agreements", "--accept-source-agreements"])
            candidates = [Path(os.environ.get("LOCALAPPDATA", "")) / "Programs" / "Ollama" / "ollama.exe"]
            exe = next((str(p) for p in candidates if p.exists()), None) or shutil.which("ollama")
        if not exe:
            raise RuntimeError("Ollama installation finished but ollama.exe could not be found. Restart ZeroGPT and retry.")
        try:
            requests.get("http://127.0.0.1:11434/api/tags", timeout=2).raise_for_status()
        except Exception:
            subprocess.Popen([exe, "serve"], creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
            time.sleep(3)
        self.log(f"Pulling default model: {DEFAULT_CHAT_MODEL}")
        self._run([exe, "pull", DEFAULT_CHAT_MODEL])

    def ensure_comfyui(self):
        comfy_root = RUNTIME_DIR / "ComfyUI_windows_portable"
        if not comfy_root.exists():
            self.log("Finding latest ComfyUI Windows portable package...")
            release = requests.get("https://api.github.com/repos/comfyanonymous/ComfyUI/releases/latest", timeout=30).json()
            assets = release.get("assets", [])
            asset = next((a for a in assets if "windows_portable_nvidia" in a.get("name", "").lower() and a.get("name", "").lower().endswith(".7z")), None)
            if not asset:
                asset = next((a for a in assets if "windows_portable" in a.get("name", "").lower() and a.get("name", "").lower().endswith(".7z")), None)
            if not asset:
                raise RuntimeError("Could not locate a ComfyUI Windows portable release asset.")
            archive = RUNTIME_DIR / asset["name"]
            self._download(asset["browser_download_url"], archive)
            self.log("Extracting ComfyUI...")
            with py7zr.SevenZipFile(archive, mode="r") as z:
                z.extractall(path=RUNTIME_DIR)
            archive.unlink(missing_ok=True)
        checkpoints = comfy_root / "ComfyUI" / "models" / "checkpoints"
        model_path = checkpoints / DEFAULT_IMAGE_MODEL
        if not model_path.exists():
            self.log("Downloading the default SDXL Turbo image model...")
            self._download(DEFAULT_IMAGE_URL, model_path)
        self.start_comfyui()

    def start_comfyui(self):
        try:
            if requests.get("http://127.0.0.1:8188/system_stats", timeout=2).ok:
                return
        except Exception:
            pass
        root = RUNTIME_DIR / "ComfyUI_windows_portable"
        py = root / "python_embeded" / "python.exe"
        main = root / "ComfyUI" / "main.py"
        if not py.exists() or not main.exists():
            raise RuntimeError("ComfyUI runtime is incomplete.")
        self.log("Starting ComfyUI local server...")
        subprocess.Popen([str(py), "-s", str(main), "--windows-standalone-build", "--listen", "127.0.0.1", "--port", "8188"], cwd=str(root / "ComfyUI"), creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))

    def install_everything(self):
        self.log("ZeroGPT local AI setup started.")
        self.ensure_ollama()
        self.ensure_comfyui()
        self.log("Setup complete. Chat and image generation are ready for offline use.")
