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

    def models(self) -> list[str]:
        r = requests.get(f"{self.base_url}/api/tags", timeout=5)
        r.raise_for_status()
        return [m.get("name", "") for m in r.json().get("models", []) if m.get("name")]

    def chat(self, model: str, messages: list[dict], timeout: int = 600) -> str:
        r = requests.post(
            f"{self.base_url}/api/chat",
            json={"model": model, "messages": messages, "stream": False},
            timeout=timeout,
        )
        r.raise_for_status()
        return r.json().get("message", {}).get("content", "")
