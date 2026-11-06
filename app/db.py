"""SQLite 저장소.
- 연결은 호출마다 열고 닫아서 백업/복원/동기화 스레드와 충돌하지 않는다.
- 동기화를 위해 각 항목은 uid(전역 고유ID), rev(수정 횟수), deleted(삭제 표시), dirty(미전송 변경)를 가진다.
"""
import hashlib
import hmac
import os
import sqlite3
import time
import uuid
from contextlib import closing
from typing import Callable, Optional

from . import config

SCHEMA = """
CREATE TABLE IF NOT EXISTS entries (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    category    TEXT NOT NULL,
    title       TEXT NOT NULL,
    solution    TEXT NOT NULL DEFAULT '',
    original    TEXT,              -- 원본 사진 (data/ 기준 상대경로)
    image       TEXT,              -- 카드용 사진(크롭본)
    crop_meta   TEXT,              -- 크롭 정보(JSON)
    created_at  REAL NOT NULL,
    updated_at  REAL NOT NULL,
    uid         TEXT,
    rev         INTEGER NOT NULL DEFAULT 1,
    deleted     INTEGER NOT NULL DEFAULT 0,
    dirty       INTEGER NOT NULL DEFAULT 1,
    device      TEXT
);
CREATE INDEX IF NOT EXISTS idx_entries_cat ON entries(category);
CREATE TABLE IF NOT EXISTS settings (
    key   TEXT PRIMARY KEY,
    value TEXT NOT NULL
);
"""

REMOTE_FIELDS = ("category", "title", "solution", "original", "image", "crop_meta",
                 "created_at", "updated_at", "rev", "deleted", "device")


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
        # 로컬에서 데이터가 바뀌었을 때 호출(동기화 요청). 동기화 스레드의 쓰기에는 호출되지 않는다.
        self.on_local_change: Optional[Callable[[], None]] = None
        self.init()

    def _conn(self):
        conn = sqlite3.connect(str(self.path), timeout=15)
        conn.row_factory = sqlite3.Row
        return conn

    def _notify(self):
        if self.on_local_change:
            self.on_local_change()

    def init(self):
        with closing(self._conn()) as c, c:
            c.executescript(SCHEMA)
            cols = {r["name"] for r in c.execute("PRAGMA table_info(entries)")}
            for name, ddl in (("uid", "TEXT"), ("rev", "INTEGER NOT NULL DEFAULT 1"),
                              ("deleted", "INTEGER NOT NULL DEFAULT 0"),
                              ("dirty", "INTEGER NOT NULL DEFAULT 1"), ("device", "TEXT")):
                if name not in cols:
                    c.execute(f"ALTER TABLE entries ADD COLUMN {name} {ddl}")
            for row in c.execute("SELECT id FROM entries WHERE uid IS NULL").fetchall():
                c.execute("UPDATE entries SET uid=?, dirty=1 WHERE id=?", (uuid.uuid4().hex, row["id"]))
            for old, new in config.LEGACY_CATEGORY_MAP.items():
                c.execute("UPDATE entries SET category=?, dirty=1 WHERE category=?", (new, old))
            c.execute("CREATE UNIQUE INDEX IF NOT EXISTS idx_entries_uid ON entries(uid)")
            defaults = {
                "font_pt": str(config.DEFAULT_FONT_PT),
                "card_ratio": config.DEFAULT_RATIO,
                "password": _hash_password(config.DEFAULT_PASSWORD),
                "device_id": uuid.uuid4().hex,
                "sync_path": "",
                "sync_auto": "1",
                "sync_interval": str(config.DEFAULT_SYNC_INTERVAL),
                "shared_rev": "0",        # 공유 설정(비밀번호/카드비율)의 버전
                "shared_dirty": "0",
            }
            for k, v in defaults.items():
                c.execute("INSERT OR IGNORE INTO settings(key, value) VALUES(?, ?)", (k, v))

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
    def device_id(self) -> str:
        return self.get_setting("device_id")

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

    # ---- 공유 설정 (모든 PC가 같은 값을 쓴다: 비밀번호, 카드 비율) ----
    def _bump_shared(self):
        rev = int(self.get_setting("shared_rev", "0")) + 1
        self.set_setting("shared_rev", str(rev))
        self.set_setting("shared_dirty", "1")
        self._notify()

    def set_card_ratio(self, key: str):
        self.set_setting("card_ratio", key)
        self._bump_shared()

    def verify_password(self, password: str) -> bool:
        return _check_password(password, self.get_setting("password"))

    def set_password(self, new_password: str):
        self.set_setting("password", _hash_password(new_password))
        self._bump_shared()

    def shared_state(self) -> dict:
        return {"password": self.get_setting("password"), "card_ratio": self.card_ratio_key,
                "rev": int(self.get_setting("shared_rev", "0")),
                "dirty": self.get_setting("shared_dirty") == "1"}

    def apply_shared(self, remote: dict):
        """다른 PC에서 온 공유 설정을 적용(전송 대기 상태는 해제)."""
        if remote.get("password"):
            self.set_setting("password", remote["password"])
        if remote.get("card_ratio") in config.RATIOS:
            self.set_setting("card_ratio", remote["card_ratio"])
        self.set_setting("shared_rev", str(int(remote.get("rev", 0))))
        self.set_setting("shared_dirty", "0")

    def clear_shared_dirty(self):
        self.set_setting("shared_dirty", "0")

    # ---- 항목 ----
    def list_entries(self, category: str, query: str = "") -> list:
        with closing(self._conn()) as c:
            rows = c.execute("SELECT * FROM entries WHERE category=? AND deleted=0 ORDER BY id DESC",
                             (category,)).fetchall()
        items = [dict(r) for r in rows]
        q = query.strip().casefold()
        if q:  # 대소문자 무시 + 부분 일치 (유니코드 포함)
            items = [e for e in items if q in e["title"].casefold()]
        return items

    def get_entry(self, entry_id: int) -> Optional[dict]:
        with closing(self._conn()) as c:
            row = c.execute("SELECT * FROM entries WHERE id=? AND deleted=0", (entry_id,)).fetchone()
        return dict(row) if row else None

    def add_entry(self, category, title, solution, original, image, crop_meta=None) -> int:
        now = time.time()
        with closing(self._conn()) as c, c:
            cur = c.execute(
                "INSERT INTO entries(category,title,solution,original,image,crop_meta,created_at,updated_at,"
                "uid,rev,deleted,dirty,device) VALUES(?,?,?,?,?,?,?,?,?,1,0,1,?)",
                (category, title, solution, original, image, crop_meta, now, now,
                 uuid.uuid4().hex, self.device_id))
            new_id = cur.lastrowid
        self._notify()
        return new_id

    def update_entry(self, entry_id: int, **fields):
        allowed = {"title", "solution", "original", "image", "crop_meta"}
        fields = {k: v for k, v in fields.items() if k in allowed}
        if not fields:
            return
        fields.update(updated_at=time.time(), device=self.device_id)
        sets = ", ".join(f"{k}=?" for k in fields)
        with closing(self._conn()) as c, c:
            c.execute(f"UPDATE entries SET {sets}, rev=rev+1, dirty=1 WHERE id=?", (*fields.values(), entry_id))
        self._notify()

    def delete_entry(self, entry_id: int):
        """실제로 지우지 않고 '삭제됨' 표시를 남겨 다른 PC에도 삭제가 전파되게 한다."""
        with closing(self._conn()) as c, c:
            c.execute("UPDATE entries SET deleted=1, rev=rev+1, dirty=1, updated_at=?, device=? WHERE id=?",
                      (time.time(), self.device_id, entry_id))
        self._notify()

    def all_entries(self) -> list:
        with closing(self._conn()) as c:
            return [dict(r) for r in c.execute("SELECT * FROM entries WHERE deleted=0").fetchall()]

    # ---- 동기화용 ----
    def get_by_uid(self, uid: str) -> Optional[dict]:
        with closing(self._conn()) as c:
            row = c.execute("SELECT * FROM entries WHERE uid=?", (uid,)).fetchone()
        return dict(row) if row else None

    def dirty_entries(self) -> list:
        with closing(self._conn()) as c:
            return [dict(r) for r in c.execute("SELECT * FROM entries WHERE dirty=1").fetchall()]

    def dirty_count(self) -> int:
        with closing(self._conn()) as c:
            n = c.execute("SELECT COUNT(*) FROM entries WHERE dirty=1").fetchone()[0]
        return n + (1 if self.get_setting("shared_dirty") == "1" else 0)

    def mark_clean(self, uid: str, rev: int):
        """전송 중에 다시 수정되지 않았을 때만(rev 동일) 전송 완료로 표시."""
        with closing(self._conn()) as c, c:
            c.execute("UPDATE entries SET dirty=0 WHERE uid=? AND rev=?", (uid, rev))

    def upsert_remote(self, uid: str, rec: dict):
        vals = [rec.get(k) for k in REMOTE_FIELDS]
        with closing(self._conn()) as c, c:
            row = c.execute("SELECT id FROM entries WHERE uid=?", (uid,)).fetchone()
            if row:
                sets = ", ".join(f"{k}=?" for k in REMOTE_FIELDS)
                c.execute(f"UPDATE entries SET {sets}, dirty=0 WHERE uid=?", (*vals, uid))
            else:
                cols = ",".join(REMOTE_FIELDS)
                marks = ",".join("?" * len(REMOTE_FIELDS))
                c.execute(f"INSERT INTO entries({cols},uid,dirty) VALUES({marks},?,0)", (*vals, uid))

    def mark_all_dirty(self):
        """백업 가져오기 후: 가져온 데이터를 공유 폴더의 기존 내용보다 우선하도록 rev 를 올리고 전송 대기."""
        with closing(self._conn()) as c, c:
            c.execute("UPDATE entries SET rev=rev+1000, dirty=1, updated_at=?, device=?",
                      (time.time(), self.device_id))
        self.set_setting("shared_dirty", "1")
        self.set_setting("shared_rev", str(int(self.get_setting("shared_rev", "0")) + 1000))
        self._notify()
