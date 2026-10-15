from pathlib import Path

APP_NAME = "ZeroGPT"
APP_VERSION = "0.1.0"
ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = Path.home() / ".zerogpt"
DATA_DIR.mkdir(parents=True, exist_ok=True)
DB_PATH = DATA_DIR / "zerogpt.db"
RUNTIME_DIR = DATA_DIR / "runtime"
RUNTIME_DIR.mkdir(parents=True, exist_ok=True)
OLLAMA_URL = "http://127.0.0.1:11434"
COMFY_URL = "http://127.0.0.1:8188"
DEFAULT_CHAT_MODEL = "gemma3:4b"
DEFAULT_IMAGE_MODEL = "sd_xl_turbo_1.0_fp16.safetensors"
DEFAULT_IMAGE_URL = "https://huggingface.co/stabilityai/sdxl-turbo/resolve/main/sd_xl_turbo_1.0_fp16.safetensors?download=true"
