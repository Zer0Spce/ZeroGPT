import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path

import psutil


@dataclass
class HardwareInfo:
    cpu: str
    ram_gb: float
    gpu: str
    vram_gb: float
    disk_free_gb: float


def detect_hardware() -> HardwareInfo:
    import platform
    cpu = platform.processor() or platform.uname().processor or "Unknown CPU"
    ram = psutil.virtual_memory().total / (1024 ** 3)
    disk = psutil.disk_usage(str(Path.home())).free / (1024 ** 3)
    gpu = "No NVIDIA GPU detected"
    vram = 0.0
    if shutil.which("nvidia-smi"):
        try:
            out = subprocess.check_output(["nvidia-smi","--query-gpu=name,memory.total","--format=csv,noheader,nounits"], text=True, creationflags=getattr(subprocess,"CREATE_NO_WINDOW",0), timeout=5).strip().splitlines()[0]
            name, mem = [x.strip() for x in out.rsplit(",",1)]
            gpu = name; vram = float(mem) / 1024
        except Exception:
            pass
    return HardwareInfo(cpu, ram, gpu, vram, disk)


def recommended_models(info: HardwareInfo) -> list[tuple[str,str]]:
    if info.vram_gb >= 20 or info.ram_gb >= 32:
        return [("qwen3:14b","High quality"),("gemma3:12b","Vision"),("qwen3:8b","Fast")]
    if info.vram_gb >= 10 or info.ram_gb >= 24:
        return [("qwen3:8b","Balanced"),("gemma3:4b","Vision"),("qwen3:4b","Fast")]
    return [("gemma3:4b","Balanced + vision"),("qwen3:4b","General"),("qwen3:1.7b","Low memory")]
