# ZeroGPT

**ZeroGPT** is a Windows-first desktop AI workspace designed to run chat, vision, and image generation locally on your own machine.

## ZeroGPT 1.0

### Chat
- Ollama-powered local chat
- Streaming responses
- Stop and regenerate controls
- Copy last response
- Persistent SQLite conversation history
- Searchable chats
- Markdown, code blocks, and tables
- Image attachments for vision-capable Ollama models
- Select any installed Ollama model
- Configurable system prompt, temperature, and context window

### Local Image Studio
- ComfyUI API backend
- Text-to-image generation
- Negative prompts
- Multiple aspect ratios
- Steps, CFG, seed, and checkpoint controls
- Persistent generation gallery
- Import local `.safetensors`, `.ckpt`, and `.pt` checkpoints
- Default SDXL Turbo setup

### Model Manager
- View installed Ollama models and sizes
- Download additional Ollama models by name
- Delete models locally
- View/import ComfyUI checkpoints
- Hardware-aware model recommendations

### Setup and privacy
- One-click `Install_ZeroGPT.bat` app bootstrap
- In-app **Install / Repair Local AI** workflow
- Automatically installs/starts Ollama
- Automatically downloads the default chat model
- Automatically downloads the official ComfyUI Windows portable runtime
- Automatically downloads the default image checkpoint
- Runtime status indicators for Ollama and ComfyUI
- Data lives under `%USERPROFILE%\.zerogpt`
- After required models are downloaded, normal inference runs locally

## Windows quick start

1. Clone or download this repository.
2. Double-click `Install_ZeroGPT.bat`.
3. ZeroGPT launches automatically.
4. Click **Install / Repair Local AI** inside the app.
5. Leave the setup page open until it reports that everything is ready.

Large model/runtime downloads can require many gigabytes of free disk space.

## Build the EXE

After running the installer once, double-click:

```text
Build_ZeroGPT.bat
```

The Windows build will be written to:

```text
dist\ZeroGPT\ZeroGPT.exe
```

## Local data layout

```text
%USERPROFILE%\.zerogpt\
  zerogpt.db
  attachments\
  generations\
  runtime\
    ComfyUI_windows_portable\
```

## Development

```powershell
py -3.12 -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
python app.py
```

## Backends

- **Ollama** provides local LLM and vision inference.
- **ComfyUI** provides local image-generation inference.
- **PySide6** provides the native Windows interface.
- **SQLite** stores chat history, settings, and generation metadata.

ZeroGPT does not require a hosted AI API for normal local inference. Optional downloads and initial setup naturally require an internet connection.
