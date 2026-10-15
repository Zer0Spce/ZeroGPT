import sqlite3
from datetime import datetime

from .config import DB_PATH


class Storage:
    def __init__(self):
        self.db = sqlite3.connect(DB_PATH)
        self.db.execute("CREATE TABLE IF NOT EXISTS chats (id INTEGER PRIMARY KEY AUTOINCREMENT, title TEXT, created_at TEXT)")
        self.db.execute("CREATE TABLE IF NOT EXISTS messages (id INTEGER PRIMARY KEY AUTOINCREMENT, chat_id INTEGER, role TEXT, content TEXT, created_at TEXT)")
        self.db.commit()

    def new_chat(self, title="New chat") -> int:
        cur = self.db.execute("INSERT INTO chats(title, created_at) VALUES(?, ?)", (title, datetime.utcnow().isoformat()))
        self.db.commit()
        return int(cur.lastrowid)

    def chats(self):
        return self.db.execute("SELECT id, title FROM chats ORDER BY id DESC").fetchall()

    def add_message(self, chat_id: int, role: str, content: str):
        self.db.execute("INSERT INTO messages(chat_id, role, content, created_at) VALUES(?,?,?,?)", (chat_id, role, content, datetime.utcnow().isoformat()))
        self.db.commit()

    def messages(self, chat_id: int):
        return [{"role": r, "content": c} for r, c in self.db.execute("SELECT role, content FROM messages WHERE chat_id=? ORDER BY id", (chat_id,)).fetchall()]
