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
    def __init__(self, log: Callable[[str], None], progress: Callable[[int, str], None] | None = None):
        self.log = log
        self.progress = progress or (lambda value, label: None)

    def _emit(self, value: int, label: str):
        self.progress(max(0, min(100, int(value))), label)
        self.log(label)

    def _run(self, args, cwd=None, check=True, capture_output=False):
        self.log("> " + " ".join(map(str, args)))
        return subprocess.run(
            args,
            cwd=cwd,
            check=check,
            text=True,
            capture_output=capture_output,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        )

    def _download(self, url: str, target: Path, start: int, end: int):
        target.parent.mkdir(parents=True, exist_ok=True)
        temp = target.with_suffix(target.suffix + ".part")
        temp.unlink(missing_ok=True)
        with requests.get(url, stream=True, timeout=(15, 120), allow_redirects=True) as r:
            r.raise_for_status()
            total = int(r.headers.get("content-length", 0))
            done = 0
            last = -1
            with open(temp, "wb") as f:
                for chunk in r.iter_content(1024 * 1024):
                    if not chunk:
                        continue
                    f.write(chunk)
                    done += len(chunk)
                    pct = int(done * 100 / total) if total else 0
                    if pct != last:
                        self.progress(start + int((end - start) * pct / 100), f"Downloading {target.name} · {pct}%")
                        last = pct
        temp.replace(target)

    def _find_ollama(self):
        candidates = [
            shutil.which("ollama"),
            str(Path(os.environ.get("LOCALAPPDATA", "")) / "Programs" / "Ollama" / "ollama.exe"),
            str(Path(os.environ.get("LOCALAPPDATA", "")) / "Ollama" / "ollama.exe"),
        ]
        return next((p for p in candidates if p and Path(p).exists()), None)

    def ensure_ollama(self):
        self._emit(4, "Checking Ollama…")
        exe = self._find_ollama()
        if not exe:
            winget = shutil.which("winget")
            if not winget:
                raise RuntimeError("Windows App Installer (winget) is required to install Ollama automatically.")
            self._emit(8, "Installing Ollama…")
            self._run([winget, "install", "--id", "Ollama.Ollama", "-e", "--accept-package-agreements", "--accept-source-agreements", "--silent"])
            exe = self._find_ollama()
        if not exe:
            raise RuntimeError("Ollama was installed but ollama.exe could not be found. Restart ZeroGPT and retry.")
        try:
            requests.get("http://127.0.0.1:11434/api/tags", timeout=2).raise_for_status()
        except Exception:
            self._emit(14, "Starting Ollama…")
            subprocess.Popen([exe, "serve"], creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0), stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            for _ in range(15):
                try:
                    if requests.get("http://127.0.0.1:11434/api/tags", timeout=2).ok:
                        break
                except Exception:
                    pass
                time.sleep(1)
        self._emit(18, f"Downloading default chat model · {DEFAULT_CHAT_MODEL}")
        self._run([exe, "pull", DEFAULT_CHAT_MODEL])
        self._emit(32, "Ollama is ready.")

    def _portable_asset(self):
        self.log("Finding current official ComfyUI Windows portable release…")
        release = requests.get(
            "https://api.github.com/repos/Comfy-Org/ComfyUI/releases/latest",
            timeout=30,
            headers={"Accept": "application/vnd.github+json"},
        )
        release.raise_for_status()
        assets = release.json().get("assets", [])
        for needle in ("windows_portable_nvidia", "windows_portable"):
            asset = next((a for a in assets if needle in a.get("name", "").lower() and a.get("name", "").lower().endswith(".7z")), None)
            if asset:
                return asset
        raise RuntimeError("Could not locate the official ComfyUI Windows portable archive.")

    def _runtime_complete(self, root: Path) -> bool:
        return (
            (root / "python_embeded" / "python.exe").exists()
            and (root / "ComfyUI" / "main.py").exists()
            and (root / "ComfyUI" / "models" / "checkpoints").exists()
        )

    def _extract_comfy_archive(self, archive: Path):
        tar = shutil.which("tar") or shutil.which("tar.exe")
        if tar:
            self.log("Extracting with Windows tar…")
            result = self._run([tar, "-xf", str(archive), "-C", str(RUNTIME_DIR)], check=False, capture_output=True)
            if result.returncode == 0:
                return
            self.log("Windows tar could not extract the archive; trying 7-Zip/py7zr fallback.")
            if result.stderr:
                self.log(result.stderr.strip())

        seven = shutil.which("7z") or shutil.which("7z.exe") or shutil.which("7zz") or shutil.which("7zz.exe")
        if seven:
            self.log("Extracting with 7-Zip…")
            result = self._run([seven, "x", str(archive), f"-o{RUNTIME_DIR}", "-y"], check=False, capture_output=True)
            if result.returncode == 0:
                return
            if result.stderr:
                self.log(result.stderr.strip())

        self.log("Trying Python 7z extraction fallback…")
        try:
            with py7zr.SevenZipFile(archive, mode="r") as z:
                z.extractall(path=RUNTIME_DIR)
            return
        except Exception as exc:
            raise RuntimeError(
                "ComfyUI extraction failed. The archive uses a compression filter not supported by the available extractors. "
                f"Windows tar/7-Zip could not extract it either. Details: {exc}"
            ) from exc

    def _stop_zerogpt_comfy(self):
        try:
            import psutil
            runtime_text = str(RUNTIME_DIR).lower()
            for proc in psutil.process_iter(["pid", "cmdline"]):
                try:
                    cmd = " ".join(proc.info.get("cmdline") or []).lower()
                    if runtime_text in cmd and "comfyui" in cmd and "main.py" in cmd:
                        proc.terminate()
                        try:
                            proc.wait(timeout=5)
                        except psutil.TimeoutExpired:
                            proc.kill()
                except (psutil.NoSuchProcess, psutil.AccessDenied):
                    pass
        except Exception:
            pass

    def ensure_comfyui(self):
        comfy_root = RUNTIME_DIR / "ComfyUI_windows_portable"

        if comfy_root.exists() and not self._runtime_complete(comfy_root):
            self._emit(34, "Incomplete ComfyUI install detected — repairing…")
            self._stop_zerogpt_comfy()
            shutil.rmtree(comfy_root, ignore_errors=True)

        if not self._runtime_complete(comfy_root):
            self._emit(35, "Preparing ComfyUI…")
            asset = self._portable_asset()
            archive = RUNTIME_DIR / asset["name"]
            if archive.exists():
                archive.unlink(missing_ok=True)
            self._download(asset["browser_download_url"], archive, 36, 56)
            self._emit(57, "Extracting ComfyUI…")
            self._extract_comfy_archive(archive)
            archive.unlink(missing_ok=True)

            if not self._runtime_complete(comfy_root):
                shutil.rmtree(comfy_root, ignore_errors=True)
                raise RuntimeError("ComfyUI archive extraction completed but the runtime is still incomplete. Please retry setup.")

        checkpoints = comfy_root / "ComfyUI" / "models" / "checkpoints"
        checkpoints.mkdir(parents=True, exist_ok=True)
        model_path = checkpoints / DEFAULT_IMAGE_MODEL
        if model_path.exists() and model_path.stat().st_size < 1_000_000_000:
            self.log("Partial image model detected — redownloading it.")
            model_path.unlink(missing_ok=True)
        if not model_path.exists():
            self._emit(62, "Downloading the high-quality SDXL Base image model…")
            self._download(DEFAULT_IMAGE_URL, model_path, 62, 92)

        self._emit(93, "Starting ComfyUI in VRAM-safe quality mode…")
        self.start_comfyui()

        try:
            info = requests.get("http://127.0.0.1:8188/object_info/CheckpointLoaderSimple", timeout=10)
            info.raise_for_status()
            values = info.json().get("CheckpointLoaderSimple", {}).get("input", {}).get("required", {}).get("ckpt_name", [[], {}])[0]
            if DEFAULT_IMAGE_MODEL not in values:
                raise RuntimeError(
                    "ComfyUI is online but the high-quality SDXL Base checkpoint is not visible to it. "
                    "Close any other ComfyUI instance using port 8188, then run Install / Repair Local AI again."
                )
        except RuntimeError:
            raise
        except Exception as exc:
            raise RuntimeError(f"ComfyUI started, but ZeroGPT could not verify the image model: {exc}") from exc

        self._emit(98, "ComfyUI and SDXL Base are ready.")

    def start_comfyui(self):
        root = RUNTIME_DIR / "ComfyUI_windows_portable"
        py = root / "python_embeded" / "python.exe"
        main = root / "ComfyUI" / "main.py"
        if not py.exists() or not main.exists():
            raise RuntimeError("ComfyUI runtime is incomplete. Re-run Install Local AI.")

        try:
            if requests.get("http://127.0.0.1:8188/system_stats", timeout=2).ok:
                return
        except Exception:
            pass

        # Current ComfyUI supports --lowvram. This keeps SDXL Base practical on
        # a 6 GB NVIDIA GPU by moving text encoders/offloaded components to RAM.
        subprocess.Popen(
            [
                str(py), "-s", str(main),
                "--windows-standalone-build",
                "--listen", "127.0.0.1",
                "--port", "8188",
                "--disable-auto-launch",
                "--lowvram",
            ],
            cwd=str(root / "ComfyUI"),
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        for _ in range(60):
            try:
                if requests.get("http://127.0.0.1:8188/system_stats", timeout=2).ok:
                    return
            except Exception:
                pass
            time.sleep(1)
        raise RuntimeError("ComfyUI was started but did not become ready.")

    def install_everything(self):
        self._emit(1, "ZeroGPT local AI setup started.")
        self.ensure_ollama()
        self.ensure_comfyui()
        self._emit(100, "Everything is installed. ZeroGPT is ready for high-quality offline image generation.")
