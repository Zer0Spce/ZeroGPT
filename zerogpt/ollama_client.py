import base64
import json
from pathlib import Path
from typing import Callable, Iterable

import requests

from .config import OLLAMA_URL


class OllamaClient:
    def __init__(self, base_url: str = OLLAMA_URL):
        self.base_url = base_url.rstrip("/")

    def available(self) -> bool:
        try:
            return requests.get(f"{self.base_url}/api/tags", timeout=2).ok
        except requests.RequestException:
            return False

    def models(self) -> list[dict]:
        r = requests.get(f"{self.base_url}/api/tags", timeout=8)
        r.raise_for_status()
        return r.json().get("models", [])

    def model_names(self) -> list[str]:
        return [m.get("name", "") for m in self.models() if m.get("name")]

    @staticmethod
    def encode_image(path: str | Path) -> str:
        return base64.b64encode(Path(path).read_bytes()).decode("ascii")

    def chat_stream(
        self,
        model: str,
        messages: list[dict],
        *,
        temperature: float = 0.7,
        num_ctx: int = 8192,
        cancel: Callable[[], bool] | None = None,
        timeout: int = 900,
    ) -> Iterable[str]:
        payload = {
            "model": model,
            "messages": messages,
            "stream": True,
            "options": {"temperature": temperature, "num_ctx": num_ctx},
        }
        with requests.post(
            f"{self.base_url}/api/chat",
            json=payload,
            stream=True,
            timeout=(10, timeout),
        ) as r:
            r.raise_for_status()
            for line in r.iter_lines():
                if cancel and cancel():
                    return
                if not line:
                    continue
                obj = json.loads(line.decode("utf-8"))
                chunk = obj.get("message", {}).get("content", "")
                if chunk:
                    yield chunk
                if obj.get("done"):
                    return

    def chat(self, model: str, messages: list[dict], **kwargs) -> str:
        return "".join(self.chat_stream(model, messages, **kwargs))

    def pull(self, model: str, progress: Callable[[dict], None] | None = None, timeout: int = 3600):
        with requests.post(
            f"{self.base_url}/api/pull",
            json={"name": model, "stream": True},
            stream=True,
            timeout=(10, timeout),
        ) as r:
            r.raise_for_status()
            for line in r.iter_lines():
                if not line:
                    continue
                obj = json.loads(line.decode("utf-8"))
                if progress:
                    progress(obj)
                if obj.get("status") == "success":
                    return

    def delete(self, model: str):
        r = requests.delete(f"{self.base_url}/api/delete", json={"name": model}, timeout=30)
        r.raise_for_status()

    def running(self) -> list[dict]:
        try:
            r = requests.get(f"{self.base_url}/api/ps", timeout=4)
            r.raise_for_status()
            return r.json().get("models", [])
        except requests.RequestException:
            return []
