# ZeroGPT

**ZeroGPT** is a Windows-first desktop AI workspace designed to run chat, vision, and image generation locally on your own machine.

## ZeroGPT 1.0.1 Portable

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

### Portable release behavior
- No installer is required for the built ZeroGPT application.
- The build output is an unpacked `ZeroGPT-Portable` folder.
- The same folder is also packaged automatically as `ZeroGPT-Portable.zip`.
- Run `ZeroGPT.exe` directly from the extracted folder.
- Chats, settings, generated images, attachments, and ZeroGPT's downloaded ComfyUI runtime live in `ZeroGPT_Data` beside the EXE.
- The entire portable folder can be moved or copied as one unit.
- Initial AI runtime/model downloads still require internet access.

## Source/development quick start

1. Clone or download this repository.
2. Double-click `Install_ZeroGPT.bat` to prepare the Python build environment.
3. Launch ZeroGPT.
4. Click **Install / Repair Local AI** inside the app if Ollama/ComfyUI/models are not ready.

Large model/runtime downloads can require many gigabytes of free disk space.

## Build the portable release

After preparing the development environment once, double-click:

```text
Build_ZeroGPT.bat
```

It produces both:

```text
release\ZeroGPT-Portable\
release\ZeroGPT-Portable.zip
```

The unpacked folder contains `ZeroGPT.exe` and all application dependencies required by the PyInstaller build.

## Portable data layout

```text
ZeroGPT-Portable\
  ZeroGPT.exe
  README-PORTABLE.txt
  _internal\
  ZeroGPT_Data\
    zerogpt.db
    attachments\
    generations\
    runtime\
      ComfyUI_windows_portable\
```

`ZeroGPT_Data` is created automatically on first run.

When running from source instead of the frozen EXE, development data continues to use `%USERPROFILE%\.zerogpt`.

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
