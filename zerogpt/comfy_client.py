import random
import time
import requests

from .config import COMFY_URL, DEFAULT_IMAGE_MODEL


class ComfyClient:
    def __init__(self, base_url: str = COMFY_URL):
        self.base_url = base_url.rstrip("/")

    def available(self) -> bool:
        try:
            return requests.get(f"{self.base_url}/system_stats", timeout=2).ok
        except requests.RequestException:
            return False

    def _workflow(self, prompt: str, negative: str, width: int, height: int) -> dict:
        seed = random.randint(1, 2**31 - 1)
        return {
            "1": {"class_type": "CheckpointLoaderSimple", "inputs": {"ckpt_name": DEFAULT_IMAGE_MODEL}},
            "2": {"class_type": "CLIPTextEncode", "inputs": {"text": prompt, "clip": ["1", 1]}},
            "3": {"class_type": "CLIPTextEncode", "inputs": {"text": negative, "clip": ["1", 1]}},
            "4": {"class_type": "EmptyLatentImage", "inputs": {"width": width, "height": height, "batch_size": 1}},
            "5": {"class_type": "KSampler", "inputs": {"seed": seed, "steps": 4, "cfg": 1.0, "sampler_name": "euler", "scheduler": "normal", "denoise": 1.0, "model": ["1", 0], "positive": ["2", 0], "negative": ["3", 0], "latent_image": ["4", 0]}},
            "6": {"class_type": "VAEDecode", "inputs": {"samples": ["5", 0], "vae": ["1", 2]}},
            "7": {"class_type": "SaveImage", "inputs": {"filename_prefix": "ZeroGPT", "images": ["6", 0]}},
        }

    def generate(self, prompt: str, negative: str = "low quality, blurry", width: int = 1024, height: int = 1024, timeout: int = 600) -> bytes:
        r = requests.post(f"{self.base_url}/prompt", json={"prompt": self._workflow(prompt, negative, width, height)}, timeout=15)
        r.raise_for_status()
        prompt_id = r.json()["prompt_id"]
        deadline = time.time() + timeout
        while time.time() < deadline:
            h = requests.get(f"{self.base_url}/history/{prompt_id}", timeout=10).json()
            if prompt_id in h:
                outputs = h[prompt_id].get("outputs", {})
                for node in outputs.values():
                    images = node.get("images", [])
                    if images:
                        im = images[0]
                        vr = requests.get(f"{self.base_url}/view", params={"filename": im["filename"], "subfolder": im.get("subfolder", ""), "type": im.get("type", "output")}, timeout=60)
                        vr.raise_for_status()
                        return vr.content
            time.sleep(1)
        raise TimeoutError("Image generation timed out")
