"""SQLite 저장소. 연결은 호출마다 열고 닫아서 백업/복원 시 파일 잠금이 남지 않는다."""
import hashlib
import hmac
import os
import sqlite3
import time
from contextlib import closing
from typing import Optional

from . import config

SCHEMA = """
CREATE TABLE IF NOT EXISTS entries (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    category    TEXT NOT NULL,
    title       TEXT NOT NULL,
    solution    TEXT NOT NULL DEFAULT '',
    original    TEXT,              -- 원본 사진 (data/ 기준 상대경로)
    image       TEXT,              -- 카드용 사진 (검사PC: 크롭본 / 제어PC: 원본과 동일)
    crop_meta   TEXT,              -- 크롭 정보(JSON)
    created_at  REAL NOT NULL,
    updated_at  REAL NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_entries_cat ON entries(category);
CREATE TABLE IF NOT EXISTS settings (
    key   TEXT PRIMARY KEY,
    value TEXT NOT NULL
);
"""


def _hash_password(password: str, salt: Optional[bytes] = None) -> str:
    salt = salt or os.urandom(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, 120_000)
    return salt.hex() + "$" + digest.hex()


def _check_password(password: str, stored: str) -> bool:
    try:
        salt_hex, digest_hex = stored.split("$", 1)
        salt = bytes.fromhex(salt_hex)
    except ValueError:
        return False
    candidate = _hash_password(password, salt).split("$", 1)[1]
    return hmac.compare_digest(candidate, digest_hex)


class Database:
    def __init__(self, path=None):
        self.path = path or config.DB_PATH
        self.init()

    def _conn(self):
        conn = sqlite3.connect(str(self.path))
        conn.row_factory = sqlite3.Row
        return conn

    def init(self):
        with closing(self._conn()) as c, c:
            c.executescript(SCHEMA)
            c.execute("INSERT OR IGNORE INTO settings(key, value) VALUES('font_pt', ?)",
                      (str(config.DEFAULT_FONT_PT),))
            c.execute("INSERT OR IGNORE INTO settings(key, value) VALUES('card_ratio', ?)",
                      (config.DEFAULT_RATIO,))
            c.execute("INSERT OR IGNORE INTO settings(key, value) VALUES('password', ?)",
                      (_hash_password(config.DEFAULT_PASSWORD),))

    # ---- 설정 ----
    def get_setting(self, key: str, default: str = "") -> str:
        with closing(self._conn()) as c:
            row = c.execute("SELECT value FROM settings WHERE key=?", (key,)).fetchone()
        return row["value"] if row else default

    def set_setting(self, key: str, value: str):
        with closing(self._conn()) as c, c:
            c.execute("INSERT INTO settings(key, value) VALUES(?, ?) "
                      "ON CONFLICT(key) DO UPDATE SET value=excluded.value", (key, str(value)))

    @property
    def font_pt(self) -> int:
        try:
            v = int(self.get_setting("font_pt", str(config.DEFAULT_FONT_PT)))
        except ValueError:
            v = config.DEFAULT_FONT_PT
        return max(config.MIN_FONT_PT, min(config.MAX_FONT_PT, v))

    @property
    def card_ratio_key(self) -> str:
        key = self.get_setting("card_ratio", config.DEFAULT_RATIO)
        return key if key in config.RATIOS else config.DEFAULT_RATIO

    @property
    def card_ratio(self) -> float:
        return config.RATIOS[self.card_ratio_key]

    # ---- 비밀번호 ----
    def verify_password(self, password: str) -> bool:
        return _check_password(password, self.get_setting("password"))

    def set_password(self, new_password: str):
        self.set_setting("password", _hash_password(new_password))

    # ---- 항목 ----
    def list_entries(self, category: str, query: str = "") -> list:
        with closing(self._conn()) as c:
            rows = c.execute("SELECT * FROM entries WHERE category=? ORDER BY id DESC",
                             (category,)).fetchall()
        items = [dict(r) for r in rows]
        q = query.strip().casefold()
        if q:  # 대소문자 무시 + 부분 일치 (유니코드 포함)
            items = [e for e in items if q in e["title"].casefold()]
        return items

    def get_entry(self, entry_id: int) -> Optional[dict]:
        with closing(self._conn()) as c:
            row = c.execute("SELECT * FROM entries WHERE id=?", (entry_id,)).fetchone()
        return dict(row) if row else None

    def add_entry(self, category, title, solution, original, image, crop_meta=None) -> int:
        now = time.time()
        with closing(self._conn()) as c, c:
            cur = c.execute(
                "INSERT INTO entries(category,title,solution,original,image,crop_meta,created_at,updated_at)"
                " VALUES(?,?,?,?,?,?,?,?)",
                (category, title, solution, original, image, crop_meta, now, now))
            return cur.lastrowid

    def update_entry(self, entry_id: int, **fields):
        allowed = {"title", "solution", "original", "image", "crop_meta"}
        fields = {k: v for k, v in fields.items() if k in allowed}
        if not fields:
            return
        fields["updated_at"] = time.time()
        sets = ", ".join(f"{k}=?" for k in fields)
        with closing(self._conn()) as c, c:
            c.execute(f"UPDATE entries SET {sets} WHERE id=?", (*fields.values(), entry_id))

    def delete_entry(self, entry_id: int):
        with closing(self._conn()) as c, c:
            c.execute("DELETE FROM entries WHERE id=?", (entry_id,))

    def all_entries(self) -> list:
        with closing(self._conn()) as c:
            return [dict(r) for r in c.execute("SELECT * FROM entries").fetchall()]
