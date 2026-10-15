import json
import sqlite3
from datetime import datetime, timezone

from .config import DB_PATH, DEFAULT_SYSTEM_PROMPT


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


class Storage:
    def __init__(self):
        self.db = sqlite3.connect(DB_PATH, check_same_thread=False)
        self.db.row_factory = sqlite3.Row
        self._migrate()

    def _migrate(self):
        self.db.executescript("""
        CREATE TABLE IF NOT EXISTS chats (id INTEGER PRIMARY KEY AUTOINCREMENT,title TEXT NOT NULL DEFAULT 'New chat',created_at TEXT,updated_at TEXT);
        CREATE TABLE IF NOT EXISTS messages (id INTEGER PRIMARY KEY AUTOINCREMENT,chat_id INTEGER NOT NULL,role TEXT NOT NULL,content TEXT NOT NULL,attachment TEXT,created_at TEXT);
        CREATE TABLE IF NOT EXISTS generations (id INTEGER PRIMARY KEY AUTOINCREMENT,path TEXT NOT NULL,prompt TEXT,negative TEXT,model TEXT,width INTEGER,height INTEGER,seed INTEGER,created_at TEXT);
        CREATE TABLE IF NOT EXISTS settings (key TEXT PRIMARY KEY,value TEXT);
        """)
        columns = {r["name"] for r in self.db.execute("PRAGMA table_info(messages)")}
        if "attachment" not in columns:
            self.db.execute("ALTER TABLE messages ADD COLUMN attachment TEXT")
        chat_columns = {r["name"] for r in self.db.execute("PRAGMA table_info(chats)")}
        if "updated_at" not in chat_columns:
            self.db.execute("ALTER TABLE chats ADD COLUMN updated_at TEXT")
        self.db.commit()

    def new_chat(self, title="New chat") -> int:
        stamp = now_iso()
        cur = self.db.execute("INSERT INTO chats(title,created_at,updated_at) VALUES(?,?,?)", (title, stamp, stamp))
        self.db.commit()
        return int(cur.lastrowid)

    def chats(self, search: str = ""):
        if search.strip():
            rows = self.db.execute("SELECT id,title,updated_at FROM chats WHERE title LIKE ? ORDER BY updated_at DESC,id DESC", (f"%{search.strip()}%",)).fetchall()
        else:
            rows = self.db.execute("SELECT id,title,updated_at FROM chats ORDER BY updated_at DESC,id DESC").fetchall()
        return [dict(r) for r in rows]

    def rename_chat(self, chat_id: int, title: str):
        self.db.execute("UPDATE chats SET title=?,updated_at=? WHERE id=?", (title, now_iso(), chat_id)); self.db.commit()

    def delete_chat(self, chat_id: int):
        self.db.execute("DELETE FROM messages WHERE chat_id=?", (chat_id,)); self.db.execute("DELETE FROM chats WHERE id=?", (chat_id,)); self.db.commit()

    def add_message(self, chat_id: int, role: str, content: str, attachment: str | None = None) -> int:
        cur = self.db.execute("INSERT INTO messages(chat_id,role,content,attachment,created_at) VALUES(?,?,?,?,?)", (chat_id, role, content, attachment, now_iso()))
        self.db.execute("UPDATE chats SET updated_at=? WHERE id=?", (now_iso(), chat_id)); self.db.commit(); return int(cur.lastrowid)

    def messages(self, chat_id: int):
        return [dict(r) for r in self.db.execute("SELECT id,role,content,attachment,created_at FROM messages WHERE chat_id=? ORDER BY id", (chat_id,)).fetchall()]

    def delete_last_assistant(self, chat_id: int):
        row = self.db.execute("SELECT id FROM messages WHERE chat_id=? AND role='assistant' ORDER BY id DESC LIMIT 1", (chat_id,)).fetchone()
        if row:
            self.db.execute("DELETE FROM messages WHERE id=?", (row["id"],)); self.db.commit()

    def add_generation(self, **meta):
        self.db.execute("INSERT INTO generations(path,prompt,negative,model,width,height,seed,created_at) VALUES(?,?,?,?,?,?,?,?)", (meta.get("path"),meta.get("prompt"),meta.get("negative"),meta.get("model"),meta.get("width"),meta.get("height"),meta.get("seed"),now_iso())); self.db.commit()

    def generations(self, limit: int = 100):
        return [dict(r) for r in self.db.execute("SELECT * FROM generations ORDER BY id DESC LIMIT ?", (limit,)).fetchall()]

    def get_setting(self, key: str, default=None):
        row = self.db.execute("SELECT value FROM settings WHERE key=?", (key,)).fetchone()
        if not row: return default
        try: return json.loads(row["value"])
        except Exception: return row["value"]

    def set_setting(self, key: str, value):
        self.db.execute("INSERT INTO settings(key,value) VALUES(?,?) ON CONFLICT(key) DO UPDATE SET value=excluded.value", (key,json.dumps(value))); self.db.commit()

    def defaults(self):
        return {"system_prompt":self.get_setting("system_prompt",DEFAULT_SYSTEM_PROMPT),"temperature":float(self.get_setting("temperature",0.7)),"num_ctx":int(self.get_setting("num_ctx",8192))}
