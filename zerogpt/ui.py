import sys
from pathlib import Path

from PySide6.QtCore import QObject, QThread, QTimer, Signal, Qt
from PySide6.QtGui import QPixmap
from PySide6.QtWidgets import (
    QApplication, QComboBox, QFileDialog, QFrame, QHBoxLayout, QLabel, QListWidget,
    QMainWindow, QMessageBox, QPushButton, QProgressBar, QScrollArea, QSizePolicy,
    QStackedWidget, QTextEdit, QVBoxLayout, QWidget
)

from .comfy_client import ComfyClient
from .config import APP_NAME, APP_VERSION, DATA_DIR, DEFAULT_CHAT_MODEL
from .ollama_client import OllamaClient
from .setup_manager import SetupManager
from .storage import Storage


STYLE = """
QWidget { background:#171a19; color:#edf2ef; font-family:'Segoe UI'; font-size:14px; }
QMainWindow { background:#171a19; }
QFrame#sidebar { background:#111413; border-right:1px solid #2a302d; }
QFrame#panel { background:#1d211f; border:1px solid #2a302d; border-radius:14px; }
QPushButton { background:#242a27; border:1px solid #343c38; border-radius:10px; padding:10px 14px; font-weight:600; }
QPushButton:hover { background:#2a312d; border-color:#55d98c; }
QPushButton#primary { background:#3ecf78; color:#07130c; border:0; }
QPushButton#primary:hover { background:#55dc8a; }
QPushButton#nav { text-align:left; background:transparent; border:0; padding:10px; }
QPushButton#nav:hover { background:#202521; }
QTextEdit, QComboBox, QListWidget { background:#111413; border:1px solid #303733; border-radius:10px; padding:8px; selection-background-color:#3ecf78; }
QListWidget::item { padding:9px; border-radius:8px; }
QListWidget::item:selected { background:#263129; color:white; }
QProgressBar { background:#101311; border:1px solid #303733; border-radius:7px; text-align:center; }
QProgressBar::chunk { background:#3ecf78; border-radius:6px; }
QScrollArea { border:0; }
"""


class Worker(QObject):
    done = Signal(object)
    error = Signal(str)
    log = Signal(str)

    def __init__(self, fn):
        super().__init__()
        self.fn = fn

    def run(self):
        try:
            self.done.emit(self.fn())
        except Exception as e:
            self.error.emit(str(e))


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle(f"{APP_NAME} {APP_VERSION}")
        self.resize(1360, 860)
        self.setMinimumSize(1050, 680)
        self.storage = Storage()
        self.ollama = OllamaClient()
        self.comfy = ComfyClient()
        self.current_chat = None
        self._threads = []
        self._pulse = 0
        self._build()
        self._refresh_chats()
        self._status_timer = QTimer(self)
        self._status_timer.timeout.connect(self.refresh_status)
        self._status_timer.start(4000)
        self._anim_timer = QTimer(self)
        self._anim_timer.timeout.connect(self._animate_accent)
        self._anim_timer.start(700)
        self.refresh_status()

    def _build(self):
        root = QWidget(); self.setCentralWidget(root)
        outer = QHBoxLayout(root); outer.setContentsMargins(0,0,0,0); outer.setSpacing(0)

        sidebar = QFrame(); sidebar.setObjectName("sidebar"); sidebar.setFixedWidth(265)
        sl = QVBoxLayout(sidebar); sl.setContentsMargins(16,18,16,18); sl.setSpacing(10)
        logo = QLabel("ZeroGPT"); logo.setStyleSheet("font-size:27px;font-weight:800;color:#63e69a;padding:4px 5px 14px 5px;")
        sl.addWidget(logo)
        new_btn = QPushButton("＋  New chat"); new_btn.setObjectName("primary"); new_btn.clicked.connect(self.new_chat); sl.addWidget(new_btn)
        self.chat_list = QListWidget(); self.chat_list.itemClicked.connect(self.load_selected_chat); sl.addWidget(self.chat_list,1)
        self.install_btn = QPushButton("⬇  Install Local AI"); self.install_btn.setObjectName("primary"); self.install_btn.clicked.connect(self.install_local_ai); sl.addWidget(self.install_btn)
        self.status = QLabel("Checking local engines…"); self.status.setWordWrap(True); self.status.setStyleSheet("color:#98a49e;font-size:12px;padding:4px;"); sl.addWidget(self.status)
        outer.addWidget(sidebar)

        main = QWidget(); ml = QVBoxLayout(main); ml.setContentsMargins(26,20,26,24); ml.setSpacing(14)
        top = QHBoxLayout()
        title = QLabel("Private AI on your machine"); title.setStyleSheet("font-size:20px;font-weight:700;"); top.addWidget(title)
        top.addStretch()
        self.mode_chat = QPushButton("Chat"); self.mode_img = QPushButton("Images")
        self.mode_chat.clicked.connect(lambda:self.pages.setCurrentIndex(0)); self.mode_img.clicked.connect(lambda:self.pages.setCurrentIndex(1))
        top.addWidget(self.mode_chat); top.addWidget(self.mode_img)
        self.model_box = QComboBox(); self.model_box.setMinimumWidth(190); self.model_box.addItem(DEFAULT_CHAT_MODEL); top.addWidget(self.model_box)
        ml.addLayout(top)

        self.pages = QStackedWidget(); ml.addWidget(self.pages,1)
        self.pages.addWidget(self._chat_page())
        self.pages.addWidget(self._image_page())
        outer.addWidget(main,1)

    def _chat_page(self):
        page = QWidget(); l = QVBoxLayout(page); l.setContentsMargins(0,0,0,0); l.setSpacing(12)
        self.transcript = QTextEdit(); self.transcript.setReadOnly(True); self.transcript.setPlaceholderText("Start a new chat. Everything stays on this PC.")
        l.addWidget(self.transcript,1)
        row = QHBoxLayout(); self.input = QTextEdit(); self.input.setFixedHeight(92); self.input.setPlaceholderText("Ask anything…")
        send = QPushButton("Send  ➜"); send.setObjectName("primary"); send.setFixedWidth(120); send.clicked.connect(self.send_message)
        row.addWidget(self.input,1); row.addWidget(send); l.addLayout(row)
        return page

    def _image_page(self):
        page = QWidget(); l = QVBoxLayout(page); l.setContentsMargins(0,0,0,0); l.setSpacing(12)
        hero = QFrame(); hero.setObjectName("panel"); hl = QVBoxLayout(hero)
        h = QLabel("Local Image Studio"); h.setStyleSheet("font-size:22px;font-weight:800;color:#66e89d;"); hl.addWidget(h)
        d = QLabel("Generate images through your local ComfyUI engine. After setup, no cloud service is required."); d.setStyleSheet("color:#aab5af;"); d.setWordWrap(True); hl.addWidget(d); l.addWidget(hero)
        self.image_prompt = QTextEdit(); self.image_prompt.setFixedHeight(110); self.image_prompt.setPlaceholderText("Describe the image you want…"); l.addWidget(self.image_prompt)
        gen = QPushButton("Generate image"); gen.setObjectName("primary"); gen.clicked.connect(self.generate_image); l.addWidget(gen)
        self.image_label = QLabel("Your generated image will appear here"); self.image_label.setAlignment(Qt.AlignCenter); self.image_label.setMinimumHeight(360); self.image_label.setStyleSheet("background:#111413;border:1px solid #303733;border-radius:14px;color:#748078;"); l.addWidget(self.image_label,1)
        return page

    def _run_worker(self, fn, on_done=None, on_error=None):
        thread = QThread(self); worker = Worker(fn); worker.moveToThread(thread)
        thread.started.connect(worker.run)
        worker.done.connect(lambda value: on_done(value) if on_done else None)
        worker.error.connect(lambda msg: on_error(msg) if on_error else QMessageBox.critical(self,"ZeroGPT",msg))
        worker.done.connect(thread.quit); worker.error.connect(thread.quit); worker.done.connect(worker.deleteLater); worker.error.connect(worker.deleteLater)
        thread.finished.connect(thread.deleteLater); thread.finished.connect(lambda:self._threads.remove(thread) if thread in self._threads else None)
        self._threads.append(thread); thread.start()

    def _refresh_chats(self):
        self.chat_list.clear()
        for cid, title in self.storage.chats():
            self.chat_list.addItem(f"{cid}  ·  {title}")

    def new_chat(self):
        self.current_chat = self.storage.new_chat(); self.transcript.clear(); self.input.clear(); self.pages.setCurrentIndex(0); self._refresh_chats()

    def load_selected_chat(self, item):
        self.current_chat = int(item.text().split("  ·  ")[0]); self.transcript.clear()
        for m in self.storage.messages(self.current_chat):
            self.transcript.append(f"<b>{'You' if m['role']=='user' else 'ZeroGPT'}</b><br>{m['content']}<br><br>")
        self.pages.setCurrentIndex(0)

    def send_message(self):
        text = self.input.toPlainText().strip()
        if not text: return
        if self.current_chat is None: self.current_chat = self.storage.new_chat(text[:42])
        self.storage.add_message(self.current_chat,"user",text); self.transcript.append(f"<b>You</b><br>{text}<br><br>"); self.input.clear(); self._refresh_chats()
        model = self.model_box.currentText() or DEFAULT_CHAT_MODEL
        messages = self.storage.messages(self.current_chat)
        self._run_worker(lambda:self.ollama.chat(model,messages), self._chat_done)

    def _chat_done(self, text):
        self.storage.add_message(self.current_chat,"assistant",text); self.transcript.append(f"<b style='color:#63e69a'>ZeroGPT</b><br>{text}<br><br>")

    def generate_image(self):
        prompt = self.image_prompt.toPlainText().strip()
        if not prompt: return
        self.image_label.setText("Generating locally…")
        self._run_worker(lambda:self.comfy.generate(prompt), self._image_done)

    def _image_done(self, data):
        out = DATA_DIR / "last_generated.png"; out.write_bytes(data)
        pix = QPixmap(); pix.loadFromData(data); self.image_label.setPixmap(pix.scaled(self.image_label.size(), Qt.KeepAspectRatio, Qt.SmoothTransformation))

    def install_local_ai(self):
        self.install_btn.setEnabled(False); self.install_btn.setText("Installing local AI…")
        self.setup_log = QTextEdit(); self.setup_log.setWindowTitle("ZeroGPT Setup"); self.setup_log.resize(760,480); self.setup_log.show()
        def log(msg): self.setup_log.append(str(msg))
        manager = SetupManager(log)
        self._run_worker(manager.install_everything, lambda _ : self._setup_done(), lambda msg:self._setup_failed(msg))

    def _setup_done(self):
        self.install_btn.setEnabled(True); self.install_btn.setText("✓ Local AI installed"); self.refresh_status(); QMessageBox.information(self,"ZeroGPT","Local AI setup is complete. ZeroGPT can now work offline.")

    def _setup_failed(self, msg):
        self.install_btn.setEnabled(True); self.install_btn.setText("⬇  Install Local AI"); QMessageBox.critical(self,"Setup failed",msg)

    def refresh_status(self):
        o = self.ollama.available(); c = self.comfy.available(); self.status.setText(f"● Ollama {'online' if o else 'offline'}   •   ComfyUI {'online' if c else 'offline'}")
        if o:
            try:
                names = self.ollama.models(); current = self.model_box.currentText(); self.model_box.clear(); self.model_box.addItems(names or [DEFAULT_CHAT_MODEL]);
                if current in names: self.model_box.setCurrentText(current)
            except Exception: pass

    def _animate_accent(self):
        self._pulse = 1 - self._pulse
        c = "#67e89d" if self._pulse else "#48d982"
        self.install_btn.setStyleSheet(f"QPushButton{{background:{c};color:#07130c;border:0;border-radius:10px;padding:10px 14px;font-weight:700;}}")


def run_app():
    app = QApplication(sys.argv); app.setApplicationName(APP_NAME); app.setStyleSheet(STYLE)
    w = MainWindow(); w.show(); sys.exit(app.exec())
