import sys
from pathlib import Path

APP_NAME = "ZeroGPT"
APP_VERSION = "1.0.2"

ROOT = Path(__file__).resolve().parents[1]

# Portable releases keep all ZeroGPT-owned data beside ZeroGPT.exe.
# Source/development runs continue using the user's home folder.
if getattr(sys, "frozen", False):
    APP_DIR = Path(sys.executable).resolve().parent
    DATA_DIR = APP_DIR / "ZeroGPT_Data"
else:
    APP_DIR = ROOT
    DATA_DIR = Path.home() / ".zerogpt"

RUNTIME_DIR = DATA_DIR / "runtime"
GENERATIONS_DIR = DATA_DIR / "generations"
ATTACHMENTS_DIR = DATA_DIR / "attachments"
for _path in (DATA_DIR, RUNTIME_DIR, GENERATIONS_DIR, ATTACHMENTS_DIR):
    _path.mkdir(parents=True, exist_ok=True)

DB_PATH = DATA_DIR / "zerogpt.db"
OLLAMA_URL = "http://127.0.0.1:11434"
COMFY_URL = "http://127.0.0.1:8188"

DEFAULT_CHAT_MODEL = "gemma3:4b"
DEFAULT_VISION_MODEL = "gemma3:4b"
DEFAULT_IMAGE_MODEL = "sd_xl_turbo_1.0_fp16.safetensors"
DEFAULT_IMAGE_URL = (
    "https://huggingface.co/stabilityai/sdxl-turbo/resolve/main/"
    "sd_xl_turbo_1.0_fp16.safetensors?download=true"
)

DEFAULT_SYSTEM_PROMPT = (
    "You are ZeroGPT, a capable local AI assistant running privately on the user's computer. "
    "Be useful, concise when possible, and clear about uncertainty."
)
