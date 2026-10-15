# ZeroGPT

**ZeroGPT** is a Windows-first local AI desktop application for private on-device chat and image generation.

## v0.1 foundation

- Clean dark gray + green PySide6 interface
- Local chat through Ollama
- Local image generation through ComfyUI
- SQLite conversation history
- Model selector
- Chat and Image Studio modes
- One-click **Install Local AI** setup inside the application
- Automatic Ollama installation and default model pull
- Automatic ComfyUI Windows portable download/extraction
- Automatic SDXL Turbo checkpoint download
- Animated green UI accents and engine status indicators
- Windows bootstrap and PyInstaller build scripts

## Quick start

1. Clone/download this repository on Windows 10/11.
2. Double-click `Install_ZeroGPT.bat`.
3. When ZeroGPT opens, click **Install Local AI**.
4. Leave the setup window open until it reports completion.
5. Chat and generate images locally. Internet is only needed for the initial downloads.

The initial AI downloads are several gigabytes. Their exact size depends on upstream Ollama/ComfyUI packages and models.

## Development

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
python app.py
```

Build a Windows app folder with:

```bat
Build_ZeroGPT.bat
```

## Local data

ZeroGPT stores conversations, runtime components, and generated output under `%USERPROFILE%\.zerogpt`.

## Backends

- Ollama API: `http://127.0.0.1:11434`
- ComfyUI API: `http://127.0.0.1:8188`

ZeroGPT is designed so normal inference can operate locally after setup.
