import random
import time
from pathlib import Path
from typing import Callable

import requests

from .config import (
    COMFY_URL,
    DEFAULT_IMAGE_CFG,
    DEFAULT_IMAGE_MODEL,
    DEFAULT_IMAGE_SAMPLER,
    DEFAULT_IMAGE_SCHEDULER,
    DEFAULT_IMAGE_STEPS,
    RUNTIME_DIR,
)


class ComfyClient:
    def __init__(self, base_url: str = COMFY_URL):
        self.base_url = base_url.rstrip("/")

    def available(self) -> bool:
        try:
            return requests.get(f"{self.base_url}/system_stats", timeout=2).ok
        except requests.RequestException:
            return False

    def local_checkpoints(self) -> list[str]:
        root = RUNTIME_DIR / "ComfyUI_windows_portable" / "ComfyUI" / "models" / "checkpoints"
        if not root.exists():
            return []
        names = []
        for p in root.iterdir():
            if p.is_file() and p.suffix.lower() in {".safetensors", ".ckpt", ".pt"}:
                names.append(p.name)
        return sorted(names)

    def server_checkpoints(self) -> list[str]:
        try:
            r = requests.get(f"{self.base_url}/object_info/CheckpointLoaderSimple", timeout=10)
            r.raise_for_status()
            return list(
                r.json()
                .get("CheckpointLoaderSimple", {})
                .get("input", {})
                .get("required", {})
                .get("ckpt_name", [[], {}])[0]
            )
        except Exception:
            return []

    def checkpoints(self) -> list[str]:
        server = self.server_checkpoints() if self.available() else []
        if server:
            return sorted(server)
        local = self.local_checkpoints()
        return local or [DEFAULT_IMAGE_MODEL]

    def _workflow(
        self,
        prompt: str,
        negative: str,
        width: int,
        height: int,
        model: str,
        steps: int,
        cfg: float,
        seed: int,
        sampler: str | None = None,
        scheduler: str | None = None,
    ) -> dict:
        turbo = "turbo" in model.lower()
        if turbo:
            effective_steps = min(8, max(1, steps))
            effective_cfg = min(2.0, max(0.5, cfg))
            sampler_name = "euler"
            scheduler_name = "normal"
        else:
            effective_steps = max(12, steps)
            effective_cfg = max(3.0, cfg)
            sampler_name = sampler or DEFAULT_IMAGE_SAMPLER
            scheduler_name = scheduler or DEFAULT_IMAGE_SCHEDULER

        return {
            "1": {"class_type": "CheckpointLoaderSimple", "inputs": {"ckpt_name": model}},
            "2": {"class_type": "CLIPTextEncode", "inputs": {"text": prompt, "clip": ["1", 1]}},
            "3": {"class_type": "CLIPTextEncode", "inputs": {"text": negative, "clip": ["1", 1]}},
            "4": {"class_type": "EmptyLatentImage", "inputs": {"width": width, "height": height, "batch_size": 1}},
            "5": {
                "class_type": "KSampler",
                "inputs": {
                    "seed": seed,
                    "steps": effective_steps,
                    "cfg": effective_cfg,
                    "sampler_name": sampler_name,
                    "scheduler": scheduler_name,
                    "denoise": 1.0,
                    "model": ["1", 0],
                    "positive": ["2", 0],
                    "negative": ["3", 0],
                    "latent_image": ["4", 0],
                },
            },
            "6": {"class_type": "VAEDecode", "inputs": {"samples": ["5", 0], "vae": ["1", 2]}},
            "7": {"class_type": "SaveImage", "inputs": {"filename_prefix": "ZeroGPT", "images": ["6", 0]}},
        }

    def _prompt_error(self, response: requests.Response, model: str) -> RuntimeError:
        detail = ""
        try:
            payload = response.json()
            detail = payload.get("error", {}).get("message") or payload.get("error", {}).get("details") or str(payload)
        except Exception:
            detail = response.text.strip()
        available = self.server_checkpoints()
        if model not in available:
            if available:
                return RuntimeError(
                    f"ComfyUI rejected the workflow because checkpoint '{model}' is not available. "
                    f"Available checkpoint(s): {', '.join(available[:8])}. Open Settings and run Install / Repair Local AI."
                )
            return RuntimeError(
                "ComfyUI is online but has no usable image checkpoint loaded. Run Install / Repair Local AI and let setup finish completely."
            )
        msg = f"ComfyUI rejected the image workflow ({response.status_code})."
        if detail:
            msg += f" Details: {detail}"
        return RuntimeError(msg)

    def generate(
        self,
        prompt: str,
        *,
        negative: str = "low quality, blurry, distorted, deformed hands, bad anatomy, artifacts",
        width: int = 1024,
        height: int = 1024,
        model: str = DEFAULT_IMAGE_MODEL,
        steps: int = DEFAULT_IMAGE_STEPS,
        cfg: float = DEFAULT_IMAGE_CFG,
        sampler: str | None = None,
        scheduler: str | None = None,
        seed: int | None = None,
        timeout: int = 1200,
        progress: Callable[[str], None] | None = None,
        cancel: Callable[[], bool] | None = None,
    ) -> tuple[bytes, int]:
        seed = int(seed if seed is not None else random.randint(1, 2**31 - 1))

        available = self.server_checkpoints()
        if available and model not in available:
            model = DEFAULT_IMAGE_MODEL if DEFAULT_IMAGE_MODEL in available else available[0]
        elif not available:
            raise RuntimeError(
                "ComfyUI is online, but no image checkpoint is available. Run Install / Repair Local AI and wait for it to finish."
            )

        workflow = self._workflow(prompt, negative, width, height, model, steps, cfg, seed, sampler, scheduler)
        r = requests.post(f"{self.base_url}/prompt", json={"prompt": workflow}, timeout=20)
        if not r.ok:
            raise self._prompt_error(r, model)
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
                status = history[prompt_id].get("status", {})
                if status.get("status_str") == "error":
                    messages = status.get("messages", [])
                    raise RuntimeError(f"ComfyUI generation failed: {messages[-1] if messages else 'unknown error'}")
                for node in outputs.values():
                    images = node.get("images", [])
                    if images:
                        image = images[0]
                        view = requests.get(
                            f"{self.base_url}/view",
                            params={"filename": image["filename"], "subfolder": image.get("subfolder", ""), "type": image.get("type", "output")},
                            timeout=90,
                        )
                        view.raise_for_status()
                        return view.content, seed
            if progress:
                progress("Generating high-quality image…")
            time.sleep(0.75)
        raise TimeoutError("Image generation timed out")
