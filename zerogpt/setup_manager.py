import os
import shutil
import subprocess
import time
from pathlib import Path
from typing import Callable

import py7zr
import requests

from .config import DEFAULT_CHAT_MODEL, DEFAULT_IMAGE_MODEL, DEFAULT_IMAGE_URL, RUNTIME_DIR


class SetupManager:
    def __init__(self, log: Callable[[str], None], progress: Callable[[int,str], None] | None = None):
        self.log = log
        self.progress = progress or (lambda value,label: None)

    def _emit(self, value: int, label: str):
        self.progress(max(0,min(100,int(value))), label)
        self.log(label)

    def _run(self, args, cwd=None, check=True):
        self.log("> " + " ".join(map(str,args)))
        return subprocess.run(args,cwd=cwd,check=check,text=True,capture_output=False,creationflags=getattr(subprocess,"CREATE_NO_WINDOW",0))

    def _download(self, url: str, target: Path, start: int, end: int):
        target.parent.mkdir(parents=True,exist_ok=True)
        with requests.get(url,stream=True,timeout=(15,120),allow_redirects=True) as r:
            r.raise_for_status(); total=int(r.headers.get("content-length",0)); done=0; last=-1
            with open(target,"wb") as f:
                for chunk in r.iter_content(1024*1024):
                    if not chunk: continue
                    f.write(chunk); done += len(chunk); pct=int(done*100/total) if total else 0
                    if pct != last:
                        self.progress(start + int((end-start)*pct/100), f"Downloading {target.name} · {pct}%"); last=pct

    def _find_ollama(self):
        candidates=[shutil.which("ollama"),str(Path(os.environ.get("LOCALAPPDATA",""))/"Programs"/"Ollama"/"ollama.exe"),str(Path(os.environ.get("LOCALAPPDATA",""))/"Ollama"/"ollama.exe")]
        return next((p for p in candidates if p and Path(p).exists()),None)

    def ensure_ollama(self):
        self._emit(4,"Checking Ollama…"); exe=self._find_ollama()
        if not exe:
            winget=shutil.which("winget")
            if not winget: raise RuntimeError("Windows App Installer (winget) is required to install Ollama automatically.")
            self._emit(8,"Installing Ollama…")
            self._run([winget,"install","--id","Ollama.Ollama","-e","--accept-package-agreements","--accept-source-agreements","--silent"])
            exe=self._find_ollama()
        if not exe: raise RuntimeError("Ollama was installed but ollama.exe could not be found. Restart ZeroGPT and retry.")
        try: requests.get("http://127.0.0.1:11434/api/tags",timeout=2).raise_for_status()
        except Exception:
            self._emit(14,"Starting Ollama…")
            subprocess.Popen([exe,"serve"],creationflags=getattr(subprocess,"CREATE_NO_WINDOW",0),stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
            for _ in range(15):
                try:
                    if requests.get("http://127.0.0.1:11434/api/tags",timeout=2).ok: break
                except Exception: pass
                time.sleep(1)
        self._emit(18,f"Downloading default chat model · {DEFAULT_CHAT_MODEL}"); self._run([exe,"pull",DEFAULT_CHAT_MODEL]); self._emit(32,"Ollama is ready.")

    def _portable_asset(self):
        self.log("Finding current official ComfyUI Windows portable release…")
        release=requests.get("https://api.github.com/repos/Comfy-Org/ComfyUI/releases/latest",timeout=30,headers={"Accept":"application/vnd.github+json"}); release.raise_for_status(); assets=release.json().get("assets",[])
        for needle in ("windows_portable_nvidia","windows_portable"):
            asset=next((a for a in assets if needle in a.get("name","").lower() and a.get("name","").lower().endswith(".7z")),None)
            if asset: return asset
        raise RuntimeError("Could not locate the official ComfyUI Windows portable archive.")

    def ensure_comfyui(self):
        comfy_root=RUNTIME_DIR/"ComfyUI_windows_portable"
        if not comfy_root.exists():
            self._emit(35,"Preparing ComfyUI…"); asset=self._portable_asset(); archive=RUNTIME_DIR/asset["name"]
            self._download(asset["browser_download_url"],archive,36,56); self._emit(57,"Extracting ComfyUI…")
            with py7zr.SevenZipFile(archive,mode="r") as z: z.extractall(path=RUNTIME_DIR)
            archive.unlink(missing_ok=True)
        checkpoints=comfy_root/"ComfyUI"/"models"/"checkpoints"; model_path=checkpoints/DEFAULT_IMAGE_MODEL
        if not model_path.exists(): self._emit(62,"Downloading the default SDXL Turbo image model…"); self._download(DEFAULT_IMAGE_URL,model_path,62,92)
        self._emit(93,"Starting ComfyUI…"); self.start_comfyui(); self._emit(98,"ComfyUI is ready.")

    def start_comfyui(self):
        try:
            if requests.get("http://127.0.0.1:8188/system_stats",timeout=2).ok: return
        except Exception: pass
        root=RUNTIME_DIR/"ComfyUI_windows_portable"; py=root/"python_embeded"/"python.exe"; main=root/"ComfyUI"/"main.py"
        if not py.exists() or not main.exists(): raise RuntimeError("ComfyUI runtime is incomplete. Re-run Install Local AI.")
        subprocess.Popen([str(py),"-s",str(main),"--windows-standalone-build","--listen","127.0.0.1","--port","8188","--disable-auto-launch"],cwd=str(root/"ComfyUI"),creationflags=getattr(subprocess,"CREATE_NO_WINDOW",0),stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
        for _ in range(45):
            try:
                if requests.get("http://127.0.0.1:8188/system_stats",timeout=2).ok: return
            except Exception: pass
            time.sleep(1)
        raise RuntimeError("ComfyUI was started but did not become ready.")

    def install_everything(self):
        self._emit(1,"ZeroGPT local AI setup started."); self.ensure_ollama(); self.ensure_comfyui(); self._emit(100,"Everything is installed. ZeroGPT is ready for offline use.")
