import html
import shutil
import sys
import time
from pathlib import Path

import markdown
from PySide6.QtCore import QObject, QThread, QTimer, Signal, Qt, QSize
from PySide6.QtGui import QIcon, QPixmap
from PySide6.QtWidgets import (QApplication,QComboBox,QDoubleSpinBox,QFileDialog,QFormLayout,QFrame,QHBoxLayout,QLabel,QLineEdit,QListWidget,QListWidgetItem,QMainWindow,QMessageBox,QPushButton,QProgressBar,QScrollArea,QSpinBox,QStackedWidget,QTextBrowser,QTextEdit,QVBoxLayout,QWidget)

from .comfy_client import ComfyClient
from .config import APP_NAME,APP_VERSION,ATTACHMENTS_DIR,DEFAULT_CHAT_MODEL,DEFAULT_IMAGE_MODEL,GENERATIONS_DIR,RUNTIME_DIR
from .hardware import detect_hardware,recommended_models
from .ollama_client import OllamaClient
from .setup_manager import SetupManager
from .storage import Storage

STYLE='''
*{font-family:"Segoe UI";font-size:14px} QWidget{background:#171a19;color:#edf2ef} QMainWindow{background:#171a19}
QFrame#sidebar{background:#111413;border-right:1px solid #2b312e} QFrame#panel,QFrame#card{background:#1d211f;border:1px solid #2d3430;border-radius:14px}
QFrame#composer{background:#111413;border:1px solid #343c38;border-radius:16px}
QPushButton{background:#242a27;border:1px solid #343c38;border-radius:10px;padding:9px 14px;font-weight:600} QPushButton:hover{background:#2c332f;border-color:#55d98c} QPushButton:disabled{color:#6e7873;background:#1b1e1d;border-color:#272c29}
QPushButton#primary{background:#42d77d;color:#07130c;border:0;font-weight:750} QPushButton#primary:hover{background:#61e699} QPushButton#danger{color:#ffb3b3}
QPushButton#nav{text-align:left;background:transparent;border:0;padding:10px 11px} QPushButton#nav:hover{background:#202521} QPushButton#nav[active="true"]{background:#263029;color:#6be8a0}
QLineEdit,QTextEdit,QTextBrowser,QComboBox,QListWidget,QSpinBox,QDoubleSpinBox{background:#111413;border:1px solid #303733;border-radius:10px;padding:8px;selection-background-color:#42d77d}
QTextBrowser{padding:14px} QListWidget::item{padding:8px;border-radius:8px} QListWidget::item:selected{background:#27322b;color:white}
QProgressBar{background:#101311;border:1px solid #303733;border-radius:7px;text-align:center;min-height:16px} QProgressBar::chunk{background:#42d77d;border-radius:6px} QScrollArea{border:0}
'''

class TaskWorker(QObject):
    result=Signal(object); error=Signal(str); chunk=Signal(str); progress=Signal(int,str); log=Signal(str); finished=Signal()
    def __init__(self,fn): super().__init__(); self.fn=fn; self.cancelled=False
    def cancel(self): self.cancelled=True
    def run(self):
        try: self.result.emit(self.fn(self))
        except Exception as exc: self.error.emit(str(exc))
        finally: self.finished.emit()

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__(); self.setWindowTitle(f"{APP_NAME} {APP_VERSION}"); self.resize(1450,900); self.setMinimumSize(1120,720)
        self.storage=Storage(); self.ollama=OllamaClient(); self.comfy=ComfyClient(); self.current_chat=None; self.attached_image=None; self._threads=[]; self._active_worker=None; self._stream_text=""; self._pulse=False
        self._build(); self._refresh_chats(); self._refresh_gallery(); self._load_settings(); self.refresh_status()
        self.status_timer=QTimer(self); self.status_timer.timeout.connect(self.refresh_status); self.status_timer.start(5000)
        self.anim_timer=QTimer(self); self.anim_timer.timeout.connect(self._animate); self.anim_timer.start(900)

    def _build(self):
        root=QWidget(); self.setCentralWidget(root); outer=QHBoxLayout(root); outer.setContentsMargins(0,0,0,0); outer.setSpacing(0)
        sidebar=QFrame(); sidebar.setObjectName("sidebar"); sidebar.setFixedWidth(280); sl=QVBoxLayout(sidebar); sl.setContentsMargins(16,18,16,18); sl.setSpacing(8)
        self.logo=QLabel("ZeroGPT"); self.logo.setStyleSheet("font-size:28px;font-weight:850;color:#63e69a;padding:4px 5px 8px 5px;"); sl.addWidget(self.logo)
        sub=QLabel("LOCAL • PRIVATE • YOUR MACHINE"); sub.setStyleSheet("color:#77827c;font-size:10px;font-weight:700;padding-left:6px;padding-bottom:9px;"); sl.addWidget(sub)
        b=QPushButton("＋  New chat"); b.setObjectName("primary"); b.clicked.connect(self.new_chat); sl.addWidget(b)
        self.search=QLineEdit(); self.search.setPlaceholderText("Search chats…"); self.search.textChanged.connect(self._refresh_chats); sl.addWidget(self.search)
        self.chat_list=QListWidget(); self.chat_list.itemClicked.connect(self.load_selected_chat); sl.addWidget(self.chat_list,1)
        self.nav_chat=self._nav("💬  Chat",0); self.nav_images=self._nav("✦  Image Studio",1); self.nav_models=self._nav("◫  Models",2); self.nav_settings=self._nav("⚙  Settings",3)
        for x in (self.nav_chat,self.nav_images,self.nav_models,self.nav_settings): sl.addWidget(x)
        self.install_btn=QPushButton("↓  Install / Repair Local AI"); self.install_btn.setObjectName("primary"); self.install_btn.clicked.connect(self.install_local_ai); sl.addWidget(self.install_btn)
        self.status=QLabel("Checking local engines…"); self.status.setWordWrap(True); self.status.setStyleSheet("color:#8b9891;font-size:11px;padding:6px;"); sl.addWidget(self.status); outer.addWidget(sidebar)
        main=QWidget(); ml=QVBoxLayout(main); ml.setContentsMargins(24,18,24,22); ml.setSpacing(12); top=QHBoxLayout(); self.page_title=QLabel("Chat"); self.page_title.setStyleSheet("font-size:20px;font-weight:750;"); top.addWidget(self.page_title); top.addStretch(); self.model_box=QComboBox(); self.model_box.setMinimumWidth(220); self.model_box.addItem(DEFAULT_CHAT_MODEL); self.model_box.currentTextChanged.connect(lambda v:self.storage.set_setting("chat_model",v) if v else None); top.addWidget(QLabel("Model")); top.addWidget(self.model_box); ml.addLayout(top)
        self.pages=QStackedWidget(); self.pages.addWidget(self._chat_page()); self.pages.addWidget(self._image_page()); self.pages.addWidget(self._models_page()); self.pages.addWidget(self._settings_page()); self.pages.currentChanged.connect(self._page_changed); ml.addWidget(self.pages,1); outer.addWidget(main,1); self._page_changed(0)

    def _nav(self,text,index):
        b=QPushButton(text); b.setObjectName("nav"); b.clicked.connect(lambda:self.pages.setCurrentIndex(index)); return b
    def _page_changed(self,index):
        self.page_title.setText(["Chat","Image Studio","Model Manager","Settings & Setup"][index])
        for i,b in enumerate((self.nav_chat,self.nav_images,self.nav_models,self.nav_settings)):
            b.setProperty("active",i==index); b.style().unpolish(b); b.style().polish(b)
        if index==2:self.refresh_models()
        if index==3:self.refresh_hardware()

    def _chat_page(self):
        p=QWidget(); l=QVBoxLayout(p); l.setContentsMargins(0,0,0,0); l.setSpacing(10); tools=QHBoxLayout(); self.chat_hint=QLabel("Everything in this chat stays on this PC."); self.chat_hint.setStyleSheet("color:#7e8b84;"); tools.addWidget(self.chat_hint); tools.addStretch(); r=QPushButton("↻ Regenerate"); r.clicked.connect(self.regenerate); c=QPushButton("Copy last"); c.clicked.connect(self.copy_last); tools.addWidget(r); tools.addWidget(c); l.addLayout(tools)
        self.transcript=QTextBrowser(); self.transcript.setOpenExternalLinks(True); self.transcript.setPlaceholderText("Start a conversation with your local model."); l.addWidget(self.transcript,1)
        self.attachment_label=QLabel(""); self.attachment_label.setStyleSheet("color:#67dfa0;font-size:12px;padding-left:8px;"); self.attachment_label.hide(); l.addWidget(self.attachment_label)
        f=QFrame(); f.setObjectName("composer"); row=QHBoxLayout(f); row.setContentsMargins(10,10,10,10); a=QPushButton("＋ Image"); a.clicked.connect(self.attach_image); row.addWidget(a); self.input=QTextEdit(); self.input.setPlaceholderText("Message ZeroGPT…"); self.input.setFixedHeight(92); self.input.setStyleSheet("border:0;background:transparent;"); row.addWidget(self.input,1); self.stop_btn=QPushButton("■ Stop"); self.stop_btn.clicked.connect(self.stop_task); self.stop_btn.hide(); row.addWidget(self.stop_btn); self.send_btn=QPushButton("Send  ➜"); self.send_btn.setObjectName("primary"); self.send_btn.setFixedWidth(116); self.send_btn.clicked.connect(self.send_message); row.addWidget(self.send_btn); l.addWidget(f); return p

    def new_chat(self): self.current_chat=self.storage.new_chat(); self.attached_image=None; self.attachment_label.hide(); self.transcript.clear(); self.input.clear(); self._refresh_chats(); self.pages.setCurrentIndex(0)
    def _refresh_chats(self):
        q=self.search.text() if hasattr(self,"search") else ""; self.chat_list.clear()
        for row in self.storage.chats(q):
            it=QListWidgetItem(row["title"]); it.setData(Qt.UserRole,row["id"]); self.chat_list.addItem(it)
    def load_selected_chat(self,item): self.current_chat=int(item.data(Qt.UserRole)); self.pages.setCurrentIndex(0); self._render_chat()
    def _message_html(self,role,content,attachment=None):
        who="You" if role=="user" else "ZeroGPT"; cls="user" if role=="user" else "assistant"; body=markdown.markdown(content or "",extensions=["fenced_code","tables"]) if role=="assistant" else html.escape(content or "").replace("\n","<br>"); extra=f"<div class='attach'>📎 {html.escape(Path(attachment).name)}</div>" if attachment else ""; return f"<div class='m {cls}'><div class='who'>{who}</div>{body}{extra}</div>"
    def _render_chat(self,streaming=""):
        if self.current_chat is None:self.transcript.clear();return
        blocks=[self._message_html(m["role"],m["content"],m.get("attachment")) for m in self.storage.messages(self.current_chat)]
        if streaming:blocks.append(self._message_html("assistant",streaming+" ▌"))
        css="<style>body{font-family:'Segoe UI';color:#edf2ef;background:#111413}.m{margin:8px 0 16px;padding:13px 15px;border-radius:12px}.user{background:#26302b;margin-left:9%}.assistant{background:#1b201d;border:1px solid #2b332f;margin-right:5%}.who{font-size:11px;color:#69e49d;font-weight:700;margin-bottom:6px}code,pre{background:#0d100f}pre{padding:10px;border-radius:8px;white-space:pre-wrap}.attach{color:#89a094;font-size:11px;margin-top:7px}a{color:#69e49d}</style>"; self.transcript.setHtml(css+"".join(blocks)); self.transcript.verticalScrollBar().setValue(self.transcript.verticalScrollBar().maximum())
    def attach_image(self):
        path,_=QFileDialog.getOpenFileName(self,"Attach image","","Images (*.png *.jpg *.jpeg *.webp *.bmp)")
        if path:
            src=Path(path); dst=ATTACHMENTS_DIR/f"{int(time.time()*1000)}_{src.name}"; shutil.copy2(src,dst); self.attached_image=str(dst); self.attachment_label.setText(f"📎 Attached: {dst.name}"); self.attachment_label.show()
    def _ollama_messages(self):
        s=self.storage.defaults(); msgs=[{"role":"system","content":s["system_prompt"]}]
        for m in self.storage.messages(self.current_chat):
            x={"role":m["role"],"content":m["content"]}
            if m.get("attachment"):
                try:x["images"]=[self.ollama.encode_image(m["attachment"])]
                except Exception:pass
            msgs.append(x)
        return msgs,s
    def send_message(self):
        text=self.input.toPlainText().strip()
        if (not text and not self.attached_image) or self._active_worker:return
        if not self.ollama.available():QMessageBox.warning(self,"Ollama offline","Local chat is not running. Use Install / Repair Local AI.");return
        if self.current_chat is None:self.current_chat=self.storage.new_chat((text or "Image chat")[:48])
        att=self.attached_image; self.storage.add_message(self.current_chat,"user",text or "Describe this image.",att); self.input.clear(); self.attached_image=None; self.attachment_label.hide(); self._refresh_chats(); self._render_chat(); msgs,s=self._ollama_messages(); model=self.model_box.currentText() or DEFAULT_CHAT_MODEL; self._stream_text=""; self.send_btn.setEnabled(False); self.stop_btn.setText("■ Stop"); self.stop_btn.show()
        def task(w):
            for chunk in self.ollama.chat_stream(model,msgs,temperature=s["temperature"],num_ctx=s["num_ctx"],cancel=lambda:w.cancelled):w.chunk.emit(chunk)
        self._run_task(task,on_chunk=self._chat_chunk,on_done=self._chat_stream_done)
    def _chat_chunk(self,chunk): self._stream_text+=chunk; self._render_chat(self._stream_text)
    def _chat_stream_done(self,_):
        if self._stream_text.strip() and self.current_chat is not None:self.storage.add_message(self.current_chat,"assistant",self._stream_text.strip())
        self._stream_text=""; self._render_chat(); self._finish_chat_controls()
    def _finish_chat_controls(self): self.send_btn.setEnabled(True); self.stop_btn.hide(); self.stop_btn.setText("■ Stop")
    def regenerate(self):
        if self.current_chat is None or self._active_worker:return
        if not self.storage.messages(self.current_chat):return
        self.storage.delete_last_assistant(self.current_chat); self._render_chat(); payload,s=self._ollama_messages(); model=self.model_box.currentText() or DEFAULT_CHAT_MODEL; self._stream_text=""; self.send_btn.setEnabled(False); self.stop_btn.show()
        def task(w):
            for chunk in self.ollama.chat_stream(model,payload,temperature=s["temperature"],num_ctx=s["num_ctx"],cancel=lambda:w.cancelled):w.chunk.emit(chunk)
        self._run_task(task,on_chunk=self._chat_chunk,on_done=self._chat_stream_done)
    def copy_last(self):
        if self.current_chat is None:return
        a=next((m for m in reversed(self.storage.messages(self.current_chat)) if m["role"]=="assistant"),None)
        if a:QApplication.clipboard().setText(a["content"]);self.chat_hint.setText("Copied last response.");QTimer.singleShot(1800,lambda:self.chat_hint.setText("Everything in this chat stays on this PC."))

    def _image_page(self):
        p=QWidget(); l=QHBoxLayout(p); l.setContentsMargins(0,0,0,0); l.setSpacing(14); panel=QFrame(); panel.setObjectName("panel"); panel.setFixedWidth(365); v=QVBoxLayout(panel); h=QLabel("Local Image Studio"); h.setStyleSheet("font-size:20px;font-weight:800;color:#69e49d;"); v.addWidget(h); self.image_prompt=QTextEdit(); self.image_prompt.setPlaceholderText("Describe the image you want…"); self.image_prompt.setFixedHeight(120); v.addWidget(QLabel("Prompt"));v.addWidget(self.image_prompt);self.negative_prompt=QTextEdit();self.negative_prompt.setPlainText("low quality, blurry, distorted, artifacts");self.negative_prompt.setFixedHeight(70);v.addWidget(QLabel("Negative prompt"));v.addWidget(self.negative_prompt);self.image_model_box=QComboBox();self.image_model_box.addItem(DEFAULT_IMAGE_MODEL);v.addWidget(QLabel("Checkpoint"));v.addWidget(self.image_model_box);self.size_box=QComboBox();self.size_box.addItems(["1024 × 1024","896 × 1152","1152 × 896","768 × 1344","1344 × 768"]);v.addWidget(QLabel("Size"));v.addWidget(self.size_box);row=QHBoxLayout();self.steps=QSpinBox();self.steps.setRange(1,50);self.steps.setValue(4);self.cfg=QDoubleSpinBox();self.cfg.setRange(.5,20);self.cfg.setSingleStep(.5);self.cfg.setValue(1);row.addWidget(QLabel("Steps"));row.addWidget(self.steps);row.addWidget(QLabel("CFG"));row.addWidget(self.cfg);v.addLayout(row);self.seed=QLineEdit();self.seed.setPlaceholderText("Random seed");v.addWidget(QLabel("Seed (optional)"));v.addWidget(self.seed);self.generate_btn=QPushButton("✦  Generate locally");self.generate_btn.setObjectName("primary");self.generate_btn.clicked.connect(self.generate_image);v.addWidget(self.generate_btn);self.image_progress=QProgressBar();self.image_progress.setRange(0,0);self.image_progress.hide();v.addWidget(self.image_progress);v.addStretch();l.addWidget(panel)
        right=QVBoxLayout();self.image_label=QLabel("Your generated image will appear here");self.image_label.setAlignment(Qt.AlignCenter);self.image_label.setMinimumHeight(440);self.image_label.setStyleSheet("background:#111413;border:1px solid #303733;border-radius:14px;color:#748078;");right.addWidget(self.image_label,1);gh=QHBoxLayout();gh.addWidget(QLabel("Recent generations"));gh.addStretch();o=QPushButton("Open folder");o.clicked.connect(self.open_generations_folder);gh.addWidget(o);right.addLayout(gh);self.gallery=QListWidget();self.gallery.setViewMode(QListWidget.IconMode);self.gallery.setIconSize(QSize(96,96));self.gallery.setFixedHeight(145);self.gallery.itemClicked.connect(self.gallery_selected);right.addWidget(self.gallery);l.addLayout(right,1);return p
    def _parse_size(self):a,b=self.size_box.currentText().replace(" ","").split("×");return int(a),int(b)
    def generate_image(self):
        prompt=self.image_prompt.toPlainText().strip()
        if not prompt or self._active_worker:return
        if not self.comfy.available():QMessageBox.warning(self,"ComfyUI offline","Local image generation is not running. Use Install / Repair Local AI.");return
        width,height=self._parse_size(); model=self.image_model_box.currentText() or DEFAULT_IMAGE_MODEL; seed=None
        if self.seed.text().strip():
            try:seed=int(self.seed.text().strip())
            except ValueError:QMessageBox.warning(self,"Invalid seed","Seed must be an integer or blank.");return
        self.generate_btn.setEnabled(False);self.image_progress.show();self.image_label.setText("Generating locally…");negative=self.negative_prompt.toPlainText().strip();steps=self.steps.value();cfg=self.cfg.value()
        def task(w):return self.comfy.generate(prompt,negative=negative,width=width,height=height,model=model,steps=steps,cfg=cfg,seed=seed,cancel=lambda:w.cancelled)
        def done(value):
            data,used=value; out=GENERATIONS_DIR/f"zerogpt_{int(time.time()*1000)}_{used}.png";out.write_bytes(data);self.storage.add_generation(path=str(out),prompt=prompt,negative=negative,model=model,width=width,height=height,seed=used);pix=QPixmap(str(out));self.image_label.setPixmap(pix.scaled(self.image_label.size(),Qt.KeepAspectRatio,Qt.SmoothTransformation));self.seed.setText(str(used));self.generate_btn.setEnabled(True);self.image_progress.hide();self._refresh_gallery()
        self._run_task(task,on_done=done,on_error=self._image_error)
    def _image_error(self,msg):self.generate_btn.setEnabled(True);self.image_progress.hide();self.image_label.setText("Generation failed");QMessageBox.critical(self,"Image generation",msg)
    def _refresh_gallery(self):
        if not hasattr(self,"gallery"):return
        self.gallery.clear()
        for row in self.storage.generations(40):
            p=Path(row["path"])
            if p.exists():it=QListWidgetItem(QIcon(str(p)),p.name);it.setData(Qt.UserRole,str(p));it.setToolTip(row.get("prompt") or "");self.gallery.addItem(it)
    def gallery_selected(self,item):
        pix=QPixmap(item.data(Qt.UserRole))
        if not pix.isNull():self.image_label.setPixmap(pix.scaled(self.image_label.size(),Qt.KeepAspectRatio,Qt.SmoothTransformation))
    def open_generations_folder(self):
        import os; os.startfile(str(GENERATIONS_DIR))

    def _models_page(self):
        p=QWidget();l=QHBoxLayout(p);l.setContentsMargins(0,0,0,0);l.setSpacing(14);left=QFrame();left.setObjectName("panel");ll=QVBoxLayout(left);t=QLabel("Ollama chat models");t.setStyleSheet("font-size:18px;font-weight:750;");ll.addWidget(t);self.models_list=QListWidget();ll.addWidget(self.models_list,1);r=QHBoxLayout();self.pull_model_input=QLineEdit();self.pull_model_input.setPlaceholderText("e.g. qwen3:8b");b=QPushButton("Download");b.setObjectName("primary");b.clicked.connect(self.pull_model);r.addWidget(self.pull_model_input,1);r.addWidget(b);ll.addLayout(r);d=QPushButton("Delete selected model");d.setObjectName("danger");d.clicked.connect(self.delete_model);ll.addWidget(d);l.addWidget(left,1);right=QFrame();right.setObjectName("panel");rl=QVBoxLayout(right);t2=QLabel("Image checkpoints");t2.setStyleSheet("font-size:18px;font-weight:750;");rl.addWidget(t2);self.checkpoints_list=QListWidget();rl.addWidget(self.checkpoints_list,1);ib=QPushButton("Import checkpoint…");ib.clicked.connect(self.import_checkpoint);rl.addWidget(ib);note=QLabel("Checkpoint files are copied into ZeroGPT's local ComfyUI model folder. Model licenses and hardware requirements vary.");note.setWordWrap(True);note.setStyleSheet("color:#819087;font-size:12px;");rl.addWidget(note);l.addWidget(right,1);return p
    def refresh_models(self):
        try:models=self.ollama.models() if self.ollama.available() else []
        except Exception:models=[]
        self.models_list.clear()
        for m in models:
            name=m.get("name","Unknown");it=QListWidgetItem(f"{name}   ·   {m.get('size',0)/(1024**3):.1f} GB");it.setData(Qt.UserRole,name);self.models_list.addItem(it)
        names=[m.get("name") for m in models if m.get("name")];current=self.storage.get_setting("chat_model",self.model_box.currentText() or DEFAULT_CHAT_MODEL);self.model_box.blockSignals(True);self.model_box.clear();self.model_box.addItems(names or [DEFAULT_CHAT_MODEL]);
        if current in names:self.model_box.setCurrentText(current)
        self.model_box.blockSignals(False);checks=self.comfy.checkpoints();self.checkpoints_list.clear();self.checkpoints_list.addItems(checks);self.image_model_box.clear();self.image_model_box.addItems(checks)
    def pull_model(self):
        model=self.pull_model_input.text().strip()
        if not model or self._active_worker:return
        if not self.ollama.available():QMessageBox.warning(self,"Ollama offline","Install or start Ollama first.");return
        self.install_btn.setText(f"Downloading {model}…")
        def task(w):self.ollama.pull(model,progress=lambda obj:w.progress.emit(int(100*obj.get("completed",0)/max(1,obj.get("total",1))) if obj.get("total") else 0,obj.get("status","Downloading…")));return model
        def done(_):self.install_btn.setText("↓  Install / Repair Local AI");self.pull_model_input.clear();self.refresh_models()
        self._run_task(task,on_done=done)
    def delete_model(self):
        it=self.models_list.currentItem()
        if not it:return
        model=it.data(Qt.UserRole)
        if QMessageBox.question(self,"Delete model",f"Delete local model '{model}'?")!=QMessageBox.Yes:return
        self._run_task(lambda w:self.ollama.delete(model),on_done=lambda _:self.refresh_models())
    def import_checkpoint(self):
        path,_=QFileDialog.getOpenFileName(self,"Import image checkpoint","","Checkpoint (*.safetensors *.ckpt *.pt)")
        if not path:return
        dst=RUNTIME_DIR/"ComfyUI_windows_portable"/"ComfyUI"/"models"/"checkpoints"
        if not dst.exists():QMessageBox.warning(self,"ComfyUI not installed","Install Local AI before importing checkpoints.");return
        try:shutil.copy2(path,dst/Path(path).name);self.refresh_models()
        except Exception as exc:QMessageBox.critical(self,"Import failed",str(exc))

    def _settings_page(self):
        scroll=QScrollArea();scroll.setWidgetResizable(True);content=QWidget();l=QVBoxLayout(content);l.setSpacing(14);card=QFrame();card.setObjectName("card");f=QFormLayout(card);self.system_prompt=QTextEdit();self.system_prompt.setFixedHeight(110);f.addRow("System prompt",self.system_prompt);self.temperature=QDoubleSpinBox();self.temperature.setRange(0,2);self.temperature.setSingleStep(.1);f.addRow("Temperature",self.temperature);self.context=QSpinBox();self.context.setRange(1024,131072);self.context.setSingleStep(1024);f.addRow("Context window",self.context);save=QPushButton("Save AI settings");save.setObjectName("primary");save.clicked.connect(self.save_settings);f.addRow("",save);l.addWidget(card)
        hw=QFrame();hw.setObjectName("card");v=QVBoxLayout(hw);t=QLabel("Hardware");t.setStyleSheet("font-size:18px;font-weight:750;");v.addWidget(t);self.hardware_label=QLabel("Detecting…");self.hardware_label.setWordWrap(True);v.addWidget(self.hardware_label);self.recommend_label=QLabel("");self.recommend_label.setWordWrap(True);self.recommend_label.setStyleSheet("color:#79dca1;");v.addWidget(self.recommend_label);l.addWidget(hw)
        setup=QFrame();setup.setObjectName("card");s=QVBoxLayout(setup);t=QLabel("One-click local AI setup");t.setStyleSheet("font-size:18px;font-weight:750;");s.addWidget(t);desc=QLabel("Downloads and configures Ollama, the default chat model, ComfyUI, and the default image model. Large downloads are saved under ~/.zerogpt.");desc.setWordWrap(True);desc.setStyleSheet("color:#8c9992;");s.addWidget(desc);self.setup_progress=QProgressBar();self.setup_progress.setRange(0,100);s.addWidget(self.setup_progress);self.setup_status=QLabel("Ready");s.addWidget(self.setup_status);self.setup_log=QTextEdit();self.setup_log.setReadOnly(True);self.setup_log.setFixedHeight(150);s.addWidget(self.setup_log);b=QPushButton("↓  Install / Repair everything");b.setObjectName("primary");b.clicked.connect(self.install_local_ai);s.addWidget(b);l.addWidget(setup);l.addStretch();scroll.setWidget(content);return scroll
    def _load_settings(self):d=self.storage.defaults();self.system_prompt.setPlainText(d["system_prompt"]);self.temperature.setValue(d["temperature"]);self.context.setValue(d["num_ctx"])
    def save_settings(self):self.storage.set_setting("system_prompt",self.system_prompt.toPlainText().strip());self.storage.set_setting("temperature",self.temperature.value());self.storage.set_setting("num_ctx",self.context.value());self.setup_status.setText("Settings saved.")
    def refresh_hardware(self):
        try:
            x=detect_hardware();self.hardware_label.setText(f"CPU: {x.cpu}\nRAM: {x.ram_gb:.1f} GB\nGPU: {x.gpu}\nVRAM: {x.vram_gb:.1f} GB\nFree disk: {x.disk_free_gb:.1f} GB");self.recommend_label.setText("Suggested local models: "+" • ".join(f"{n} ({lab})" for n,lab in recommended_models(x)))
        except Exception as exc:self.hardware_label.setText(f"Hardware detection unavailable: {exc}")
    def install_local_ai(self):
        if self._active_worker:return
        self.pages.setCurrentIndex(3);self.install_btn.setEnabled(False);self.install_btn.setText("Installing local AI…");self.setup_progress.setValue(0);self.setup_log.clear()
        def task(w):SetupManager(lambda m:w.log.emit(str(m)),lambda value,label:w.progress.emit(value,label)).install_everything();return True
        def prog(v,label):self.setup_progress.setValue(v);self.setup_status.setText(label)
        def done(_):self.install_btn.setEnabled(True);self.install_btn.setText("✓ Local AI ready");self.setup_status.setText("Setup complete — local chat and image generation are ready.");self.refresh_status();self.refresh_models()
        self._run_task(task,on_done=done,on_progress=prog,on_log=lambda m:self.setup_log.append(html.escape(m)),on_error=self._setup_error)
    def _setup_error(self,msg):self.install_btn.setEnabled(True);self.install_btn.setText("↓  Install / Repair Local AI");self.setup_status.setText("Setup failed. See log below.");self.setup_log.append("ERROR: "+html.escape(msg));QMessageBox.critical(self,"ZeroGPT setup",msg)

    def _run_task(self,fn,on_done=None,on_chunk=None,on_progress=None,on_log=None,on_error=None):
        if self._active_worker:return
        thread=QThread(self);worker=TaskWorker(fn);worker.moveToThread(thread);thread.started.connect(worker.run)
        if on_done:worker.result.connect(on_done)
        if on_chunk:worker.chunk.connect(on_chunk)
        if on_progress:worker.progress.connect(on_progress)
        if on_log:worker.log.connect(on_log)
        worker.error.connect(on_error or self._task_error);worker.finished.connect(thread.quit);worker.finished.connect(worker.deleteLater);thread.finished.connect(thread.deleteLater)
        def cleanup():
            if thread in self._threads:self._threads.remove(thread)
            if self._active_worker is worker:self._active_worker=None
            if not self.send_btn.isEnabled():self._finish_chat_controls()
        thread.finished.connect(cleanup);self._threads.append(thread);self._active_worker=worker;thread.start()
    def stop_task(self):
        if self._active_worker:self._active_worker.cancel();self.stop_btn.setText("Stopping…")
    def _task_error(self,msg):self._finish_chat_controls();QMessageBox.critical(self,"ZeroGPT",msg)
    def refresh_status(self):
        o=self.ollama.available();c=self.comfy.available();self.status.setText(f"● Ollama {'online' if o else 'offline'}\n● ComfyUI {'online' if c else 'offline'}");self.status.setStyleSheet(f"color:{'#67dfa0' if o and c else '#a8a39a'};font-size:11px;padding:6px;")
        if o:
            try:
                names=self.ollama.model_names();current=self.storage.get_setting("chat_model",self.model_box.currentText());self.model_box.blockSignals(True);self.model_box.clear();self.model_box.addItems(names or [DEFAULT_CHAT_MODEL]);
                if current in names:self.model_box.setCurrentText(current)
                self.model_box.blockSignals(False)
            except Exception:pass
        if c:
            try:
                checks=self.comfy.checkpoints();cur=self.image_model_box.currentText();self.image_model_box.clear();self.image_model_box.addItems(checks)
                if cur in checks:self.image_model_box.setCurrentText(cur)
            except Exception:pass
    def _animate(self):self._pulse=not self._pulse;col="#70eca6" if self._pulse else "#51dc8a";self.logo.setStyleSheet(f"font-size:28px;font-weight:850;color:{col};padding:4px 5px 8px 5px;")
    def closeEvent(self,event):
        if self._active_worker:self._active_worker.cancel()
        event.accept()

def run_app():
    app=QApplication(sys.argv);app.setApplicationName(APP_NAME);app.setApplicationVersion(APP_VERSION);app.setStyleSheet(STYLE);w=MainWindow();w.show();sys.exit(app.exec())
