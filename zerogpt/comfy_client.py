import random
import time
from pathlib import Path
from typing import Callable

import requests

from .config import COMFY_URL, DEFAULT_IMAGE_MODEL, RUNTIME_DIR


class ComfyClient:
    def __init__(self, base_url: str = COMFY_URL):
        self.base_url = base_url.rstrip("/")

    def available(self) -> bool:
        try:
            return requests.get(f"{self.base_url}/system_stats", timeout=2).ok
        except requests.RequestException:
            return False

    def checkpoints(self) -> list[str]:
        root = RUNTIME_DIR / "ComfyUI_windows_portable" / "ComfyUI" / "models" / "checkpoints"
        if not root.exists():
            return [DEFAULT_IMAGE_MODEL]
        names = []
        for p in root.iterdir():
            if p.suffix.lower() in {".safetensors", ".ckpt", ".pt"}:
                names.append(p.name)
        return sorted(names) or [DEFAULT_IMAGE_MODEL]

    def _workflow(self, prompt: str, negative: str, width: int, height: int, model: str, steps: int, cfg: float, seed: int) -> dict:
        turbo = "turbo" in model.lower()
        effective_steps = min(8, steps) if turbo else steps
        effective_cfg = min(2.0, cfg) if turbo else cfg
        return {
            "1": {"class_type": "CheckpointLoaderSimple", "inputs": {"ckpt_name": model}},
            "2": {"class_type": "CLIPTextEncode", "inputs": {"text": prompt, "clip": ["1", 1]}},
            "3": {"class_type": "CLIPTextEncode", "inputs": {"text": negative, "clip": ["1", 1]}},
            "4": {"class_type": "EmptyLatentImage", "inputs": {"width": width, "height": height, "batch_size": 1}},
            "5": {"class_type": "KSampler", "inputs": {"seed": seed, "steps": effective_steps, "cfg": effective_cfg, "sampler_name": "euler", "scheduler": "normal", "denoise": 1.0, "model": ["1", 0], "positive": ["2", 0], "negative": ["3", 0], "latent_image": ["4", 0]}},
            "6": {"class_type": "VAEDecode", "inputs": {"samples": ["5", 0], "vae": ["1", 2]}},
            "7": {"class_type": "SaveImage", "inputs": {"filename_prefix": "ZeroGPT", "images": ["6", 0]}},
        }

    def generate(self, prompt: str, *, negative: str = "low quality, blurry, distorted", width: int = 1024, height: int = 1024, model: str = DEFAULT_IMAGE_MODEL, steps: int = 4, cfg: float = 1.0, seed: int | None = None, timeout: int = 900, progress: Callable[[str], None] | None = None, cancel: Callable[[], bool] | None = None) -> tuple[bytes, int]:
        seed = int(seed if seed is not None else random.randint(1, 2**31 - 1))
        workflow = self._workflow(prompt, negative, width, height, model, steps, cfg, seed)
        r = requests.post(f"{self.base_url}/prompt", json={"prompt": workflow}, timeout=20)
        r.raise_for_status()
        prompt_id = r.json()["prompt_id"]
        deadline = time.time() + timeout
        while time.time() < deadline:
            if cancel and cancel():
                try:
                    requests.post(f"{self.base_url}/interrupt", timeout=3)
                except requests.RequestException:
                    pass
                raise RuntimeError("Generation cancelled")
            history = requests.get(f"{self.base_url}/history/{prompt_id}", timeout=10).json()
            if prompt_id in history:
                outputs = history[prompt_id].get("outputs", {})
                for node in outputs.values():
                    images = node.get("images", [])
                    if images:
                        image = images[0]
                        view = requests.get(f"{self.base_url}/view", params={"filename": image["filename"], "subfolder": image.get("subfolder", ""), "type": image.get("type", "output")}, timeout=90)
                        view.raise_for_status()
                        return view.content, seed
            if progress:
                progress("Generating…")
            time.sleep(0.75)
        raise TimeoutError("Image generation timed out")
