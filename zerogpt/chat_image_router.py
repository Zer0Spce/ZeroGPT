import html
import re
import time
from pathlib import Path

import markdown
from PySide6.QtGui import QPixmap
from PySide6.QtWidgets import QApplication, QMessageBox
from PySide6.QtCore import QTimer, Qt

from .config import DEFAULT_CHAT_MODEL, DEFAULT_IMAGE_MODEL, GENERATIONS_DIR


_IMAGE_PATTERNS = (
    r"\b(generate|create|make|draw|design|render|produce)\b.{0,40}\b(image|picture|photo|thumbnail|art|artwork|poster|wallpaper|logo|illustration)\b",
    r"\b(image|picture|photo|thumbnail|poster|wallpaper|logo|illustration)\b.{0,24}\b(of|for|showing|with)\b",
    r"\btext[- ]to[- ]image\b",
)


def is_image_request(text: str) -> bool:
    text = (text or "").strip().lower()
    if not text:
        return False
    return any(re.search(pattern, text, flags=re.I | re.S) for pattern in _IMAGE_PATTERNS)


def _dimensions_for(text: str) -> tuple[int, int]:
    t = (text or "").lower()
    if any(k in t for k in ("youtube thumbnail", "thumbnail", "16:9", "landscape", "widescreen")):
        return 1344, 768
    if any(k in t for k in ("9:16", "tiktok", "reel", "shorts", "portrait", "vertical")):
        return 768, 1344
    if "4:5" in t:
        return 896, 1152
    return 1024, 1024


def install_chat_image_routing(MainWindow):
    """Patch ZeroGPT's main window so image requests in Chat route to ComfyUI."""
    original_send = MainWindow.send_message
    original_ollama_messages = MainWindow._ollama_messages

    def message_html(self, role, content, attachment=None):
        who = "You" if role == "user" else "ZeroGPT"
        cls = "user" if role == "user" else "assistant"
        body = (
            markdown.markdown(content or "", extensions=["fenced_code", "tables"])
            if role == "assistant"
            else html.escape(content or "").replace("\n", "<br>")
        )
        extra = ""
        if attachment:
            p = Path(attachment)
            if role == "assistant" and p.exists() and p.suffix.lower() in {".png", ".jpg", ".jpeg", ".webp", ".bmp"}:
                try:
                    uri = p.resolve().as_uri()
                    extra = (
                        f"<div class='generated'><img src='{html.escape(uri)}' width='720'><br>"
                        f"<span>✦ {html.escape(p.name)}</span></div>"
                    )
                except Exception:
                    extra = f"<div class='attach'>📎 {html.escape(p.name)}</div>"
            else:
                extra = f"<div class='attach'>📎 {html.escape(p.name)}</div>"
        return f"<div class='m {cls}'><div class='who'>{who}</div>{body}{extra}</div>"

    def ollama_messages(self):
        # Generated assistant images are displayed in chat but are not sent back as
        # assistant-role vision inputs, which some Ollama models reject.
        s = self.storage.defaults()
        msgs = [{"role": "system", "content": s["system_prompt"]}]
        for m in self.storage.messages(self.current_chat):
            x = {"role": m["role"], "content": m["content"]}
            if m.get("attachment") and m["role"] == "user":
                try:
                    x["images"] = [self.ollama.encode_image(m["attachment"])]
                except Exception:
                    pass
            msgs.append(x)
        return msgs, s

    def finish_image_controls(self):
        self.send_btn.setEnabled(True)
        self.stop_btn.hide()
        self.stop_btn.setText("■ Stop")

    def send_image_request(self, text: str):
        if self._active_worker:
            return
        if not self.comfy.available():
            QMessageBox.warning(
                self,
                "ComfyUI offline",
                "This is an image-generation request, but the local image engine is not running. "
                "Use Install / Repair Local AI, then try again.",
            )
            return

        if self.current_chat is None:
            self.current_chat = self.storage.new_chat((text or "Image generation")[:48])

        user_attachment = self.attached_image
        self.storage.add_message(self.current_chat, "user", text, user_attachment)
        self.input.clear()
        self.attached_image = None
        self.attachment_label.hide()
        self._refresh_chats()

        width, height = _dimensions_for(text)
        model = self.image_model_box.currentText() or DEFAULT_IMAGE_MODEL
        negative = self.negative_prompt.toPlainText().strip() if hasattr(self, "negative_prompt") else "low quality, blurry, distorted, artifacts"
        steps = self.steps.value() if hasattr(self, "steps") else 4
        cfg = self.cfg.value() if hasattr(self, "cfg") else 1.0

        self._stream_text = f"Generating image locally at {width} × {height}…"
        self._render_chat(self._stream_text)
        self.send_btn.setEnabled(False)
        self.stop_btn.setText("■ Stop")
        self.stop_btn.show()

        # The user-facing request itself is intentionally kept as the generation
        # prompt. This avoids a second LLM call and keeps image creation fully local.
        prompt = text

        def task(worker):
            return self.comfy.generate(
                prompt,
                negative=negative,
                width=width,
                height=height,
                model=model,
                steps=steps,
                cfg=cfg,
                seed=None,
                cancel=lambda: worker.cancelled,
            )

        def done(value):
            data, used_seed = value
            out = GENERATIONS_DIR / f"zerogpt_chat_{int(time.time() * 1000)}_{used_seed}.png"
            out.write_bytes(data)
            self.storage.add_generation(
                path=str(out), prompt=prompt, negative=negative, model=model,
                width=width, height=height, seed=used_seed,
            )
            self.storage.add_message(
                self.current_chat,
                "assistant",
                f"Generated locally • {width}×{height} • seed {used_seed}",
                str(out),
            )
            self._stream_text = ""
            self._render_chat()
            finish_image_controls(self)
            self._refresh_gallery()
            try:
                pix = QPixmap(str(out))
                if not pix.isNull():
                    self.image_label.setPixmap(
                        pix.scaled(self.image_label.size(), Qt.KeepAspectRatio, Qt.SmoothTransformation)
                    )
            except Exception:
                pass

        def failed(msg):
            self._stream_text = ""
            self._render_chat()
            finish_image_controls(self)
            QMessageBox.critical(self, "Image generation", msg)

        self._run_task(task, on_done=done, on_error=failed)

    def send_message(self):
        text = self.input.toPlainText().strip()
        if text and is_image_request(text):
            return send_image_request(self, text)
        return original_send(self)

    MainWindow._message_html = message_html
    MainWindow._ollama_messages = ollama_messages
    MainWindow.send_message = send_message
